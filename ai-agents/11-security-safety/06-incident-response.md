---
created: 2026-05-28
tags: [course/security, incident-response, architect]
status: active
---

# Урок 43d: Incident Response для AI-агентов

> [!quote] Ключевая идея
> Агент — недетерминированная система. Инциденты неизбежны. Разница между «инцидент с ущербом $50K» и «инцидент с ущербом $50» — в скорости обнаружения и реакции. IR plan для агента отличается от обычного софта: нужно уметь откатывать не только код, но и промпты, модель и память.

---

## 1. Сценарии инцидентов

| Сценарий | Пример | Вектор |
|----------|--------|--------|
| **Data breach** | Агент отправил конфиденциальные данные | Output guardrail failure |
| **Cost explosion** | Бесконечный цикл, $10K за час | Budget control failure |
| **Unauthorized action** | Агент удалил production данные | Excessive agency |
| **Model compromise** | Injection в system prompt | Prompt injection |
| **Service degradation** | P95 latency вырос с 2s до 30s | Context poisoning |
| **Reputation damage** | Агент оскорбил пользователя | Safety guardrail failure |

---

## 2. IR Playbook для AI-агентов

### Playbook A: Data Breach

```python
# playbook_data_breach.py
SEVERITY = "critical"
TRIGGERS = [
    "Sensitive data in agent response",
    "API key leak in log",
    "PII in tool call arguments",
]

STEPS = [
    {"order": 1, "action": "isolate_agent",
     "description": "Немедленно заблокировать агента (stop serving)",
     "command": "router.set_active_version('blocked')",
     "owner": "on-call"},

    {"order": 2, "action": "snapshot_context",
     "description": "Сохранить полный контекст агента для расследования",
     "command": "checkpointer.get_state_history(thread_id) + input/output log",
     "owner": "on-call"},

    {"order": 3, "action": "revoke_tokens",
     "description": "Отозвать API-ключи, которые могли быть скомпрометированы",
     "command": "secret_rotator.rotate(service='llm_provider')",
     "owner": "security"},

    {"order": 4, "action": "assess_damage",
     "description": "Определить, какие данные утекли и к кому",
     "command": "audit_log.query(agent_id, timerange)",
     "owner": "security"},

    {"order": 5, "action": "notify",
     "description": "Уведомить affected parties (DPO, legal, user)",
     "command": "incident_notify(severity='critical', stakeholders=[...])",
     "owner": "legal"},
]
```

### Playbook B: Cost Explosion

```python
# playbook_cost_explosion.py
SEVERITY = "high"
TRIGGERS = [
    "Cost per session > $1.00",
    "LLM calls per minute > 100",
    "Daily cost > 10x baseline",
]

STEPS = [
    {"order": 1, "action": "kill_agent_session",
     "description": "Завершить все активные сессии агента",
     "command": "agent_manager.kill_all_sessions(emergency=true)",
     "owner": "on-call",
     "time": "< 30 seconds"},

    {"order": 2, "action": "enable_budget_override",
     "description": "Принудительно включить budget limit для всех агентов",
     "command": "feature_flag.set('budget_control', 'strict')",
     "owner": "on-call"},

    {"order": 3, "action": "analyze_root_cause",
     "description": "Почему budget control не сработал?",
     "command": "logs.query('cost_exceeded', timerange)",
     "owner": "engineering"},

    {"order": 4, "action": "fix_and_deploy",
     "description": "Исправить budget control и раскатать hotfix",
     "owner": "engineering"},

    {"order": 5, "action": "calculate_loss",
     "description": "Подсчитать точные потери",
     "command": "cost_analyzer.calculate(thread_ids)",
     "owner": "finance"},
]
```

---

## 3. Post-mortem шаблон для агентов

```markdown
## Post-mortem: [Название инцидента]

**Дата:** 2026-05-28
**Severity:** Critical / High / Medium
**Длительность:** 2 часа 15 минут
**Влияние:** [описание]

### Хронология

| Время | Событие | Действие |
|-------|---------|----------|
| 14:23 | Первый аномальный запрос | LLM response > 10K токенов |
| 14:45 | Cost alarm сработал | PagerDuty уведомление |
| 14:47 | On-call подтвердил | Начало расследования |
| 15:12 | Root cause найден | Проблема в system prompt |
| 15:30 | Hotfix применён | Rollback на предыдущую версию |
| 16:38 | Мониторинг подтвердил | All clear |

### Root Cause

Агент получил задачу с вложенным контекстом > 50K токенов,
system prompt был «забыт» из-за attention decay → агент начал следовать
инструкциям из пользовательских данных (indirect injection).

### Почему не сработали защиты

- Output guardrail: был настроен только на PII, не на injection
- Budget control: не было ограничения на размер одного ответа
- Consistency check: не было проверки, что агент следует инструкциям

### Действия

| Действие | Owner | Deadline |
|----------|-------|----------|
| Добавить output guardrail на injection | Иванов | 2026-06-04 |
| Добавить limit на max_tokens_per_response | Петров | 2026-06-04 |
| Добавить consistency check после 30K токенов | Сидоров | 2026-06-11 |
| Red team тест на контекстное отравление | Иванов | 2026-06-11 |

### Выводы

1. Никогда не доверять model-provided внимание к инструкциям
2. Budget control должен быть multi-layer (cost + tokens + iterations)
3. Consistency check должен быть после каждого N-ного шага
```

---

## 4. Автоматический детектор инцидентов

```python
class IncidentDetector:
    """Обнаруживает аномалии в поведении агента."""

    ANOMALY_RULES = [
        {
            "name": "cost_spike",
            "metric": "cost_per_minute",
            "threshold": 1.0,  # $/min
            "window": "5m",
            "action": "block_agent",
        },
        {
            "name": "response_size_anomaly",
            "metric": "response_tokens",
            "threshold": 5000,  # токенов
            "window": "1m",
            "action": "warn",
        },
        {
            "name": "tool_call_frequency",
            "metric": "tool_calls_per_session",
            "threshold": 20,
            "window": "session",
            "action": "block_session",
        },
        {
            "name": "latency_degradation",
            "metric": "p95_latency",
            "threshold": 10.0,  # seconds
            "window": "5m",
            "action": "alert",
        },
        {
            "name": "guardrail_trigger_rate",
            "metric": "guardrail_blocks_per_hour",
            "threshold": 50,
            "window": "1h",
            "action": "investigate",
        },
    ]

    def evaluate(self, metrics: dict) -> list[dict]:
        """Проверяет метрики по всем правилам."""
        alerts = []
        for rule in self.ANOMALY_RULES:
            value = metrics.get(rule["metric"], 0)
            if value > rule["threshold"]:
                alerts.append({
                    "rule": rule["name"],
                    "value": value,
                    "threshold": rule["threshold"],
                    "action": rule["action"],
                    "timestamp": datetime.now(),
                })
        return alerts
```

---

## 5. Communication Template

```python
# Шаблон коммуникации при инциденте
INCIDENT_COMMS = {
    "slack": {
        "initial": (
            ":warning: *Agent Incident Detected*\n"
            "Severity: {severity}\n"
            "Agent: {agent_name}\n"
            "Time: {timestamp}\n"
            "Metric: {metric} = {value} (threshold: {threshold})\n"
            "Action taken: {action}\n"
            "Investigation: @on-call"
        ),
        "resolved": (
            ":white_check_mark: *Agent Incident Resolved*\n"
            "Duration: {duration}\n"
            "Root cause: {cause}\n"
            "Fix: {fix}\n"
            "Post-mortem: {link}"
        ),
    },
    "pagerduty": {
        "critical": {
            "urgency": "high",
            "dedup_key": "agent_{agent_name}_{incident_type}",
        },
    },
}
```

---

## Резюме

```
Incident Response для агентов:

Playbooks:
  - Data breach: isolate → snapshot → revoke → assess → notify
  - Cost explosion: kill → budget override → analyze → fix

Post-mortem:
  - Хронология (timeline)
  - Root cause (почему?)
  - Почему не сработали защиты?
  - Действия (action items)

Detection:
  - Anomaly rules (cost, latency, guardrails)
  - Автоматические действия (block, warn, alert)
```

---

## Практическое задание

Симулируй инцидент Cost Explosion и выполни playbook:

1. Создай `MockAgent`, который входит в бесконечный цикл tool calls (например, рекурсивно вызывает `search` и получает всё новые результаты)
2. Настрой `IncidentDetector` с правилами на cost, response_tokens и tool_call_frequency
3. Запусти агента — дождись срабатывания детектора
4. Выполни шаги playbook: kill session → enable budget override → analyze root cause
5. Напиши post-mortem по шаблону из урока (timeline, root cause, почему не сработали защиты, action items)

Требования: детектор срабатывает до превышения бюджета в $1, полный post-mortem с action items.

---

## Проверь себя

1. Чем IR для агента отличается от IR для обычного софта?
2. Какие 5 шагов в playbook для data breach?
3. Что должно быть в post-mortem для агента?
4. Напиши anomaly rule для детекции injection через content analysis.
5. Сколько времени должно занимать isolation агента при critical инциденте?

---

## Ссылки

- [[05-red-teaming]] — предыдущий урок
- [[07-compliance-audit]] — следующий урок
- [[../../../17-case-studies/01-budget-explosion]] — case study: budget explosion
- [[../../../17-case-studies/02-production-db-deletion]] — case study: DB deletion
