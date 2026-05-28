> [!success] Status: Implemented
> All Python files for this stage are implemented. See `.py` files in this directory.

# SupportFlow — Этап 3: Production

> После [[../../../05-production/01-guardrails|Модуля 5 (Production)]]

## Что добавлено

- Input/output guardrails (в `src/agent/core.py`)
- Budget control (BudgetController)
- LangFuse observability
- Resilience (retry, fallback)

## Файлы

- `guardrails.py` — настройка guardrails для SupportFlow
- `monitoring.py` — интеграция с LangFuse + OpenTelemetry

## В production

```bash
# Monitoring stack
docker compose -f src/deploy/docker-compose.yml up
```
