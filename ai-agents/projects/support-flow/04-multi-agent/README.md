> [!success] Status: Implemented
> All Python files for this stage are implemented. See `.py` files in this directory.

# SupportFlow — Этап 4: Мультиагент

> После [[../../../04-multi-agent/01-orchestration|Модуля 4 (Мультиагентные системы)]]

## Что добавлено

- Supervisor-агент: распределяет тикеты
- Специалисты: billing, technical, account
- Эскалация: сложные запросы → человек

## Топология

```
[Supervisor] ← тикет
  ├── [Billing Agent] — финансовые вопросы
  ├── [Technical Agent] — технические проблемы
  └── [Account Agent] — управление аккаунтом
         ↓ эскалация
      [Human Support]
```

## Файлы

- `supervisor.py` — маршрутизация запросов
- `specialists.py` — специализированные агенты
