---
created: 2026-05-28
tags: [course/production, observability, langfuse, practice, architect]
status: active
---

# Урок 17b: Observability на практике — LangFuse + OpenTelemetry

> [!quote] Ключевая идея
> В уроке 17 (теория observability) мы разобрали, что логировать. Теперь — **как это подключить**. LangFuse — open-source платформа для LLM-observability: трейсы, метрики, cost tracking, eval. OpenTelemetry — промышленный стандарт сбора телеметрии. Вместе они дают полную картину работы агента.

---

## 1. LangFuse: трейсинг агента

```bash
pip install langfuse
```

```python
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse(
    secret_key="sk-lf-...",
    public_key="pk-lf-...",
    host="https://cloud.langfuse.com",  # или self-hosted
)


# === Трейсинг всего цикла агента ===
@observe(as_type="agent")
def agent_cycle(user_input: str) -> str:
    """Полный цикл агента с трейсингом."""

    # Шаг 1: думаем
    thought = think_step(user_input)
    langfuse_context.update_current_observation(
        name="think",
        input=user_input,
        output=thought,
    )

    # Шаг 2: вызываем инструмент
    tool_result = call_tool(thought)
    langfuse_context.update_current_observation(
        name="call_tool",
        input=thought,
        output=tool_result,
        metadata={"tool": "search", "latency_ms": 150},
    )

    # Шаг 3: финальный ответ
    final = respond(tool_result)
    langfuse_context.update_current_observation(
        name="respond",
        input=tool_result,
        output=final,
    )

    return final
```

### Что даёт LangFuse

```
Trace: agent_cycle (session="user_42")
  ├── Observation: think
  │     ├── input: "Как сбросить пароль?"
  │     ├── output: "Нужно найти инструкцию в базе знаний"
  │     └── tokens: 156 input, 23 output
  ├── Observation: call_tool
  │     ├── input: "search('password reset guide')"
  │     ├── output: "Password reset steps: 1. Settings..."
  │     ├── tool: "search"
  │     └── latency: 150ms
  └── Observation: respond
        ├── input: "Password reset steps: 1..."
        └── output: "Чтобы сбросить пароль, перейдите в..."
```

---

## 2. LangFuse + LangGraph: интеграция

```python
from langfuse.callback import CallbackHandler
from langgraph.graph import StateGraph

# Callback-обработчик для LangGraph
langfuse_handler = CallbackHandler(
    secret_key="sk-lf-...",
    public_key="pk-lf-...",
    host="https://cloud.langfuse.com",
)

# Использование с любым графом
config = {
    "configurable": {"thread_id": "session_42"},
    "callbacks": [langfuse_handler],  # ← трейсинг всех шагов
}

for event in graph.stream(inputs, config, stream_mode="updates"):
    # Каждый узел графа автоматически трейсится
    pass
```

---

## 3. Кастомные метрики в LangFuse

```python
class MetricsCollector:
    """Собирает кастомные метрики агента."""

    def __init__(self):
        self.steps = []
        self.start_time = None

    def begin_session(self):
        self.start_time = time.time()

    def end_session(self, agent_state: dict) -> dict:
        """Формирует метрики по завершении сессии."""
        duration = time.time() - self.start_time

        metrics = {
            "duration_ms": duration * 1000,
            "total_tokens": sum(s.get("tokens", 0) for s in self.steps),
            "total_cost": sum(s.get("cost", 0) for s in self.steps),
            "tool_calls": len([s for s in self.steps if s["type"] == "tool"]),
            "llm_calls": len([s for s in self.steps if s["type"] == "llm"]),
            "guardrail_triggers": agent_state.get("guardrail_count", 0),
            "max_confidence": max(
                (s.get("confidence", 0) for s in self.steps), default=0
            ),
            "iterations": len(self.steps),
        }

        # Отправка в LangFuse
        langfuse.score(
            trace_id=agent_state.get("trace_id"),
            name="agent_session_metrics",
            value=metrics,
        )

        return metrics
```

---

## 4. OpenTelemetry: стандартный сбор метрик

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Настройка метрик
reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://otel-collector:4317")
)
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("agent-monitoring")

# LLM-метрики
llm_requests = meter.create_counter(
    name="llm.requests.total",
    description="Total LLM requests",
    unit="1",
)
llm_latency = meter.create_histogram(
    name="llm.latency",
    description="LLM request latency",
    unit="ms",
)
llm_tokens = meter.create_counter(
    name="llm.tokens.total",
    description="Total tokens used",
    unit="1",
)
agent_cost = meter.create_counter(
    name="agent.cost.total",
    description="Total cost in USD",
    unit="USD",
)


class OTelMetrics:
    """OpenTelemetry метрики для агента."""

    def record_llm_call(self, latency_ms: float, tokens: int, cost: float, model: str):
        llm_requests.add(1, {"model": model, "environment": os.getenv("ENV", "dev")})
        llm_latency.record(latency_ms, {"model": model})
        llm_tokens.add(tokens, {"model": model, "type": "total"})
        agent_cost.add(cost, {"model": model})

    def record_tool_call(self, tool_name: str, latency_ms: float, success: bool):
        tool_calls = meter.create_counter(
            f"agent.tool.{tool_name}.calls",
            description=f"Tool calls for {tool_name}",
        )
        tool_calls.add(1, {"success": str(success)})

    def record_guardrail_block(self, guardrail_type: str):
        guardrail_blocks = meter.create_counter(
            "agent.guardrail.blocks",
            description="Guardrail blocks by type",
        )
        guardrail_blocks.add(1, {"type": guardrail_type})
```

---

## 5. Дашборды: Grafana

```json
// grafana-dashboard.json — метрики агента
{
  "panels": [
    {
      "title": "LLM Requests / min",
      "type": "graph",
      "targets": [
        {"expr": "rate(llm_requests_total[5m])", "legendFormat": "{{model}}"}
      ]
    },
    {
      "title": "P95 Latency",
      "type": "graph",
      "targets": [
        {"expr": "histogram_quantile(0.95, rate(llm_latency_bucket[5m]))"}
      ]
    },
    {
      "title": "Cost / hour",
      "type": "graph",
      "targets": [
        {"expr": "rate(agent_cost_total[1h])", "legendFormat": "{{model}}"}
      ]
    },
    {
      "title": "Guardrail Blocks",
      "type": "bar",
      "targets": [
        {"expr": "rate(agent_guardrail_blocks_total[5m])", "legendFormat": "{{type}}"}
      ]
    },
    {
      "title": "Session Quality Score",
      "type": "stat",
      "targets": [
        {"expr": "avg(agent_session_score)"}
      ],
      "thresholds": {"critical": 0.5, "warning": 0.8}
    }
  ],
  "alerts": [
    {
      "name": "High Error Rate",
      "condition": "rate(agent_errors_total[5m]) > 0.05",
      "severity": "critical"
    },
    {
      "name": "Cost Spike",
      "condition": "rate(agent_cost_total[5m]) > 0.01",
      "severity": "warning"
    }
  ]
}
```

---

## 6. Практика: подключи мониторинг к своему агенту

1. Установи LangFuse (pip install langfuse)
2. Создай аккаунт на cloud.langfuse.com (free tier)
3. Оберни ReAct-цикл в `@observe`
4. Запусти агента — увидишь трейсы в дашборде
5. Добавь OpenTelemetry метрики (cost, latency, tokens)
6. Настрой хотя бы один алерт (cost > $0.50 за сессию)

```python
# TODO: Запусти этот код
from langfuse.decorators import observe, langfuse_context


@observe(as_type="agent")
def my_agent(user_input: str):
    response = llm.invoke(user_input)
    langfuse_context.update_current_observation(
        output=response,
        metadata={"model": "claude-sonnet-4.6", "tokens": response.usage}
    )
    return response
```

---

## Резюме

```
Практическая observability:

LangFuse:
  - @observe() — трейсинг любого вызова
  - CallbackHandler — интеграция с LangGraph
  - Scores — кастомные метрики (quality, cost)

OpenTelemetry:
  - Counter / Histogram — стандартные метрики
  - OTLP экспорт — в любой backend
  - Grafana — визуализация и алерты

Production минимум:
  - Трейсинг каждого шага агента
  - Cost per session
  - P95 latency
  - Guardrail blocks
  - Alert на аномалии
```

---

## Проверь себя

1. Что даёт `@observe` декоратор?
2. Как подключить LangFuse к LangGraph?
3. Какие 5 метрик нужно мониторить в production?
4. Настрой Grafana-дашборд для агента: что будет на панелях?
5. Какой алерт спас бы от case study 1 (budget explosion)?

---

## Ссылки

- [[../02-observability]] — теория observability (урок 17)
- [[../../../16-langgraph-track/05-production-streaming]] — LangGraph streaming
- [[../../../assets/monitoring/README]] — monitoring stack (docker-compose + Prometheus + Grafana)
