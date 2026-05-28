---
created: 2026-05-28
tags: [course/fine-tuning-deep, agents, function-calling, tool-use, specialization]
status: active
---

# Урок 22.5: Fine-tuning для Агентов

> [!quote] Ключевая идея
> Fine-tuning агента — это не «сделать модель умнее». Это научить её _правильно вызывать функции, следовать формату, не отклоняться от system prompt, эффективно использовать контекст_. Агентный fine-tuning специфичен: data = трассы, а не тексты.

---

## 1. Что даёт fine-tuning агента

| Аспект | Prompting | После FT |
|--------|-----------|----------|
| Соблюдение формата function call | 85-90% | 98-99% |
| Правильный выбор инструмента | 75-85% | 95-98% |
| Следование system prompt | 80-90% | 97-99% |
| Отказ от лишних действий | 70-80% | 90-95% |
| Обработка ошибок API | 60-70% | 85-95% |

---

## 2. Dataset из Traces

```python
class TraceToDataset:
    """Конвертация production traces в fine-tuning датасет."""

    def convert_trace(self, trace: dict) -> list[dict]:
        """Из одной трассы → несколько SFT примеров."""

        examples = []
        for turn in trace["turns"]:
            user_message = turn["input"]
            agent_response = turn["output"]

            # Извлекаем function calls из ответа
            function_calls = self._extract_tool_calls(agent_response)

            examples.append({
                "prompt": self._format_prompt(trace["system_prompt"], user_message, trace.get("context", "")),
                "completion": self._format_completion(agent_response, function_calls),
                "metadata": {
                    "trace_id": trace["id"],
                    "tools_used": [fc["name"] for fc in function_calls],
                    "latency_ms": turn.get("latency_ms", 0),
                    "success": turn.get("success", True),
                },
            })

        return examples

    def _extract_tool_calls(self, response: str) -> list[dict]:
        """Извлекает function calls из ответа агента."""
        pattern = r'<function=(\w+)>(.*?)</function>'
        matches = re.findall(pattern, response, re.DOTALL)
        return [
            {"name": name, "arguments": args.strip()}
            for name, args in matches
        ]

    def _format_prompt(self, system: str, user: str, context: str) -> str:
        parts = [f"<system>{system}</system>"]
        if context:
            parts.append(f"<context>{context}</context>")
        parts.append(f"<user>{user}</user>")
        return "\n".join(parts)

    def _format_completion(self, response: str, function_calls: list[dict]) -> str:
        return f"<assistant>{response}</assistant>"
```

---

## 3. Специализация на функции

```python
class FunctionCallingFT:
    """Fine-tuning для точного вызова функций."""

    FUNCTIONS = [
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "location": "string",
                "unit": "string (celsius/fahrenheit)",
            }
        },
        {
            "name": "search_database",
            "description": "Search internal database",
            "parameters": {
                "query": "string",
                "limit": "integer (1-50)",
            }
        },
    ]

    def generate_synthetic_data(self, functions: list[dict], num_examples: int = 500) -> list[dict]:
        """Генерирует синтетические примеры вызова функций."""

        examples = []
        for fn in functions:
            for _ in range(num_examples // len(functions)):
                # Генерация корректного вызова
                params = self._generate_valid_params(fn["parameters"])
                user_query = self._generate_user_query(fn, params)

                examples.append({
                    "prompt": user_query,
                    "completion": json.dumps({
                        "function": fn["name"],
                        "params": params,
                    }),
                    "metadata": {"type": "valid_call", "function": fn["name"]},
                })

                # Генерация НЕкорректного вызова (negative example)
                wrong_params = self._generate_wrong_params(fn["parameters"])
                examples.append({
                    "prompt": f"User: {user_query}",
                    "completion": json.dumps({
                        "function": fn["name"],
                        "params": wrong_params,
                    }),
                    "metadata": {"type": "invalid_call", "function": fn["name"]},
                })

        return examples
```

---

## 4. Multi-turn Agent Fine-tuning

```python
class MultiTurnFT:
    """Fine-tuning для multi-turn диалогов агента."""

    def convert_conversations(self, conversations: list[list[dict]]) -> list[dict]:
        """Конвертирует multi-turn в обучающие примеры."""

        examples = []
        for conv in conversations:
            # Каждый turn — отдельный пример с историей
            for i, turn in enumerate(conv):
                history = conv[:i]  # Предыдущие turn-ы
                current = turn

                examples.append({
                    "messages": [
                        {"role": "system", "content": conv[0].get("system", "")},
                        *[{"role": m["role"], "content": m["content"]} for m in history],
                        {"role": "user", "content": current["input"]},
                    ],
                    "completion": current["output"],
                })

        return examples

    def augment_with_errors(self, examples: list[dict]) -> list[dict]:
        """Аугментация: добавляет примеры с ошибками для robustness."""

        augmented = []
        for ex in examples:
            augmented.append(ex)  # Original

            # С опечаткой в запросе
            typo_ex = deepcopy(ex)
            typo_ex["messages"][-1]["content"] = self._add_typo(ex["messages"][-1]["content"])
            augmented.append(typo_ex)

            # С неполным контекстом
            if len(ex["messages"]) > 3:
                no_ctx = deepcopy(ex)
                no_ctx["messages"] = ex["messages"][:2] + ex["messages"][-1:]
                augmented.append(no_ctx)

        return augmented
```

---

## 5. Evaluation after Agent Fine-tuning

```python
class AgentFTEvaluator:
    """Оценка качества fine-tuned агента."""

    METRICS = {
        "tool_selection_accuracy": "Правильный выбор инструмента",
        "parameter_correctness": "Правильные параметры",
        "format_compliance": "Соблюдение формата JSON/function call",
        "refusal_rate": "Отказ от небезопасных действий",
        "hallucination_rate": "Галлюцинации в ответе",
        "latency_p50": "Медианная задержка",
    }

    async def evaluate(self, base_model, ft_model, test_set: list[dict]) -> dict:
        """Сравнение base vs fine-tuned."""

        results = {"base": {}, "ft": {}}
        for label, model in [("base", base_model), ("ft", ft_model)]:
            correct_tool = 0
            correct_params = 0
            correct_format = 0

            for test in test_set:
                response = await model.generate(test["prompt"])
                if self._check_tool(response, test["expected_tool"]):
                    correct_tool += 1
                if self._check_params(response, test["expected_params"]):
                    correct_params += 1
                if self._check_format(response):
                    correct_format += 1

            n = len(test_set)
            results[label] = {
                "tool_selection_accuracy": correct_tool / n,
                "parameter_correctness": correct_params / n,
                "format_compliance": correct_format / n,
            }

        results["improvement"] = {
            k: f"+{results['ft'][k] - results['base'][k]:.1%}"
            for k in results["base"]
        }

        return results
```

---

## Резюме

```
Fine-tuning для агентов — ключевые отличия:

1. Data = трассы, не тексты
   — Конвертируем production логи в (prompt, completion)
   — Каждый turn — отдельный пример

2. Специализация на function calling
   — Синтетические данные: корректные + некорректные вызовы
   - Аугментация с ошибками для robustness

3. Multi-turn важно
   — История диалога как контекст
   — Аугментация: опечатки, неполный контекст

4. Evaluation специфичный
   — Tool selection accuracy
   — Parameter correctness
   — Format compliance

Типичный результат:
  — Tool selection: +10-15%
  — Format compliance: +8-12%
  — Hallucination: -5-10%
```

---

## Практическое задание

1. Конвертируй 10 production трасс в SFT датасет.

2. Сгенерируй 100 синтетических примеров function calling.

3. Обучи LoRA на датасете, сравни с base моделью.

4. Оцени improvement: tool selection, format compliance.

---

## Проверь себя

1. Как конвертировать production trace в обучающий пример?

2. Зачем нужны negative examples (некорректные вызовы)?

3. Как оценить качество fine-tuned агента?

4. Какие метрики специфичны для агентного fine-tuning?

---

## Ссылки

- [[02-lora-deep]] — LoRA deep dive
- [[04-data-preparation]] — data preparation
- [[06-production]] — следующий урок: production fine-tuning
