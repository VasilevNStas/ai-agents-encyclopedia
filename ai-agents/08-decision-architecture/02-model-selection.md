---
created: 2026-05-28
tags: [course/decision-architecture, model-selection, local, cloud, strategy]
status: active
---

# Урок 29: Model Selection — как выбирать модель

> [!quote] Ключевая идея
> Нет «лучшей модели». Есть модель, **достаточная** для задачи с учётом ограничений: качество, скорость, стоимость, приватность, latency. Выбор модели — это компромисс, а not гонка за лидером бенчмарков.

---

## Пять осей выбора

```
1. Quality (MMLU, HumanEval, GPQA) — насколько умна
2. Speed (tokens/s, TTFT) — как быстро отвечает
3. Cost ($/M токенов) — сколько платить
4. Context window — сколько влезает
5. Privacy — где работают данные
```

### Quality vs Speed vs Cost

```
                 Quality
                    ▲
                   /|\
                  / | \
                 /  |  \
                /   |   \
               /    |    \
              /     |     \
             /      |      \
    Claude ────────●───────●──→ Speed
    Opus          /|      /
    Gemini       / |     /
    Pro         /  |    /
    DeepSeek ──●───|───●───────→ Cost
    V3/R1          |   GPT-4o
                   |   (баланс)
              GPT-4o mini
              Claude Haiku
                   |
              Local models
              (Llama, Qwen, Mistral)
```

---

## Категории моделей

### Frontier Models (Claude Opus, GPT-4o, Gemini Pro)

| Характеристика | Значение |
|---------------|----------|
| Quality | Лучшие на рынке (MMLU >88) |
| Speed | Средняя (50-100 tok/s) |
| Cost | Высокий ($10-30 /M токенов) |
| Context | Большой (128K-2M) |
| Приватность | API (данные уходят) |

**Когда:** сложные рассуждения, генерация кода, анализ документов, архитектура.

### Middle Class (Claude Sonnet, GPT-4o mini, DeepSeek V3)

| Характеристика | Значение |
|---------------|----------|
| Quality | Хорошая (MMLU 75-85) |
| Speed | Высокая (100-200 tok/s) |
| Cost | Умеренный ($0.5-5 /M токенов) |
| Context | 128K |
| Приватность | API |

**Когда:** daily задачи, агенты, суммаризация, извлечение данных. **Стандарт для 90% агентов.**

### Small & Fast (Claude Haiku, Gemini Flash, GPT-4o mini)

| Характеристика | Значение |
|---------------|----------|
| Quality | Достаточная (MMLU 70-78) |
| Speed | Очень высокая (300-500 tok/s) |
| Cost | Низкий ($0.15-0.5 /M токенов) |
| Context | 32K-128K |
| Приватность | API |

**Когда:** простые задачи, классификация, экстракция, роутинг, кандидат для RAG.

### Local Models (Llama 3, Qwen 2.5, Mistral, DeepSeek Coder)

| Характеристика | Значение |
|---------------|----------|
| Quality | 7B=GPT-3.5, 70B≈GPT-4 | 
| Speed | Зависит от GPU (10-80 tok/s на 70B) |
| Cost | CapEx (GPU) + OpEx (electricity) |
| Context | 32K-128K |
| Приватность | Полная (данные не уходят) |

**Когда:** приватность критична, офлайн, специфичный fine-tune, автопилот.

---

## Decision Tree выбора модели

```
Данные конфиденциальны (медицина, финансы, военные)?
  ├── Да → Local model (Llama 70B, Qwen 72B)
  │         └── Нужен fine-tune? → Local + LoRA
  └── Нет
       │
       ▼
Требуется максимальное качество?
  ├── Да → Frontier (Claude Opus, GPT-4o)
  └── Нет
       │
       ▼
Требуется низкая latency (< 1s)?
  ├── Да → Small & Fast (Haiku, Flash)
  └── Нет
       │
       ▼
Работаем в режиме агента (много вызовов)?
  ├── Да → Middle Class (Sonnet, GPT-4o mini)
  │         └── Дешёвые вызовы → роутинг: Haiku для простого, Sonnet для сложного
  └── Нет
       │
       ▼
Обрабатываем большие объёмы данных?
  ├── Да → Small + LLM-as-Judge (проверка критичных случаев)
  └── Нет → Middle Class
```

---

## Local vs Cloud: глубокое сравнение

```
Характеристика          Cloud API               Local (Llama 70B)
──────────────────────────────────────────────────────────────────
Quality (MMLU)          88-90                   80-85
Latency (TTFT)          200-500ms               500ms-5s
Context window          128K-200K               32K-128K
Cost /M tok             $3-30                   ~$0.2-1 (electricity)
CapEx                   0                       $10K-50K (GPU)
Privacy                 Shared                  Complete
Fine-tuning             API LoRA                Full control
Time-to-market          Days                    Weeks
```

### Когда выбирать Cloud API

```python
def choose_cloud(task: str) -> bool:
    """Cloud API предпочтительнее, когда:"""
    conditions = [
        "быстрое прототипирование" in task,
        "мало вызовов (< 100K/день)" in task,
        "нужно frontier quality" in task,
        "нет инфраструктуры GPU" in task,
        "частые обновления модели" in task,
    ]
    return any(conditions)
```

### Когда выбирать Local

```python
def choose_local(task: str) -> bool:
    """Local model предпочтительнее, когда:"""
    conditions = [
        "конфиденциальные данные" in task,
        "миллионы вызовов в день" in task,
        "офлайн / air-gap" in task,
        "полный контроль над моделью" in task,
        "специфичный fine-tune" in task,
    ]
    return any(conditions)
```

---

## Стратегия: роутинг между моделями

Оптимальная production-архитектура использует **несколько** моделей:

```
                   ┌──────────┐
                   │ Router   │ ← Small model (Haiku, Flash)
                   │          │      классифицирует сложность
                   └────┬─────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │ Простое  │ │ Среднее  │ │ Сложное  │
     │ Haiku    │ │ Sonnet   │ │ Opus     │
     │ $0.0004  │ │ $0.003   │ │ $0.015   │
     └──────────┘ └──────────┘ └──────────┘
```

```python
class ModelRouter:
    def __init__(self):
        self.models = {
            "simple": "claude-3-haiku",
            "medium": "claude-3-sonnet",
            "complex": "claude-3-opus",
        }

    def route(self, task: str) -> str:
        # Small model классифицирует сложность
        classification = haiku_model.generate(f"""
        Классифицируй сложность задачи: simple, medium, complex.
        Задача: {task}
        Ответь одним словом.
        """)
        return self.models.get(classification.strip(), "sonnet")

    def execute(self, task: str) -> str:
        model = self.route(task)
        return api_call(model, task)

# Экономия: 60% вызовов → Haiku, 30% → Sonnet, 10% → Opus
# vs 100% → Opus: экономия ~70% cost при ~95% качества
```

**Результат:** 60-80% экономии при 95% качества frontier-модели.

---

## Критерии выбора: методика

```python
def evaluate_model(model_name: str, requirements: dict) -> float:
    """Оценка модели под требования (0..1)."""
    scores = {
        "quality": quality_score(model_name, requirements["min_quality"]),
        "speed": speed_score(model_name, requirements["max_latency_ms"]),
        "cost": cost_score(model_name, requirements["max_cost_per_call"]),
        "context": context_score(model_name, requirements["min_context"]),
    }

    # weighted sum
    weights = requirements.get("weights", {
        "quality": 0.4, "speed": 0.3, "cost": 0.2, "context": 0.1
    })
    return sum(scores[k] * weights[k] for k in scores)
```

**Пример требований:**

```yaml
# Агент поддержки
requirements:
  min_quality: 75      # MMLU
  max_latency_ms: 2000  # 2 секунды
  max_cost_per_call: 0.005  # $0.005
  min_context: 32000
  privacy: false
  # → best: Sonnet или GPT-4o mini
```

---

## Тренды и стратегия на 2026

| Тренд | Влияние |
|-------|---------|
| Small models catch up | 7B догоняют GPT-3.5, 70B → GPT-4 |
| Cost снижается | GPT-4o mini vs GPT-4 → 10x дешевле |
| Context растёт | 200K → 1M+ становится стандартом |
| Local GPU дешевеет | $10K → $5K за 70B inference |
| Multi-modal | Одна модель — текст + код + изображения |

**Стратегия архитектора 2026:**
1. Middle class как baseline (Sonnet, GPT-4o mini)
2. Small для роутинга и простых задач
3. Frontier для сложных случаев и генерации
4. Local для приватности и high-volume
5. Multi-model роутинг как production-стандарт

---

## Резюме

```
Выбор модели = Quality × Speed × Cost × Privacy

Rule of thumb:
  90% задач → Middle class (Sonnet, 4o mini)
   8% задач → Small & Fast (Haiku, Flash) для дешёвых
   2% задач → Frontier (Opus, Pro) для сложных
  Local → когда приватность или объём

Архитектор строит систему, которая:
  - маршрутизирует по сложности
  - падает на дешёвую модель при перегрузке
  - логирует качество каждой модели
```

---

## Практическое задание

1. Выбери проект и опиши требования (с помощью шаблона из 26.6)
2. Пройди по decision tree — какая модель подходит?
3. Если бы строил multi-model роутинг — как распределил бы модели?
4. Посчитай cost/month для 100K вызовов к каждой модели

---

## Проверь себя

1. Какие пять осей выбора модели?
2. Почему Middle class — стандарт для 90% агентов?
3. Когда Local model выгоднее Cloud API?
4. Как multi-model роутинг экономит cost без потери качества?

---

## Ссылки

- [[08-decision-architecture/03-cost-optimization]] — следующий урок
- [[08-decision-architecture/01-fine-tuning-rag-prompting]] — как сочетать с выбором модели
- [[05-production/04-resilience]] — fallback между моделями
