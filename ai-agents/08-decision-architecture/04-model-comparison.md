---
created: 2026-05-28
tags: [course/decision-architecture, models, comparison, providers]
status: active
---

# Урок 31: Сравнение моделей — выбор провайдера в 2026

> [!quote] Ключевая идея
> Лучшей модели не существует. Есть лучшая модель **для вашей задачи**. GPT-5.5, Claude Opus 4.7 и Gemini 3.1 Pro — лидеры в разных дисциплинах. DeepSeek V4 Flash и Qwen3-Coder-30B дают 90% качества за 10% цены. Выбор провайдера — это треугольник: качество × скорость × цена.

---

## Картина рынка, май 2026

Весна 2026 — аномальный релиз-шторм. В течение 30 дней:

| Дата | Событие |
|------|---------|
| Апрель | OpenAI: GPT-5.5 (флагман), GPT-5.4 (mid-tier), GPT-5.4 Nano (бюджет) |
| Апрель | Anthropic: Claude Opus 4.7 (рекорд SWE-bench 87.6%) |
| Май | Google I/O: Gemini 3.5 Flash (4x скорость), Gemini Spark (24/7 агент) |
| Май | DeepSeek: V4 Pro (MIT лицензия, -75% цены) |
| Май | Alibaba: Qwen 3.7 Max (35h автономной работы) |
| Май | Meta: Llama 4 Scout (10M контекст) |

**Тренд:** Контекст 1M+ стал стандартом. Open-source модели догоняют закрытые по качеству, оставляя их далеко позади по цене. Разрыв между «бюджетом» и «фронтиром» — от $0.25 до $30 за миллион выходных токенов (120x).

---

## Флагманские модели — качество без компромиссов

| Модель | Input $/M tok | Output $/M tok | Сильная сторона |
|--------|:------------:|:-------------:|-----------------|
| GPT-5.5 (OpenAI) | $5.00 | $30.00 | Универсальность, экосистема |
| Claude Opus 4.7 (Anthropic) | $5.00 | $25.00 | Кодинг (SWE-bench 87.6%), безопасность |
| Gemini 3.1 Pro (Google) | $2.00 | $12.00 | Мультимодальность, экосистема Google |
| DeepSeek V4 Pro | $0.44 | $0.87 | Лучшее соотношение цена/качество |

```python
# Decision: когда брать флагман
FLAGSHIP_USE_CASES = {
    "code_review": "Claude Opus 4.7",      # #1 на SWE-bench
    "complex_reasoning": "GPT-5.5",        # лучшее общее reasoning
    "video_analysis": "Gemini 3.1 Pro",    # нативная работа с видео
    "security_critical": "Claude Opus 4.7",# строгие guardrails
    "research": "GPT-5.5",                 # широта знаний
}
```

> [!tip] Когда платить $30/M?
> Только когда цена ошибки выше стоимости вызова. Для code review крит-бага — да. Для суммаризации email — нет.

---

## Mid-tier — баланс качества и цены

| Модель | Input $/M tok | Output $/M tok | Когда брать |
|--------|:------------:|:-------------:|-------------|
| GPT-5.4 | $2.50 | $15.00 | Универсальные задачи |
| Claude Sonnet 4.6 | $3.00 | $15.00 | Кодинг (чуть ниже Opus) |
| Gemini 2.5 Pro | $1.25 | $10.00 | Мультимодальность, цена |
| Gemini 3.5 Flash | $0.50 | $3.00 | Скорость (4x быстрее конкурентов) |

**Сладкая зона:** 80% production-задач закрываются этими моделями. Флагман нужен только для 20% самых сложных случаев.

```python
class ModelRouter:
    """
    Маршрутизирует запросы между моделями в зависимости от сложности.
    """
    TIERS = {
        "cheap": {
            "model": "gemini-2.5-flash",
            "max_complexity": 3,   # 1-10 шкала
            "cost_per_call": 0.002,
        },
        "mid": {
            "model": "claude-sonnet-4.6",
            "max_complexity": 7,
            "cost_per_call": 0.015,
        },
        "flagship": {
            "model": "claude-opus-4.7",
            "max_complexity": 10,
            "cost_per_call": 0.05,
        },
    }

    def route(self, task: str, complexity: int) -> str:
        if complexity <= self.TIERS["cheap"]["max_complexity"]:
            return self.TIERS["cheap"]["model"]
        elif complexity <= self.TIERS["mid"]["max_complexity"]:
            return self.TIERS["mid"]["model"]
        return self.TIERS["flagship"]["model"]
```

---

## Бюджетные модели — 90% качества за 10% цены

| Модель | Input $/M tok | Output $/M tok | Месяц (10K запр/день) |
|--------|:------------:|:-------------:|:--------------------:|
| DeepSeek V4 Flash | $0.14 | $0.28 | **$71** |
| Qwen3-Coder-30B | n/a | $0.35 | ~$105 |
| GPT-5.4 Nano | $0.20 | $1.25 | **$75** |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | **$30** |
| Claude Haiku 4.5 | $1.00 | $5.00 | $300 |

**Чемпион по цене:** Gemini 2.5 Flash-Lite — $30/мес за 10K запросов/день.
**Чемпион по value:** DeepSeek V4 Flash — $71/мес, quality/price ratio 34.8 (лучший в индустрии).

```python
# Сравнение стоимости: 100K запросов/день
costs = {
    "gpt-5.5":      100000 * 0.030,  # $3000/день
    "claude-opus":  100000 * 0.025,  # $2500/день
    "deepseek-v4":  100000 * 0.00028, # $28/день  ← 107x дешевле!
}
```

> [!warning]
> Бюджетные модели экономят на **качестве рассуждения**. Для простых задач (суммаризация, классификация, извлечение) — идеально. Для кода со сложной логикой — могут галлюцинировать чаще.

---

## Специализированные модели

Некоторые модели заточены под конкретные задачи:

| Модель | Специализация | Цена | Эффект |
|--------|--------------|:----:|--------|
| DeepSeek Coder | Код | $0.25/M | +15% accuracy на code gen |
| Qwen3-Coder-30B | Код | $0.35/M | Score 8.8/10 на coding-arena |
| DeepSeek-R1 | Reasoning | $2.50/M | Лучшее сложное мышление |
| Claude Opus 4.7 | Агенты | $5/$25 | SWE-bench 87.6% (агентный код) |

```python
# Router по типу задачи
TASK_MODEL_MAP = {
    "chat": "deepseek-v4-flash",       # дёшево, быстро
    "code_gen": "qwen3-coder-30b",     # специалист по коду
    "code_review": "claude-opus-4.7",  # лучшее качество
    "debug": "deepseek-r1",            # мыслит перед ответом
    "summary": "gemini-2.5-flash-lite", # бюджет
    "translation": "gpt-5.4-nano",     # универсальный бюджет
}
```

---

## Открытые модели (open-weight)

| Модель | Разработчик | Лицензия | Контекст | Плюсы | Минусы |
|--------|-----------|:---------:|:--------:|-------|--------|
| Llama 4 Scout | Meta | MIT | 10M токенов | Огромный контекст | Требует GPU |
| DeepSeek V4 Pro | DeepSeek | MIT | 1M | Цена, качество | Меньше инструментов |
| Qwen3-32B | Alibaba | Apache 2.0 | 1M | Хороший универсал | Китайский bias |
| GLM-5.1 | Z.AI | Apache 2.0 | 1M | Сильное reasoning | Меньше интеграций |
| Kimi K2.6 | Moonshot | Apache 2.0 | 1M | Top open-weights | Меньше сообщество |

**Когда выбирать open-weight:**
- Данные нельзя отправлять на API (регуляторика, секретность)
- Нужен дешёвый self-hosted инференс
- Долгие сессии (Qwen 3.7 Max — 35h автономной работы)
- Кастомизация / fine-tuning

---

## Мультимодальность

| Модель | Текст | Код | Изображения | Аудио | Видео |
|--------|:----:|:---:|:----------:|:-----:|:-----:|
| GPT-5.5 | ✅ | ✅ | ✅ (генерация) | ✅ | ❌ |
| Claude Opus 4.7 | ✅ | ✅ (лучший) | ✅ | ❌ | ❌ |
| Gemini 3.1 Pro | ✅ | ✅ | ✅ | ✅ | ✅ (нативное) |
| DeepSeek V4 Pro | ✅ | ✅ | ❌ | ❌ | ❌ |

**Если задача мультимодальная (видео + аудио + текст)** — Gemini вне конкуренции. Единственная модель с нативной обработкой видео.

---

## Decision Tree — выбор модели

```python
def select_model(task_type: str, budget: str, needs_multimodal: bool) -> str:
    """Выбирает оптимальную модель по задаче, бюджету и модальности."""

    if needs_multimodal:
        if budget == "budget":
            return "gemini-2.5-flash"
        return "gemini-3.1-pro"

    if budget == "budget":
        return "deepseek-v4-flash"   # $71/мес

    if budget == "economy":
        return "claude-sonnet-4.6"   # $6,375/мес

    # Premium — выбираем по задаче
    PREMIUM = {
        "code": "claude-opus-4.7",
        "writing": "claude-opus-4.7",
        "reasoning": "gpt-5.5",
        "research": "gpt-5.5",
        "translation": "gpt-5.4",
        "analysis": "gemini-3.1-pro",
    }
    return PREMIUM.get(task_type, "gpt-5.4")
```

---

## Сравнение контекстных окон

| Модель | Макс. контекст | Практический лимит |
|--------|:-------------:|:------------------:|
| Gemini 3.1 Pro | 2M токенов | ~1.5M (падает скорость) |
| Llama 4 Scout | 10M токенов | ~8M |
| GPT-5.5 | 1M токенов | ~900K |
| Claude Opus 4.7 | 200K токенов | ~190K |
| DeepSeek V4 Pro | 1M токенов | ~1M |

> [!tip] Контекст 2M+ — это маркетинг
> Gemini действительно держит 2M токенов, но на 1.5M+ скорость падает в 5-10 раз. Реальный практический лимит для всех моделей — ~500K-1M с приемлемой скоростью.

---

## Практическое задание

1. Составь routing-таблицу для трёх задач из твоего проекта: выбери модель (флагман / mid-tier / бюджет) для каждой задачи. Обоснуй выбор ценой и качеством.

2. Напиши функцию `select_model(task_type, budget, needs_multimodal)`, которая возвращает название модели по критериям из урока. Протестируй на 5 разных сценариях.

---

## Проверь себя

1. Какие три категории моделей по цене существуют? Приведи пример каждой.
2. Какая модель лидирует по SWE-bench в 2026?
3. Когда open-weight модель выгоднее API?
4. Что такое ModelRouter и зачем он нужен?
5. Какая модель единственная с нативной поддержкой видео?
6. Почему «лучшей модели не существует»?

---

## Резюме

```
Выбор модели = задача × бюджет × модальность

Флагман ($25-30/M):
  - Claude Opus 4.7 → код, агенты, безопасность
  - GPT-5.5 → универсальное reasoning
  - Gemini 3.1 Pro → мультимодальность

Mid-tier ($3-15/M):
  - 80% production-задач
  - Claude Sonnet 4.6 / GPT-5.4 / Gemini 2.5 Pro

Бюджет ($0.10-1.25/M):
  - DeepSeek V4 Flash — value champion
  - Gemini 2.5 Flash-Lite — дешевле всех
  - GPT-5.4 Nano — универсальный бюджет

Open-weight:
  - Llama 4 Scout (10M ctx), DeepSeek V4 Pro (MIT)
  - Для self-hosted / секретных данных

Правило: ModelRouter с 3 tier-ами сокращает счёт в 5-10x
         без заметной потери качества.
```

---

## Ссылки

- Назад: [[08-decision-architecture/03-cost-optimization]]
- Дальше: [[08-decision-architecture/01-fine-tuning-rag-prompting]]
- [[12-quality-evolution/02-ab-testing]] — A/B тестирование моделей
- [LLM Leaderboard 2026](https://llm-stats.com/) — 300+ моделей
- [AI API Pricing 2026](https://dev.to/neverknowsbest_5e174c23a3/ai-api-pricing-in-2026-what-you-actually-pay-for-gpt-55-claude-opus-gemini-and-20-models-3ani)
