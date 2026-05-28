---
created: 2026-05-28
tags: [course/data, hitl, approval, safety, human-feedback]
status: active
---

# Урок 39: Human-in-the-Loop (HITL)

> [!quote] Ключевая идея
> Агент не должен принимать критичные решения без человека. HITL — это не слабость системы, а защитный механизм. Хороший HITL-дизайн балансирует автоматизацию и контроль: агент работает сам, пока уверен в ответе, и передаёт управление, когда сомневается.

---

## Почему HITL обязателен

Даже самый лучший агент ошибается. В некоторых сценариях цена ошибки слишком высока:

| Сценарий | Последствия без HITL |
|---|---|
| Медицинская диагностика | Неверный диагноз |
| Финансовые транзакции | Потеря денег |
| Юридические документы | Судебные риски |
| Увольнение сотрудника | Репутационный ущерб |
| Публикация контента | Нарушение политик |

> [!warning]
> HITL — это не «кнопка отмены». Это архитектурный паттерн, который проектируется **до** деплоя агента. Если HITL нет в архитектуре — добавить его post-hoc в 10 раз дороже.

---

## Approval workflows: агент предлагает, человек утверждает

Базовый паттерн: агент готовит действие, отправляет его на approval, ждёт решения.

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import uuid

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"

@dataclass
class ApprovalRequest:
    id: str
    agent_name: str
    action: str
    reason: str
    context: dict
    created_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: str = ""


class ApprovalAgent:
    """
    Агент, который не выполняет критичные действия без approval.
    """
    def __init__(self, name: str, approval_timeout: int = 300):
        self.name = name
        self.timeout = approval_timeout
        self._pending: dict[str, ApprovalRequest] = {}

    def propose(self, action: str, reason: str, context: dict = None) -> ApprovalRequest:
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            agent_name=self.name,
            action=action,
            reason=reason,
            context=context or {},
            created_at=datetime.utcnow().isoformat(),
        )
        self._pending[req.id] = req
        print(f"[ApprovalAgent] Запрос {req.id}: {action}")
        print(f"  Причина: {reason}")
        return req

    def approve(self, request_id: str, reviewer: str) -> bool:
        req = self._pending.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.APPROVED
        req.reviewed_by = reviewer
        req.reviewed_at = datetime.utcnow().isoformat()
        print(f"[ApprovalAgent] {request_id} APPROVED by {reviewer}")
        return True

    def reject(self, request_id: str, reviewer: str) -> bool:
        req = self._pending.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.REJECTED
        req.reviewed_by = reviewer
        req.reviewed_at = datetime.utcnow().isoformat()
        print(f"[ApprovalAgent] {request_id} REJECTED by {reviewer}")
        return True

    def wait_for_decision(self, request_id: str, poll_interval: float = 1.0) -> ApprovalRequest:
        """Синхронное ожидание решения (с timeout)."""
        import time
        start = time.time()
        while time.time() - start < self.timeout:
            req = self._pending.get(request_id)
            if req and req.status != ApprovalStatus.PENDING:
                return req
            time.sleep(poll_interval)
        req = self._pending[request_id]
        req.status = ApprovalStatus.TIMEOUT
        return req

    def check_and_execute(self, action: str, reason: str, fn: callable, context: dict = None):
        """Предложить → дождаться → выполнить (если approved)."""
        req = self.propose(action, reason, context)
        print(f"[{self.name}] Ожидание решения...")
        result = self.wait_for_decision(req.id)
        if result.status == ApprovalStatus.APPROVED:
            print(f"[{self.name}] Выполняю: {action}")
            return fn(**result.context)
        else:
            print(f"[{self.name}] Отменено: {result.status.value}")
            return None


# Пример
agent = ApprovalAgent("publisher", approval_timeout=60)

def publish_to_prod(branch: str = "main", force: bool = False):
    print(f"  → Деплой на prod из {branch}, force={force}")
    return {"deployed": True, "branch": branch}

# Симуляция: агент предлагает, человек утверждает
req = agent.propose(
    action="deploy_to_production",
    reason="Релиз v2.1.0 — исправление критического бага в payment",
    context={"branch": "release/v2.1.0", "force": False},
)
# Человек проверяет и утверждает
agent.approve(req.id, reviewer="alice@company.com")

# Альтернатива: через check_and_execute
# agent.check_and_execute(
#     action="deploy_to_production",
#     reason="Релиз v2.1.0",
#     fn=publish_to_prod,
#     context={"branch": "release/v2.1.0"},
# )
```

---

## Confidence thresholds: когда агент решает сам

Агент должен знать, когда он уверен, а когда нет. Confidence threshold — количественная мера этой уверенности.

```python
import random

class ConfidenceRouter:
    """
    Маршрутизирует запросы: агент сам (high confidence) или человек (low confidence).
    """
    def __init__(self, agent_name: str, threshold: float = 0.95):
        self.agent_name = agent_name
        self.threshold = threshold
        self.stats = {"auto": 0, "human": 0, "total": 0}

    def decide(self, task: str, confidence: float, metadata: dict = None) -> dict:
        """
        Возвращает решение: кто выполняет задачу и почему.
        """
        self.stats["total"] += 1
        metadata = metadata or {}

        if confidence >= self.threshold:
            self.stats["auto"] += 1
            return {
                "decision": "auto",
                "handler": self.agent_name,
                "confidence": confidence,
                "reason": f"Уверенность {confidence:.2f} ≥ {self.threshold}",
                "metadata": metadata,
            }

        self.stats["human"] += 1
        return {
            "decision": "escalate",
            "handler": "human",
            "confidence": confidence,
            "reason": f"Уверенность {confidence:.2f} < {self.threshold} — нужен человек",
            "metadata": metadata,
        }

    def report(self) -> dict:
        auto_pct = (self.stats["auto"] / self.stats["total"] * 100) if self.stats["total"] else 0
        return {
            **self.stats,
            "auto_pct": round(auto_pct, 1),
            "threshold": self.threshold,
        }


# Пример
router = ConfidenceRouter("support-agent", threshold=0.90)

def classify_intent(query: str) -> tuple[str, float]:
    """Заглушка: классифицирует намерение и возвращает confidence."""
    intents = {
        "Как вернуть товар?": ("refund", 0.97),
        "У меня не работает сайт": ("tech_support", 0.85),
        "Какой ваш адрес?": ("general", 0.99),
        "Странный баг с оплатой": ("tech_support", 0.65),
    }
    return intents.get(query, ("unknown", 0.5))

for query in ["Как вернуть товар?", "У меня не работает сайт", "Какой ваш адрес?", "Странный баг с оплатой"]:
    intent, confidence = classify_intent(query)
    decision = router.decide(intent, confidence, {"query": query})
    print(f"[{decision['handler']:6s}] {query} (conf={confidence:.2f}) → {decision['reason']}")

print(f"\nИтоги: {router.report()}")
# [auto  ] Как вернуть товар? (conf=0.97) → ...
# [human ] У меня не работает сайт (conf=0.85) → ...
# [auto  ] Какой ваш адрес? (conf=0.99) → ...
# [human ] Странный баг с оплатой (conf=0.65) → ...
```

> [!important]
> Порог уверенности (threshold) — **не константа**. Он зависит от сценария:
> - Медицина: 0.999 (почти никогда не решай сам)
> - Чат-поддержка: 0.9 (большинство вопросов решай сам)
> - Развлечения: 0.7 (ошибка не критична)

---

## Escalation: когда агент передаёт задачу человеку

Escalation — это structured handoff: агент не просто говорит «я не знаю», а передаёт контекст.

```python
class EscalationManager:
    """
    Управляет передачей задач от агента человеку.
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.escalations: list[dict] = []

    def escalate(
        self,
        task: str,
        reason: str,
        context: dict,
        suggested_action: str = "",
        priority: str = "medium",
    ) -> dict:
        """
        Создаёт escalation-тикет с полным контекстом для человека.
        """
        ticket = {
            "id": str(uuid.uuid4()),
            "agent": self.agent_name,
            "task": task,
            "reason": reason,
            "context": context,
            "suggested_action": suggested_action,
            "priority": priority,
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": "",
            "resolution": "",
        }
        self.escalations.append(ticket)
        return ticket

    def resolve(self, ticket_id: str, resolution: str, status: str = "resolved") -> bool:
        for t in self.escalations:
            if t["id"] == ticket_id:
                t["status"] = status
                t["resolution"] = resolution
                t["resolved_at"] = datetime.utcnow().isoformat()
                return True
        return False

    def get_open(self) -> list[dict]:
        return [t for t in self.escalations if t["status"] == "open"]

    def format_for_human(self, ticket_id: str) -> str:
        """Форматирует escalation так, чтобы человек быстро понял суть."""
        ticket = next((t for t in self.escalations if t["id"] == ticket_id), None)
        if not ticket:
            return "Ticket not found"
        return f"""
=== ESCALATION {ticket['id']} ===
Agent:     {ticket['agent']}
Priority:  {ticket['priority']}
Task:      {ticket['task']}
Reason:    {ticket['reason']}
Context:   {ticket['context']}
Suggested: {ticket['suggested_action']}
"""


class EscalationAgent:
    """
    Агент, который умеет эскалировать задачи человеку.
    """
    def __init__(self, name: str, escalation_mgr: EscalationManager):
        self.name = name
        self.escalation = escalation_mgr

    def handle(self, task: str) -> str:
        # Пытается решить задачу
        result = self._try_auto(task)
        if result["success"]:
            return result["response"]

        # Если не может — эскалирует
        ticket = self.escalation.escalate(
            task=task,
            reason=result.get("error", "unknown"),
            context={"attempted_solution": result.get("attempt")},
            suggested_action=result.get("suggested"),
            priority="high" if "payment" in task.lower() else "medium",
        )
        return f"Escalated: {ticket['id']}"

    def _try_auto(self, task: str) -> dict:
        """Пытается выполнить задачу. Заглушка."""
        if "refund" in task.lower():
            return {"success": False, "error": "refund_amount_exceeds_limit", "attempt": "calc_refund"}
        return {"success": True, "response": f"Done: {task}"}


# Пример
mgr = EscalationManager("billing-agent")
agent = EscalationAgent("billing-agent", mgr)

result = agent.handle("Process refund for order #12345: amount $500")
print(result)
# Escalated: <uuid>

result2 = agent.handle("Check order status for #67890")
print(result2)
# Done: Check order status for #67890

# Человек смотрит
print(mgr.format_for_human(mgr.get_open()[0]["id"]))
```

---

## Human handoff: передача контекста

Когда агент передаёт задачу человеку, он должен предоставить:

```python
# Плохой handoff (человек тратит время на выяснение)
handoff_bad = {
    "error": "I can't process this",
    "task": "refund",
}
# Человек: «Почему не можешь? Какой заказ? Сколько?»

# Хороший handoff (человек сразу понимает)
handoff_good = {
    "ticket_id": "esc-20260528-001",
    "agent": "billing-agent-v2",
    "summary": "Refund превышает лимит автоматической обработки",
    "context": {
        "order_id": "ORD-12345",
        "customer": "Alice (alice@example.com)",
        "amount": 500.00,
        "limit": 200.00,
        "payment_method": "visa",
        "reason": "Товар не соответствует описанию",
    },
    "timeline": [
        {"action": "verify_order", "status": "ok", "duration_ms": 120},
        {"action": "check_refund_limit", "status": "failed", "duration_ms": 45},
    ],
    "suggested_action": "Утвердить частичный refund $200 или полный $500 с approval",
    "similar_cases": [
        {"id": "ORD-12000", "resolution": "partial_refund_200"},
        {"id": "ORD-11800", "resolution": "full_refund_after_review"},
    ],
}
```

---

## Anti-patterns

### 1. Alert Fatigue — слишком частые запросы к человеку

```python
# ❌ Агент дёргает человека на каждое действие
class NeedyAgent(ApprovalAgent):
    def do_everything(self, task: str):
        self.check_and_execute(
            f"delete_file: {task}",
            "Нужно approval на всё",
            lambda: os.remove(task),
        )
        self.check_and_execute(
            f"write_file: {task}",
            "Нужно approval на всё",
            lambda: open(task, "w").write("data"),
        )

# Человек за 5 минут получает 50 запросов → начинает жать Approve All
# → approval теряет смысл

# ✅ Агрегировать или повысить threshold
class BalancedAgent(ApprovalAgent):
    def batch_propose(self, actions: list[tuple[str, str, callable]]):
        """Один approval на группу действий."""
        summary = "\n".join([f"- {a[0]}: {a[1]}" for a in actions])
        req = self.propose(
            f"batch: {len(actions)} actions",
            summary,
        )
        decision = self.wait_for_decision(req.id)
        if decision.status == ApprovalStatus.APPROVED:
            for action, reason, fn in actions:
                fn()
```

### 2. Слишком редкие запросы — опасно

```python
# ❌ Агент решает всё сам
agent.autonomous_mode = True  # опасная настройка
agent.transfer("$100000", to="unknown-account")
# Человек узнаёт через час

# ✅ Даже в автономном режиме — логи + post-hoc audit
class AuditableAgent:
    def __init__(self):
        self.audit_log: list[dict] = []

    def execute_with_audit(self, action: str, fn: callable):
        result = fn()
        self.audit_log.append({
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "result": str(result),
        })
        # Отправлять отчёт человеку каждые N действий
        if len(self.audit_log) % 10 == 0:
            self.send_digest()
```

### 3. HITL как чёрный ящик

```python
# ❌ Человек видит только: Approve / Reject — без контекста
req = agent.propose("execute", "...")

# ✅ Человек видит полную картину
req = agent.propose_with_context(
    action="transfer_money",
    reason="Оплата счёта #INV-2026",
    context={
        "invoice": invoices[0].to_dict(),
        "customer_history": customer.get_history(),
        "similar_transactions": get_similar(amount=1500),
        "risk_score": 0.02,
    }
)
```

---

## Проверь себя

1. Какие три порога уверенности (confidence thresholds) ты бы выбрал для: медицинского диагноста, чат-бота поддержки, рекомендательного сервера?
2. Чем escalation отличается от обычного запроса approval? Какой формат handoff позволяет человеку быстро войти в контекст?
3. Что такое alert fatigue? Как его избежать?
4. Какие поля обязательно должны быть в escalation-тикете?
5. Почему HITL нельзя добавить post-hoc? Какие архитектурные последствия?

---

## Практическое задание

Реализуй систему HITL для банковского агента-оператора:

- `TransferAgent` — обрабатывает переводы между счетами
- Если сумма < $1000 и confidence > 0.95 — агент решает сам
- Если сумма $1000-$10000 — нужен approval менеджера
- Если сумма > $10000 — escalation старшему менеджеру
- Каждый перевод логируется в audit trail
- Формат handoff: ticket с информацией об отправителе, получателе, сумме, истории операций, оценке риска

Требования: реализовать `ConfidenceRouter` + `ApprovalAgent` + `EscalationManager` в одной системе. Написать демо с 3-4 транзакциями разного уровня.

---

## Резюме

```
Human-in-the-Loop — три уровня контроля:

1. Confidence threshold (автономия)
   - confidence > threshold → агент решает сам
   - confidence < threshold → человек

2. Approval workflow (утверждение)
   - Агент: propose(action, reason, context)
   - Человек: approve / reject
   - Таймаут: если человек не ответил — reject или fallback

3. Escalation (передача управления)
   - Агент не может решить → создаёт escalation ticket
   - Ticket содержит: summary, context, timeline, suggested action
   - Человек разбирается и закрывает

Правила:
  - Агрегировать запросы (batch approval)
  - Всегда audit log (даже для auto-approved)
  - threshold зависит от сценария
  - handoff должен быть «readable in 10 seconds»
```

---

## Ссылки

- [[10-data-communication/01-data-engineering]] — оценка качества агента
- [[10-data-communication/02-agent-communication]] — коммуникация с человеком
- [[05-production/01-guardrails]] — защитные механизмы до HITL
- [[05-production/02-observability]] — логирование действий агента