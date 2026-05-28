> [!success] Status: Implemented
> All Python files for this stage are implemented. See `.py` files in this directory.

# SupportFlow — Этап 5: Cost Optimization

> После [[../../../08-decision-architecture/01-fine-tuning-rag-prompting|Модуля 8 (Decision Architecture)]]

## Что добавлено

- Model router: Haiku для простых запросов, Sonnet для сложных
- Budget control: $0.50/сессия
- Cost tracking per user/team

## Model Routing Logic

```python
if is_simple_query(query):
    model = "claude-haiku-4.6"   # $0.25/M tok
elif is_complex_query(query):
    model = "claude-sonnet-4.6"  # $3.00/M tok
elif is_escalated():
    model = "claude-opus-4.7"    # $15.00/M tok
```

## Файлы

- `model_router.py` — выбор модели под задачу
- `budget.py` — бюджетный контроллер
