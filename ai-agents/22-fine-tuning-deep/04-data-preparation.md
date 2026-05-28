---
created: 2026-05-28
tags: [course/fine-tuning-deep, data, quality, augmentation, dedup]
status: active
---

# Урок 22.4: Data Preparation & Quality для Fine-tuning

> [!quote] Ключевая идея
> Качество данных важнее архитектуры. LoRA на плохих данных = быстрая генерация мусора. 80% успеха fine-tuning — в подготовке датасета: дедупликация, балансировка, фильтрация, аугментация.

---

## 1. Data Quality Pipeline

```python
class DataQualityPipeline:
    """Пайплайн очистки данных для fine-tuning."""

    def __init__(self):
        self.dedup = Deduplicator()
        self.filter = QualityFilter()
        self.balancer = ClassBalancer()
        self.augmenter = DataAugmenter()

    async def process(self, raw_data: list[dict]) -> list[dict]:
        log(f"Raw: {len(raw_data)} examples")

        # 1. Дедупликация
        data = self.dedup.deduplicate(raw_data)
        log(f"After dedup: {len(data)}")

        # 2. Фильтрация качества
        data = await self.filter.filter(data)
        log(f"After quality filter: {len(data)}")

        # 3. Балансировка классов
        data = self.balancer.balance(data)
        log(f"After balancing: {len(data)}")

        # 4. Аугментация
        data = await self.augmenter.augment(data)
        log(f"Final: {len(data)}")

        return data
```

---

## 2. Дедупликация

```python
class Deduplicator:
    """Дедупликация данных: exact + fuzzy + semantic."""

    def deduplicate(self, data: list[dict]) -> list[dict]:
        data = self._exact_dedup(data)
        data = self._fuzzy_dedup(data)
        data = self._semantic_dedup(data)
        return data

    def _exact_dedup(self, data: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for item in data:
            key = hashlib.md5(item["text"].encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def _fuzzy_dedup(self, data: list[dict], threshold: float = 0.95) -> list[dict]:
        """MinHash deduplication."""
        unique = []
        for item in data:
            if not any(
                self._jaccard_similarity(item["text"], existing["text"]) > threshold
                for existing in unique
            ):
                unique.append(item)
        return unique

    def _semantic_dedup(self, data: list[dict], threshold: float = 0.92) -> list[dict]:
        """Deduplication по эмбеддингам."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")

        texts = [item["text"] for item in data]
        embeddings = model.encode(texts)

        keep = []
        for i, emb in enumerate(embeddings):
            if not any(
                self._cosine_similarity(emb, embeddings[j]) > threshold
                for j in keep
            ):
                keep.append(i)

        return [data[i] for i in keep]
```

---

## 3. Quality Filtering

```python
class QualityFilter:
    """Фильтрация низкокачественных примеров."""

    async def filter(self, data: list[dict]) -> list[dict]:
        filters = [
            self._min_length(50),
            self._max_length(8192),
            self._no_toxic_content(0.7),
            self._min_information_density(0.3),
        ]

        filtered = data
        for f in filters:
            filtered = [item for item in filtered if await f(item)]

        return filtered

    async def _no_toxic_content(self, threshold: float):
        """Фильтр токсичности через LLM-as-Judge."""
        # В production: детектор токсичности
        return lambda item: True

    async def _min_information_density(self, min_density: float):
        """Фильтр: достаточно ли информации в примере."""

        def check(item):
            text = item.get("text", item.get("chosen", ""))
            if not text:
                return False
            words = len(text.split())
            unique_words = len(set(text.lower().split()))
            density = unique_words / words if words > 0 else 0
            return density >= min_density

        return check
```

---

## 4. Data Augmentation

```python
class DataAugmenter:
    """Аугментация данных для fine-tuning."""

    async def augment(self, data: list[dict], target_size: int = None) -> list[dict]:
        target = target_size or int(len(data) * 1.5)
        augmented = list(data)

        while len(augmented) < target:
            # Random augmentation
            item = random.choice(data)
            aug_method = random.choice([
                self._paraphrase,
                self._back_translate,
                self._entity_swap,
                self._noise_injection,
            ])
            new_item = await aug_method(item)
            if new_item:
                augmented.append(new_item)

        return augmented[:target]

    async def _paraphrase(self, item: dict) -> dict:
        """Парафраз через LLM."""
        new_text = await self.llm.generate(
            f"Paraphrase (keep meaning, change wording): {item['text']}"
        )
        return {**item, "text": new_text}

    async def _entity_swap(self, item: dict) -> dict:
        """Замена сущностей (имена, даты, числа)."""
        import random
        text = item["text"]
        text = re.sub(r'\b\d{4}\b', str(random.randint(2000, 2026)), text)
        text = re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', 
                     lambda m: random.choice(["Alice Smith", "Bob Jones", "Charlie Brown"]), text)
        return {**item, "text": text}

    async def _noise_injection(self, item: dict) -> dict:
        """Лёгкий шум (typos, punctuation)."""
        text = item["text"]
        if random.random() < 0.1:
            # Swap two adjacent characters
            i = random.randint(0, len(text) - 2)
            text = text[:i] + text[i+1] + text[i] + text[i+2:]
        return {**item, "text": text}
```

---

## 5. Dataset Format & Storage

```python
class DatasetFormatter:
    """Форматирование датасета под разные методы fine-tuning."""

    FORMATS = {
        "sft": {"type": "text", "fields": ["prompt", "completion"]},
        "dpo": {"type": "preference", "fields": ["prompt", "chosen", "rejected"]},
        "grpo": {"type": "prompt", "fields": ["prompt"]},
        "kto": {"type": "binary", "fields": ["prompt", "completion", "label"]},
    }

    def to_chat_format(self, dataset: list[dict], template: str = "chatml") -> list[dict]:
        """Конвертирует в chat format."""
        formatted = []
        for item in dataset:
            formatted.append({
                "messages": [
                    {"role": "user", "content": item["prompt"]},
                    {"role": "assistant", "content": item.get("completion", item.get("chosen", ""))},
                ]
            })
        return formatted

    def to_jsonl(self, dataset: list[dict], path: str):
        """Сохраняет в JSONL."""
        with open(path, "w") as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

---

## Резюме

```
Data Quality Pipeline:

Raw data ──► Dedup ──► Filter ──► Balance ──► Augment ──► Format
                │          │          │            │
           exact +    length +   class +     paraphrase +
           fuzzy +    toxicity +  domain      entity swap
           semantic   density

Checklist:
  ☐ 50+ токенов минимум
  ☐ 8192 токенов максимум
  ☐ Нет дубликатов (exact + fuzzy + semantic)
  ☐ Аугментация: +50% примеров
  ☐ Баланс классов (если классификация)
  ☐ Формат: ChatML / JSONL
```

---

## Практическое задание

1. Реализуй DataQualityPipeline для 1000 сырых примеров.

2. Добавь MinHash dedup с порогом 0.95.

3. Настрой аугментацию: парафраз + entity swap.

4. Конвертируй датасет в ChatML формат.

---

## Проверь себя

1. Какие 4 этапа проходит data quality pipeline?

2. Чем fuzzy dedup отличается от semantic dedup?

3. Какие методы аугментации данных существуют?

4. Почему качество данных важнее архитектуры модели?

---

## Ссылки

- [[02-lora-deep]] — LoRA deep dive
- [[03-rlhf-dpo]] — RLHF/DPO/GRPO
- [[05-agent-finetuning]] — следующий урок: fine-tuning для агентов
