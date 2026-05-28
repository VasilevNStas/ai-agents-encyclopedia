> [!success] Status: Implemented
> All Python files for this stage are implemented. See `.py` files in this directory.

# SupportFlow — Этап 6: Security

> После [[../../../11-security-safety/01-prompt-injection|Модуля 11 (Security & Safety)]]

## Что добавлено

- Audit trail (immutable log)
- Permission manager (least privilege)
- Input sanitizer (injection detection)
- PII pseudonymization

## Compliance

- EU AI Act: transparency + explainability
- GDPR: right to access + right to be forgotten
- SOC2: audit trail

## Файлы

- `audit.py` — immutable audit log
- `permissions.py` — RBAC для инструментов
- `sanitizer.py` — защита от injection
