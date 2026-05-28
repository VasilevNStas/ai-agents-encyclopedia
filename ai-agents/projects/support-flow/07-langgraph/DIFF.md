# DIFF: Stage 7 — LangGraph

> Относительно: [[../../06-security/DIFF|Stage 6 — Security]]
> Модуль курса: [[../../../16-langgraph-track/01-graph-basics]]

## Что изменилось

### Режим исполнения: ReAct → State Graph

| Аспект | До (ReAct Loop) | После (LangGraph) |
|--------|----------------|-------------------|
| Управление | `while True` + if/else | `StateGraph` с явными узлами и рёбрами |
| Состояние | Локальные переменные | `TypedDict` (явная схема) |
| Маршрутизация | `if msg.tool_calls:` | `add_conditional_edges()` |
| Тестирование | Интеграционное | Поузловое (каждый node — функция) |
| Streaming | Нет | `stream()` с событиями на каждом шаге |
| HITL | Самописный | `interrupt()` примитив |
| Persistence | Нет | Плагин `Checkpointer` |
| Инструменты | Прямой вызов функций | `ToolNode` с роутингом |

### Граф

```
[START]
   │
   ▼
classify_node ──[escalate]──► escalate_node ──► respond_node
   │                                  ▲
   ▼                                  │
guardrail_node ──[block]──────────────┘
   │
   ▼
rag_search_node ──(если нужно)──► llm_call_node
                                      │
                                 ┌────┴────┐
                                 ▼         ▼
                           tool_execute  output_guardrail
                                 │         │
                                 └────┬────┘
                                      ▼
                                 respond_node ──► [END]
```

### Новые компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| `AgentState` | `langgraph_agent.py` | TypedDict с messages, session_id, cost, classification, guardrail_result, rag_results, llm_output, tool_result, escalation, final_response |
| `SupportFlowGraph` | `langgraph_agent.py` | Компилированный граф с `invoke()` и `stream()` |
| `LangGraphRunner` | `agent.py` | Обёртка с CLI, поддержка `/stream` |
| `compare_with_react()` | `langgraph_agent.py` | Сравнение двух парадигм |

## Ключевые концепты

- **StateGraph**: явные узлы (nodes), явные рёбра (edges), conditional routing
- **Checkpointing**: сохранение состояния между шагами (восстановление после сбоя)
- **Streaming**: клиент получает события по мере выполнения
- **HITL**: возможность остановить граф, запросить подтверждение, продолжить

## Как запустить

```bash
# Полный прогон
python agent.py "нужен возврат денег за подписку"

# С показом шагов
python agent.py --stream "не работает пароль"

# Сравнение парадигм
python agent.py --compare

# Interactive
python agent.py
# Далее: /stream для включения пошагового режима
```

## Финальный этап

SupportFlow прошёл путь от простого ReAct-цикла (Stage 1) до production-ready графа состояний (Stage 7). Каждый этап добавлял архитектурный слой:

```
Stage 1: Core ReAct          — LLM + tools + function calling
Stage 2: Memory & RAG        — трёхслойная память + RAG pipeline
Stage 3: Production          — guardrails + budget + metrics
Stage 4: Multi-Agent         — supervisor + specialists
Stage 5: Cost Optimization   — model router + cost tracking
Stage 6: Security            — audit trail + RBAC + PII
Stage 7: LangGraph           — state graph + streaming + checkpointing
```

Эта архитектура может быть развёрнута через `../../src/` (FastAPI + Docker + K8s).
