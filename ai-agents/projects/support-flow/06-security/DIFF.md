# DIFF: Stage 6 — Security

> Относительно: [[../../05-cost/DIFF|Stage 5 — Cost Optimization]]
> Модуль курса: [[../../../11-security-safety/01-prompt-injection]]

## Что изменилось

### Добавлено

| Компонент | Описание |
|-----------|----------|
| `SecureAudit` | Immutable audit log с chain-of-hash (каждая запись содержит хеш предыдущей) |
| `PermissionChecker` | RBAC: ADMIN (100), AGENT (75), USER (50), VIEWER (25) |
| `PIISanitizer` | Обнаружение и маскировка email, телефонов, кредиток, API keys |
| `SecureAgent` | Агент с 3 слоями: sanitize input → execute → audit |

### Поток данных

```
User Input (raw)
    │
    ▼
┌──────────────────────┐
│  PIISanitizer        │  ← маскирует email/phone/keys до передачи LLM
│  email → ***         │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  Agent               │  ← LLM не видит PII
│  (clean context)     │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  PIISanitizer        │  ← повторная проверка ответа
│  (output)            │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│  SecureAudit         │  ← immutable запись с chain hash
│  audit_log.jsonl     │
└──────────────────────┘
```

### Audit Chain

```
Record 1: { user, action, prev_hash: "" }
    hash = sha256(record1) → "a1b2..."
Record 2: { user, action, prev_hash: "a1b2..." }
    hash = sha256(record2 + "a1b2...") → "c3d4..."
Record 3: { user, action, prev_hash: "c3d4..." }

→ Если кто-то изменит Record 1, хеши 2 и 3 не сойдутся
```

## Как запустить

```bash
# PII: email будет замаскирован
python agent.py --user ivan "my email is ivan@example.com, help!"

# Без PII
python agent.py "как сбросить пароль?"
```

## Что дальше

[[../../07-langgraph/DIFF|Stage 7 — LangGraph: state graph, checkpointing, streaming]]
