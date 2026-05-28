---
created: 2026-05-28
tags: [course/performance-deep, inference, kv-cache, optimization, latency]
status: active
---

# Урок 25.1: Inference Optimization — KV-Cache, Batching, PagedAttention

> [!quote] Ключевая идея
> Inference — это 90% стоимости AI-агента в production. KV-cache, continuous batching, PagedAttention, Flash Attention — каждая техника даёт 2-10x ускорение. Понимание inference engine — skill уровня Architect.

---

## 1. KV-Cache Deep Dive

```python
class KVCache:
    """Key-Value cache для attention."""

    def __init__(self, max_batch_size: int = 32, max_seq_len: int = 128000, num_layers: int = 32):
        # [batch, layers, heads, seq_len, head_dim]
        self.key_cache = torch.zeros(max_batch_size, num_layers, 32, max_seq_len, 128)
        self.value_cache = torch.zeros(max_batch_size, num_layers, 32, max_seq_len, 128)
        self.current_len = 0

    def prefill(self, input_ids: torch.Tensor, model) -> torch.Tensor:
        """Prefill: первый проход, заполняем кэш."""

        with torch.no_grad():
            for layer in model.layers:
                # Compute K,V for all input tokens
                k, v = layer.compute_kv(input_ids)
                # Store in cache
                self.key_cache[:, layer.id, :, :len(input_ids)] = k
                self.value_cache[:, layer.id, :, :len(input_ids)] = v

        self.current_len = len(input_ids)
        return model.lm_head(logits_from_cache)

    def decode(self, token: int, model) -> int:
        """Decode: один токен, используем кэш."""

        with torch.no_grad():
            for layer in model.layers:
                # Compute KV только для нового токена
                k, v = layer.compute_kv(token)
                # Append to cache
                pos = self.current_len
                self.key_cache[:, layer.id, :, pos] = k
                self.value_cache[:, layer.id, :, pos] = v

        self.current_len += 1
        return next_token

    def memory_usage(self) -> dict:
        """Память, занимаемая KV-cache."""
        bytes_per_element = 2  # fp16
        total_bytes = (
            self.key_cache.numel() + self.value_cache.numel()
        ) * bytes_per_element
        return {
            "total_gb": total_bytes / 1024**3,
            "per_token_mb": total_bytes / 1024**2 / max(self.current_len, 1),
        }

    @staticmethod
    def estimate_memory(model_size: str, context_len: int, batch_size: int = 1) -> float:
        """Оценка памяти KV-cache для модели."""
        configs = {
            "7B": {"layers": 32, "heads": 32, "dim": 128},
            "13B": {"layers": 40, "heads": 40, "dim": 128},
            "70B": {"layers": 80, "heads": 64, "dim": 128},
        }
        cfg = configs[model_size]
        bytes_per_element = 2  # fp16
        # K + V = 2 * layers * heads * seq_len * dim * batch * 2 bytes
        memory = (2 * cfg["layers"] * cfg["heads"] * context_len * cfg["dim"] * batch_size * bytes_per_element)
        return memory / 1024**3  # GB
```

---

## 2. Continuous Batching

```python
class ContinuousBatching:
    """Continuous batching: динамическое добавление запросов."""

    def __init__(self, max_batch_size: int = 32):
        self.scheduler = Scheduler()
        self.kv_cache = KVCache()
        self.running_requests = []
        self.pending_requests = []
        self.max_batch_size = max_batch_size

    async def add_request(self, request: dict):
        """Добавляет запрос в очередь."""

        if len(self.running_requests) < self.max_batch_size:
            self.running_requests.append(request)
            # Prefill для нового запроса
            await self._prefill(request)
        else:
            self.pending_requests.append(request)

    def step(self):
        """Один шаг инференса для всего батча."""

        # Iteration-level scheduling
        finished = []
        for req in self.running_requests:
            if req["generated"] >= req["max_tokens"]:
                finished.append(req)
                continue

            # Generate next token (uses KV-cache)
            token = self.kv_cache.decode(req["last_token"])
            req["output"].append(token)
            req["generated"] += 1

        # Remove finished, add pending
        for req in finished:
            self.running_requests.remove(req)
            self.kv_cache.free(req["slot"])

        while len(self.running_requests) < self.max_batch_size and self.pending_requests:
            new_req = self.pending_requests.pop(0)
            self.running_requests.append(new_req)
            self._prefill(new_req)

    def throughput(self, time_seconds: float) -> float:
        """Tokens per second."""
        total_tokens = sum(r["generated"] for r in self.running_requests)
        return total_tokens / time_seconds
```

---

## 3. PagedAttention (vLLM)

```python
class PagedAttention:
    """PagedAttention: управление KV-cache страницами."""

    def __init__(self, block_size: int = 16, num_blocks: int = 2048):
        self.block_size = block_size
        self.num_blocks = num_blocks
        # Block table: [request_id][layer][block_number] → physical_block
        self.block_table = {}
        self.free_blocks = set(range(num_blocks))

    def allocate(self, request_id: str, num_tokens: int) -> list[int]:
        """Аллоцирует страницы для запроса."""

        num_blocks_needed = (num_tokens + self.block_size - 1) // self.block_size

        if len(self.free_blocks) < num_blocks_needed:
            raise MemoryError("Out of KV-cache blocks")

        allocated = []
        for _ in range(num_blocks_needed):
            block = self.free_blocks.pop()
            allocated.append(block)

        self.block_table[request_id] = allocated
        return allocated

    def copy_on_write(self, request_id: str, block_index: int):
        """Copy-on-write для shared prefixes."""
        # При изменении shared блока создаём копию
        pass

    def free(self, request_id: str):
        """Освобождает страницы запроса."""
        for block in self.block_table.get(request_id, []):
            self.free_blocks.add(block)
        del self.block_table[request_id]

    def utilization(self) -> float:
        """Использование KV-cache."""
        used = self.num_blocks - len(self.free_blocks)
        return used / self.num_blocks
```

---

## 4. Flash Attention

```python
class FlashAttention:
    """Flash Attention: IO-aware attention (Dao et al. 2022)."""

    @staticmethod
    def memory_efficiency(seq_len: int, head_dim: int) -> dict:
        """Сравнение памяти: standard vs flash attention."""

        # Standard: O(n²) attention matrix
        standard_memory = seq_len ** 2 * 2  # fp16 = 2 bytes
        # Flash: tiled, no materialization
        flash_memory = seq_len * head_dim * 4 * 2  # Q,K,V,O

        return {
            "standard_mb": standard_memory / 1024**2,
            "flash_mb": flash_memory / 1024**2,
            "reduction": f"{standard_memory / flash_memory:.1f}x",
        }

    @staticmethod
    def speedup(model_size: str, seq_len: int) -> dict:
        """Ожидаемое ускорение от Flash Attention."""
        speedups = {
            "7B": {4096: 1.5, 16384: 2.0, 65536: 3.0, 128000: 4.0},
            "70B": {4096: 1.3, 16384: 1.8, 65536: 2.5, 128000: 3.5},
        }
        model_speedups = speedups.get(model_size, speedups["7B"])
        best_match = min(model_speedups.keys(), key=lambda k: abs(k - seq_len))
        return {"speedup": model_speedups[best_match], "at_seq_len": best_match}
```

---

## Резюме

```
Inference Optimization Techniques:

KV-Cache:         2-10x ускорение (не пересчитываем прошлое)
                  1M tokens → ~40GB (7B fp16)
                  1M tokens → ~10GB (7B fp8)

Continuous Batch: 2-4x throughput (нет wait на batch fill)
                  Динамическое добавление/удаление запросов

PagedAttention:   2-3x utilisation KV-cache
                  Виртуальная память для attention
                  Copy-on-write для shared prefixes

Flash Attention:  1.5-4x ускорение (IO-aware)
                  -∞-∞ memory for attention matrix
                  Tiling + recomputation
```

---

## Практическое задание

1. Реализуй KVCache с prefill и decode фазами.

2. Настрой ContinuousBatching: batch динамически.

3. Добавь PagedAttention с аллокацией страниц.

4. Рассчитай memory savings от Flash Attention для 128K seq.

---

## Проверь себя

1. Как работает KV-cache? Почему prefill и decode разные?

2. Чем continuous batching отличается от static batching?

3. Как PagedAttention экономит память?

4. Зачем Flash Attention пересчитывает матрицу?

---

## Ссылки

- [[02-quantization]] — следующий урок: quantization
- [[../../21-context-window-deep/01-landscape]] — context window landscape
