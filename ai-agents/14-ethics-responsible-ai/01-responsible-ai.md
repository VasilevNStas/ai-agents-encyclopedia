---
created: 2026-05-28
tags: [course/ethics, responsible-ai, governance, transparency, accountability]
status: active
---

# Урок 49: Responsible AI — этика для агентов

> [!quote] Ключевая идея
> Если агент принимает решения — кто за них отвечает? Этичные AI-системы — не опция и не «политика». Это архитектурное требование: прозрачность, подотчётность, человеческий контроль. В 2026 году регуляторы (EU AI Act, US Executive Order) требуют этого по закону.

---

## Почему этика — это архитектура, а не философия

Этичные проблемы в AI-агентах — это не гипотетические сценарии, а конкретные production-инциденты:

```
2024: Агент поддержки банка оформил кредит на мошенника
      → причина: агент не проверил личность (нет guardrails)

2025: Recruiting-агент отсеял 70% кандидаток-женщин
      → причина: исторические данные обучения содержали bias

2025: Медицинский агент рекомендовал неверную дозировку
      → причина: HITL отключён «для скорости»

2026: Agent-deployer удалил production БД
      → причина: нет HITL на опасные действия, нет budget limit
```

Каждый из этих случаев — **архитектурная ошибка**, не этическая. Этика встраивается в архитектуру так же, как guardrails, rate limiting и observability.

---

## Четыре столпа ответственного AI для агентов

```
┌─────────────────────────────────────────────────────┐
│              Responsible AI Agent                     │
├──────────┬──────────┬──────────┬─────────────────────┤
│   Транс- │  Подот-  │  Спра-   │  Прозрачность        │
│   парент-│  чётность│  ведли-  │  и контроль           │
│   ность  │          │  вость   │                      │
├──────────┼──────────┼──────────┼─────────────────────┤
│ user     │ кто      │ bias в   │ user знает, что      │
│ должен   │ отвечает │ данных,  │ говорит с AI,         │
│ понимать,│ за        │ промптах,│ может вмешаться,      │
│ как      │ решение  │ инстру-  │ отменить решение,     │
│ агент    │ агента?  | ментах  │ эскалировать человеку │
│ мыслит   │          │          │                      │
└──────────┴──────────┴──────────┴─────────────────────┘
```

---

## Транспарентность: пользователь знает, с кем говорит

### Disclosure (раскрытие)

```python
class TransparencyLayer:
    """Каждый ответ агента содержит метаданные о том, как он принят."""

    def wrap_response(self, response: str, metadata: dict) -> dict:
        return {
            "content": response,
            "metadata": {
                "generated_by": "ai-agent",
                "model": metadata.get("model", "unknown"),
                "confidence": metadata.get("confidence", None),
                "disclaimer": (
                    "Этот ответ сгенерирован AI-агентом. "
                    "Критические решения проверяйте с человеком."
                ),
                "sources": metadata.get("sources", []),
                "can_escalate": True,
            },
        }

    def add_attribution(self, response: str, sources: list[str]) -> str:
        """Добавляет источники к ответу для проверяемости."""
        if sources:
            response += "\n\n---\n**Источники:**\n"
            for s in sources:
                response += f"- [{s['title']}]({s['url']})\n"
        return response


# Использование
agent = TransparencyLayer()
result = agent.wrap_response(
    response="Ваш заказ будет доставлен 15 мая.",
    metadata={
        "model": "claude-sonnet-4.6",
        "confidence": 0.87,
        "sources": [{"title": "Политика доставки v2.3", "url": "..."}],
    },
)
# → ответ содержит: disclaimer, model, confidence, sources
```

### Audit trail

Каждое решение агента должно быть восстановимо:

```python
@dataclass
class DecisionRecord:
    """Полная запись решения агента для аудита."""
    timestamp: datetime
    session_id: str
    user_id: str
    task: str
    reasoning: str           # CoT агента перед решением
    final_action: str
    alternatives: list[str]  # другие варианты, которые рассматривал агент
    escalation: bool         # был ли HITL
    human_override: bool     # отменил ли человек решение
    model: str
    cost: float
```

**Правило:** если решения агента нельзя восстановить и проверить — агент не готов к production.

---

## Подотчётность: кто отвечает

### Модель ответственности

```python
class AccountabilityMatrix:
    """
    Матрица ответственности: кто за что отвечает в системе с агентом.

    Уровни:
    - L0: Технический сбой (агент не ответил)
    - L1: Неверный ответ в рамках компетенции
    - L2: Вредоносное действие (агент удалил данные)
    - L3: Систематический bias (агент дискриминирует)
    """

    RESPONSIBILITY = {
        "L0": {
            "owner": "engineer",
            "action": "fix code/deploy",
            "automated": True,    # авто-восстановление
        },
        "L1": {
            "owner": "engineer + PM",
            "action": "fix prompt + evals",
            "automated": False,
        },
        "L2": {
            "owner": "engineer + legal",
            "action": "incident response + audit",
            "automated": False,
        },
        "L3": {
            "owner": "legal + exec",
            "action": "policy change + model retraining",
            "automated": False,
        },
    }
```

**Принцип:** человек отвечает за то, что агент делает. Не модель. Не «AI сделал».

### Human-in-the-loop по уровням

```python
HITL_POLICY = {
    "irreversible_actions": {
        "description": "Удаление данных, отправка писем, финансовые операции",
        "requirement": "mandatory_approval",
        "escalation_timeout_s": 300,
    },
    "high_impact": {
        "description": "Медицинские рекомендации, юридические советы",
        "requirement": "review_before_delivery",
        "escalation_timeout_s": 600,
    },
    "low_impact": {
        "description": "Ответы на типовые вопросы, рекомендации контента",
        "requirement": "post_factum_audit",
        "escalation_timeout_s": None,
    },
    "ambiguous": {
        "description": "Агент не уверен в ответе (confidence < threshold)",
        "requirement": "escalate_to_human",
        "escalation_timeout_s": 120,
    },
}
```

---

## Прозрачность принятия решений

### Confidence threshold для эскалации

```python
class ConfidenceEscalator:
    """
    Если агент не уверен — эскалирует человеку.
    """

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def should_escalate(self, response: str, metadata: dict) -> bool:
        confidence = metadata.get("confidence", 1.0)
        if confidence < self.threshold:
            return True

        task_risk = metadata.get("risk_level", "low")
        if task_risk == "high" and confidence < 0.95:
            return True

        return False

    def escalate(self, task: str, response: str, context: dict):
        """Отправляет задачу человеку на рассмотрение."""
        ticket = {
            "task": task,
            "agent_response": response,
            "agent_reasoning": context.get("reasoning", ""),
            "alternatives": context.get("alternatives", []),
            "assigned_to": "human_reviewer",
            "priority": "high" if context.get("risk_level") == "high" else "normal",
            "timeout": 300,
        }
        ticket_queue.push(ticket)
        return {"status": "escalated", "ticket_id": ticket["id"]}
```

### Explainability: почему агент сделал этот выбор

```python
class ExplainableAgent:
    """
    Агент, который может объяснить свои решения.
    """

    def __init__(self):
        self.decision_log: list[dict] = []

    def decide(self, task: str) -> dict:
        # CoT перед решением
        reasoning = llm.invoke(
            f"Task: {task}\n"
            "Before answering, explain what options you considered "
            "and why you chose this one."
        )

        action = llm.invoke(
            f"Task: {task}\n"
            f"Reasoning: {reasoning}\n"
            "Now provide the final answer."
        )

        record = {
            "task": task,
            "reasoning": reasoning.content,
            "action": action.content,
            "timestamp": datetime.now(),
        }
        self.decision_log.append(record)

        return {
            "action": action.content,
            "explanation": reasoning.content,
            "can_override": True,
        }

    def get_explanation(self, task_id: str) -> dict | None:
        """Пользователь может запросить объяснение постфактум."""
        for record in self.decision_log:
            if task_id in record["task"]:
                return {
                    "why": record["reasoning"],
                    "what": record["action"],
                    "when": record["timestamp"],
                }
        return None
```

---

## Регуляторный ландшафт 2026

| Регуляция | Регион | Что требует |
|-----------|--------|-------------|
| **EU AI Act** | EU | Risk classification, transparency, human oversight для high-risk AI |
| **US Executive Order** | USA | Safety testing, watermarking, privacy protection |
| **China AI Regulation** | CN | Content control, algorithm filing, bias prevention |
| **Canada AIDA** | CA | Impact assessment, transparency, accountability |

### Что это значит для архитектора агента

```python
# EU AI Act compliance checklist для агента
EU_AI_ACT_REQUIREMENTS = [
    "user_must_know_they_are_talking_to_ai",      # Art. 50
    "human_oversight_for_high_risk_decisions",     # Art. 14
    "technical_documentation_before_deployment",   # Art. 11
    "automatic_logging_of_all_decisions",          # Art. 12
    "correct_explanation_of_decisions",            # Art. 13
    "bias_detection_and_mitigation",               # Art. 10
    "human_can_override_agent_decision",           # Art. 14
]
```

---

## Anti-patterns

| Anti-pattern | Проблема | Решение |
|-------------|----------|---------|
| «AI сделал, я не в курсе» | Снятие ответственности | Accountability matrix |
| «Пользователь сам догадается, что это AI» | Обман пользователя | Явный disclaimer в каждом ответе |
| «HITL замедляет, отключим» | Неконтролируемые решения | HITL для irreversible + high-risk |
| «Наша модель не может быть biased» | Отрицание проблемы | Bias testing на каждом датасете |
| «Юристы разберутся потом» | Регуляторные риски | EU AI Act compliance с first day |

---

## Резюме

```
Responsible AI Agent = Transparency + Accountability + Fairness + Control

Transparency:
  - User знает, что говорит с AI
  - Каждый ответ — с disclaimer, confidence, sources
  - Audit trail каждого решения

Accountability:
  - Матрица ответственности (L0-L3)
  - HITL по уровням риска
  - Человек отвечает за агента

Control:
  - Confidence threshold → escalation
  - Человек может отменить решение
  - Explainability каждого шага

Compliance:
  - EU AI Act: transparency, logging, human oversight
  - US Executive Order: safety testing, watermarking

Правило: если решение агента нельзя объяснить,
         отменить или проверить — агент не готов к production.
```

---

## Практическое задание

1. Добавь TransparencyLayer к своему агенту (disclaimer + sources)
2. Реализуй ConfidenceEscalator для high-risk действий
3. Напиши audit trail для 3 решений агента
4. Определи матрицу ответственности для своей системы

---

## Проверь себя

1. Какие четыре столпа ответственного AI?
2. Что должно быть в audit trail каждого решения агента?
3. Почему нельзя полагаться только на disclaimer?
4. Как confidence threshold помогает контролировать риски?
5. Что требует EU AI Act от AI-агентов?
6. Какие уровни ответственности (L0-L3) существуют?

---

## Ссылки

- Дальше: [[14-ethics-responsible-ai/02-bias-fairness]]
- [[11-security-safety/01-prompt-injection]] — безопасность как основа
- [[13-ecosystem-operations/02-agent-lifecycle]] — деплой с human oversight
- [[05-production/01-guardrails]] — guardrails для ограничения поведения
- [EU AI Act (2024/1689)](https://eur-lex.europa.eu/eli/reg/2024/1689)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
