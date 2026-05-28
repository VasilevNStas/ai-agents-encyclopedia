---
module: 15
title: Evals & Benchmarks
tags: [course, evals, benchmarks, metrics, evaluation]
---

# Модуль 15: Evals & Benchmarks — как измерять качество LLM

> [!quote] Ключевая идея
> Бенчмарки измеряют не то, что вы думаете. MMLU — не "общий интеллект", а способность отвечать на экзаменационные вопросы. SWE-bench — не "инженерные способности", а умение править репозитории. **Понимать, что измеряет бенчмарк — половина умения его интерпретировать.** Вторая половина — знать, когда ему нельзя доверять.

---

## 1. Карта бенчмарков (2026)

### Knowledge & Reasoning

| Бенчмарк | Что измеряет | Метод | Лидер 2026 | Насыщение |
|----------|-------------|-------|-----------|-----------|
| **MMLU** | 57 предметов (от права до физики) | 4-choice QA | GPT-5.5 (92.3%) | Да (люди ~90%) |
| **MMLU-Pro** | 57 предметов, сложнее | 10-choice QA | Gemini 3.1 Pro (79.8%) | Нет |
| **GPQA** | Graduate-level Q&A | Экспертные вопросы | Claude Opus 4.7 (71.2%) | Нет |
| **ARC-Challenge** | Научные вопросы (8 класс) | 4-choice QA | DeepSeek V4 (96.1%) | Почти |
| **HellaSwag** | Выбор правдоподобного окончания | 4-choice | Все > 95% | Да (потолок) |

### Coding

| Бенчмарк | Что измеряет | Метод | Лидер 2026 | Важно |
|----------|-------------|-------|-----------|-------|
| **HumanEval** | Написание функций по docstring | Pass@1 | Многие > 95% | Потолок, неинформативен |
| **SWE-bench Verified** | Реальные PR-ы (репозитории) | % решённых | Claude Opus 4.7 (72.3%) | Самый релевантный |
| **SWE-bench Multilingual** | PR на Java, TS, Go, Rust | % решённых | GPT-5.5 (61.8%) | Растёт |
| **BigCodeBench** | Полные задачи кодинга | Pass@1 | Qwen3.7-Coder (67.7%) | Многоязычный |

### Agent & Tool Use

| Бенчмарк | Что измеряет | Лидер |
|----------|-------------|-------|
| **GAIA** | Мультишаговые задачи с инструментами | GPT-5.5 (72.4%) |
| **AgentBench** | 8 сред: ОС, SQL, Web, Game | Claude Sonnet 4.6 (68.9%) |
| **WebArena** | Навигация по сайтам | Gemini Spark (55.2%) |
| **τ-bench** | Tool calling, многошаговые планы | GPT-5.5 (81.3%) |
| **BFCL v3** | Function Calling | GPT-5.5 (94.7%) |

### Safety & Honesty

| Бенчмарк | Что измеряет |
|----------|-------------|
| **SafetyBench** | Отказ от опасных запросов |
| **TruthfulQA** | Правдивость (не галлюцинации) |
| **HarmBench** | Устойчивость к red-teaming |
| **StrongREJECT** | Устойчивость к jailbreak |

---

## 2. Как читать Chatbot Arena (Elo)

### Что это

Пользователи голосуют за ответы двух анонимных моделей. Elo-рейтинг обновляется после каждого голосования.

### Как интерпретировать

```
Elo 1300 → baseline (средняя модель)
Elo 1400 → хорошая модель (top-20)
Elo 1500 → отличная (top-5)
Elo 1600 → лидер

Разница в 100 Elo ≈ 64% побед в прямом сравнении.
Разница в 200 Elo ≈ 76% побед.
```

### Ловушки

1. **Bias голосующих** — пользователи Arena — энтузиасты, не среднестатистические пользователи
2. **Prefer longer** — Arena голосует за длинные ответы (корреляция 0.8+)
3. **Style vs substance** — красивый ответ побеждает правильный
4. **Arena не измеряет cost** — GPT-5.5 может быть лучшим, но в 100x дороже DeepSeek

### Когда Arena полезна

- Общее впечатление о модели (user experience)
- Тренды (какая модель растёт быстрее)
- Creative tasks (где нет объективной метрики)

### Когда бесполезна

- Кодинг (SWE-bench лучше)
- Факты (MMLU лучше)
- Стоимость (Arena её не учитывает)

---

## 3. Когда бенчмарки врут

### Data Contamination

Модель видела тестовые данные в обучении:

```
GPT-4 на MMLU: 86.4%
GPT-4 на MMLU (вариант, где вопросы переписаны): 76.3%
Разница 10% = contamination.

Как защититься:
- Проверяй модели на свежих бенчмарках
- Смотри дату публикации бенчмарка vs дата обучения модели
- Используй held-out наборы (непубличные)
```

### Overfitting к формату

Модель научилась отвечать на multiple-choice, а не решать задачи:

```
Модель:
  MMLU: 92%
  Open-ended QA: 68%

Разрыв = модель подогнана под формат бенчмарка,
а не под реальное понимание.
```

### Single metric fallacy

Один бенчмарк не говорит ничего:

```
"Claude Opus 4.7 beats GPT-5.5 on SWE-bench!"
  → Значит только: Claude лучше чинит реальные баги.
  → Не значит: Claude лучше пишет код.
  → Не значит: Claude дешевле.
  → Не значит: Claude лучше для вашей задачи.
```

---

## 4. Как строить свой eval

Для production-систем бенчмарки бесполезны. Нужен свой eval.

### Уровень 1: Smoke tests

Проверка, что модель отвечает в принципе:

```python
SMOKE_TESTS = [
    {"prompt": "Привет", "expected": "не пустой ответ"},
    {"prompt": "1+1=?", "expected": "2"},
    {"prompt": "", "expected": "не падает"},
]

def smoke_test(model):
    for test in SMOKE_TESTS:
        response = model.generate(test["prompt"])
        assert response, f"Empty response for: {test['prompt']}"
```

### Уровень 2: Golden dataset

20-100 эталонных пар (prompt → ideal response):

```json
[
    {
        "prompt": "Напиши краткое описание функции calculate_discount",
        "ideal": "Функция вычисляет скидку на основе цены и процентного значения.",
        "checks": ["содержит 'скидк'", "не длиннее 200 символов"]
    }
]
```

Оценка:

```python
def evaluate_golden(model, dataset):
    scores = []
    for item in dataset:
        response = model.generate(item["prompt"])
        score = sum(
            1 for check in item["checks"]
            if (check.startswith("не ") and check[3:] not in response)
            or (not check.startswith("не ") and check in response)
        )
        scores.append(score / len(item["checks"]))
    return sum(scores) / len(scores)
```

### Уровень 3: LLM-as-Judge

```python
JUDGE_PROMPT = """
Ты — evaluator для AI-агента.
Оцени ответ по 5 критериям (1-5):

1. Accuracy (1-5): нет фактических ошибок?
2. Relevance (1-5): отвечает на вопрос?
3. Conciseness (1-5): нет лишнего?
4. Safety (1-5): нет опасного контента?
5. Format (1-5): соблюдён требуемый формат?

Вопрос: {prompt}
Ответ: {response}

Ответь JSON: {{"accuracy": N, "relevance": N, ...}}
"""

def llm_judge(prompt, response, judge_model="gpt-4o"):
    result = judge_model.generate(JUDGE_PROMPT.format(
        prompt=prompt, response=response
    ))
    return json.loads(result)
```

### Production checklist

```
Мой eval готов к production, если:
  [ ] Есть минимум 20 golden пар
  [ ] Есть негативные тесты (что НЕ должен делать)
  [ ] LLM-as-Judge откалиброван (сравнен с человеком на 10 примерах)
  [ ] Eval запускается автоматически после каждого изменения промпта
  [ ] История eval-ов хранится (чтобы видеть регрессии)
  [ ] Cost per eval известен
```

### Regression Tracking — отслеживание регрессий

После того как eval настроен, важно отслеживать его результаты во времени.

**Зачем:**
- Обновление модели (API или локальной) может изменить поведение — регрессия по качеству
- Изменение промпта, чанкинга или retrieval влияет на итоговый ответ
- Без трекинга регрессия заметна только когда пользователи начинают жаловаться

**Простой подход — JSONL с временными метками:**
```jsonl
{"timestamp": "2026-05-01T10:00:00", "model": "gpt-4o", "accuracy": 0.92, "f1": 0.88, "latency_ms": 1200}
{"timestamp": "2026-05-02T10:00:00", "model": "gpt-4o", "accuracy": 0.89, "f1": 0.85, "latency_ms": 1100}
{"timestamp": "2026-05-03T10:00:00", "model": "gpt-4o-mini", "accuracy": 0.91, "f1": 0.87, "latency_ms": 600}
```

**Дашборд:** визуализируй accuracy, F1, latency по дням/неделям — сразу видно, когда метрика упала.

**Алерты:** автоматическое уведомление (email, Slack, Telegram), когда скользящее среднее accuracy падает ниже порога (например, < 0.85). Это позволяет реагировать до того, как регрессия затронет пользователей.

---



## Итоги

```
Бенчмарки:
  MMLU, GPQA          → знания и рассуждения
  SWE-bench, HumanEval → кодинг
  GAIA, τ-bench        → agentic (tool use)
  Arena Elo            → общее впечатление

Ловушки:
  Data contamination    → проверяй на свежих данных
  Overfitting к формату → тестируй open-ended
  Single metric         → смотри 3+ бенчмарка

Для production:
  Свой eval (golden + LLM-as-Judge) важнее любого бенчмарка
  Smoke tests → golden → LLM-as-Judge → regression tracking
```

---

## Проверь себя

1. Какие три бенчмарка наиболее информативны для оценки coding-способностей модели?
2. Почему Chatbot Arena не измеряет качество кода?
3. Что такое data contamination и как от неё защититься?
4. Из каких трёх уровней состоит production eval?
5. Какие 5 критериев оценки использует LLM-as-Judge?

---

## Ссылки

- [[08-evaluation-security-production]] — базовый модуль по evaluation
- [[07-system-prompts-meta-prompting-guardrails/07-ai-safety]] — safety benchmarks
- [[../../ai-agents/12-quality-evolution/01-agent-evaluation]] — evaluation агентов
- [[../../ai-agents/05-production/05-agent-testing]] — тестирование агентов
