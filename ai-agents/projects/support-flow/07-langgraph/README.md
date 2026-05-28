> [!success] Status: Implemented
> All Python files for this stage are implemented. See `.py` files in this directory.

# SupportFlow — Этап 7: LangGraph Migration

> После [[../../../16-langgraph-track/01-graph-basics|Модуля 16 (LangGraph Deep Track)]]

## Что сделано

Весь агент переписан на LangGraph:
- StateGraph с явными узлами и переходами
- Checkpointing (PostgresSaver)
- Stream mode для UX
- HITL для опасных действий

## Сравнение

| Аспект | До (цикл) | После (граф) |
|--------|-----------|--------------|
| Состояние | Неявное | TypedDict |
| Поток | while True | Явные рёбра |
| Тестирование | Интеграционное | Поузловое |
| Streaming | Нет | stream_mode="messages" |
| HITL | Самописный | interrupt() |
| Persistence | Нет | Checkpointer |

## Файлы

- `langgraph_agent.py` — полный граф SupportFlow
