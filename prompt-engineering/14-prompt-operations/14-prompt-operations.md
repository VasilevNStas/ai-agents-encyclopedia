---
module: 14
title: Prompt Operations & Management
tags: [course, operations, management, production, governance]
author: AI-Professor
---

# Модуль 14: Prompt Operations & Management

> [!quote] Ключевая идея
> Хороший промпт — это искусство. **Надёжный промпт в production** — это инженерия.
> Промпты нужно версионировать, тестировать, мониторить и менять управляемо — как любой код.

---

## 1. Prompt Versioning

Промпт — это код. Он меняется, ломается, регрессирует. Без системы версионирования вы не сможете ответить на вопрос «что изменилось и почему».

### Семантическое версионирование

Примени семантическое версионирование (semver) к промптам:

```
MAJOR — ломается структура вывода, меняется поведение
MINOR — добавляются/убираются примеры, меняется порядок инструкций
PATCH — исправляются опечатки, уточняются формулировки
```

Пример версионирования в frontmatter:

```yaml
name: code-review-prompt
version: 2.1.0
updated: 2026-05-28
change: "Добавлены примеры для Python type hints"
reviewed_by: "alice@team"
```

### Prompt Registry

Центральный каталог всех промптов в проекте:

```
prompts/
├── agents/
│   ├── v1.0.0-support-agent.yaml
│   ├── v2.0.0-support-agent.yaml
│   └── v2.1.0-support-agent.yaml
├── tasks/
│   ├── v1.0.0-code-review.yaml
│   └── v1.0.1-code-review.yaml
└── registry.yaml          ← активные версии
```

```yaml
# registry.yaml
active_versions:
  support-agent: v2.1.0
  code-review: v1.0.1
  summarizer: v1.0.0
```

**Правило:** Никогда не меняй промпт на месте. Всегда создавай новую версию. Старая версия остаётся для rollback.

---

## 2. Prompt Testing Pipeline

Промпты должны проходить автоматические проверки перед deployment:

### Уровни тестирования

```
L1: Syntax check       — YAML/JSON валиден, placeholders заполнены
L2: Golden tests       — эталонные ответы не регрессировали
L3: Adversarial tests  — injection не проходит
L4: LLM-as-Judge       — качество не ниже порога
L5: Canary             — 5% трафика, сравнение с baseline
```

### Пример golden теста

```python
GOLDEN_TESTS = [
    {
        "input": "Как сбросить пароль?",
        "checks": [
            "инструкция по сбросу",
            "ссылка на форму",
            "не запрашиваю старый пароль",
        ]
    },
    {
        "input": "Аннулируй заказ №12345",
        "checks": [
            "не_подтверждаю сразу",
            "запрашиваю причину",
        ]
    },
]
```

Прогон golden тестов должен быть частью CI/CD:

```bash
# pre-commit hook или GitHub Action
prompt-test --registry=prompts/registry.yaml --golden=golden.json
```

---

## 3. Prompt Monitoring

Промпт, который работал вчера, может сломаться сегодня — модель обновилась, данные изменились, пользователи нашли новый способ сломать систему.

### Что мониторить

| Метрика | Что измеряет | Как |
|---------|-------------|-----|
| **Task completion** | Доля успешно завершённых задач | User feedback, HITL rate |
| **Latency** | Время генерации | Prometheus / LangFuse |
| **Token cost** | Стоимость на запрос | Cost tracking |
| **Guardrail triggers** | Сколько раз сработали guardrails | Rate per session |
| **User satisfaction** | Оценка пользователя | Thumbs up/down |
| **Drift score** | Отклонение от baseline | LLM-as-Judge по выборке |

### Drift Detection

```python
class PromptDriftDetector:
    def __init__(self, baseline: dict, threshold: float = 0.1):
        self.baseline = baseline  # {"accuracy": 0.95, "latency_ms": 500}
        self.threshold = threshold

    def check(self, current: dict) -> str:
        accuracy_drop = self.baseline["accuracy"] - current["accuracy"]
        latency_increase = current["latency_ms"] - self.baseline["latency_ms"]

        if accuracy_drop > self.threshold:
            return f"Accuracy drop: {accuracy_drop:.2%}"
        if latency_increase > self.baseline["latency_ms"] * 0.5:
            return f"Latency spike: {latency_increase}ms"
        return "ok"
```

**Правило:** При обнаружении drift — автоматический rollback на предыдущую версию.

---

## 4. A/B Testing Prompts

Никогда не деплой новый промпт на 100% трафика сразу.

### Схема раскатки

```
1%   → внутренняя команда (проверка ошибок)
5%   → ранние пользователи (canary)
20%  → расширенное тестирование (сравнение метрик)
50%  → постепенный rollout
100% → полный деплой
```

На каждом этапе сравнивай метрики с контрольной группой (старый промпт):

```python
def ab_test_result(control: dict, experiment: dict) -> dict:
    return {
        "completion_rate": {
            "control": control["completion_rate"],
            "experiment": experiment["completion_rate"],
            "lift": experiment["completion_rate"] / control["completion_rate"] - 1,
        },
        "avg_cost": {
            "control": control["avg_cost"],
            "experiment": experiment["avg_cost"],
            "change": experiment["avg_cost"] / control["avg_cost"] - 1,
        },
    }
```

### Критерии отката

| Метрика | Порог | Действие |
|---------|-------|----------|
| Completion rate | < контрольной на 3% | Немедленный rollback |
| Latency p95 | > 2x от контроля | Rollback |
| Guardrail triggers | > 2x от контроля | Расследование |
| User satisfaction | < контроля на 0.5 | Rollback |

---

## 5. Prompt Governance

Промпты — это лицо продукта. Они определяют, как система общается с пользователями. Без governance каждый инженер пишет «как удобно».

### Роли и ответственность

| Роль | Обязанности |
|------|-------------|
| **Prompt Engineer** | Пишет и тестирует промпты |
| **Domain Expert** | Проверяет фактологическую точность |
| **Reviewer** | Проверяет безопасность, tone, compliance |
| **Product Owner** | Утверждает изменения в production |
| **Compliance Officer** | Проверяет регуляторные требования |

### Процесс изменения промпта

```
[Prompt Engineer] → Draft → [Domain Expert] → Review →
  [Reviewer] → Security check → [PO] → Approve →
    [CI/CD] → Canary → [Metrics OK] → Full deploy
```

### Audit Trail

Каждое изменение промпта должно логироваться:

```json
{
  "prompt_id": "support-agent",
  "version": "2.1.0",
  "changed_by": "ivan@team",
  "approved_by": "alice@team",
  "timestamp": "2026-05-28T10:30:00Z",
  "change_summary": "Added few-shot examples for refund requests",
  "golden_passed": true,
  "canary_rollout": "5% → 100% in 2h",
  "metrics_before": {"completion": 0.87, "latency_ms": 480},
  "metrics_after": {"completion": 0.92, "latency_ms": 510}
}
```

---

## 6. Инструменты и экосистема

### Prompt Management Platforms

| Инструмент | Назначение |
|-----------|-----------|
| **LangFuse** | Мониторинг, трассировка, cost tracking |
| **LangSmith** | Тестирование, A/B тесты, feedback |
| **PromptLayer** | Версионирование, логирование |
| **Agenta** | Open-source платформа управления промптами |
| **Weights & Biases Prompts** | Эксперименты, сравнение |

### Минимальный production-стек

```
LangFuse (мониторинг) + GitHub (версионирование) +
  GitHub Actions (CI/CD) + Canary (5% → 100%) +
    Golden tests (pre-commit) + LLM-as-Judge (post-deploy)
```

---

## Практическое задание

### Задание 1: Prompt Registry

Создай структуру директорий для prompt registry с тремя промптами (support-agent, code-review, summarizer) в двух версиях каждый. Напиши `registry.yaml`.

### Задание 2: CI/CD Pipeline

Напиши GitHub Actions workflow (YAML), который:
1. Прогоняет golden тесты на каждый PR
2. При merge в main — деплоит на canary (5%)
3. Если метрики в норме через 1 час — деплоит на 100%

### Задание 3: A/B Test

Придумай эксперимент: старый промпт (completion 87%) vs новый (ожидание 92%). Опиши:
- Размер выборки для статистической значимости
- Критерии остановки эксперимента
- План rollback если что-то пошло не так

---

## Проверь себя

1. Какие три уровня семантического версионирования применимы к промптам?
2. Из каких пяти уровней состоит prompt testing pipeline?
3. Какие метрики нужно мониторить в production?
4. Как устроена canary-раскатка промптов (проценты, этапы)?
5. Какие роли участвуют в prompt governance?

---

## Ссылки

- [[09-architectural-patterns]] — архитектурные паттерны для промптов
- [[15-evals-benchmarks]] — как измерять качество промптов
- [[08-evaluation-security-production]] — evaluation checklist
- [[07-system-prompts-meta-prompting-guardrails]] — system prompts & guardrails
- [[index|Главная]]
- [[../../../ai-agents/12-quality-evolution/02-ab-testing|ai-agents: A/B тестирование]] — A/B эксперименты
- [[../../../ai-agents/05-production/02-observability|ai-agents: Observability]] — мониторинг агентов
