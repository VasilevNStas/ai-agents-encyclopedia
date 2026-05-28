---
created: 2026-05-09
tags: [course/production, observability, debugging]
status: active
---

# Урок 17: Observability — как понять, что делает агент

> [!quote] Ключевая идея
> Агент — это чёрный ящик. LLM получила запрос, вызвала инструменты, вернула ответ. Но **почему** она сделала именно так? Observability — это способ заглянуть внутрь чёрного ящика.

---

## Проблема: агент не объясняет свои действия

LLM может «рассуждать вслух» (Thought), но:

- Thought может быть неполным или неверным
- LLM может «забыть» объяснить ключевое решение
- В длинном цикле теряется, почему был сделан конкретный шаг

**Без observability ты не узнаешь, почему агент:**

- Удалил файл
- Не заметил очевидный баг
- Зациклился на одном шаге
- Сжёг $100 токенов за 2 минуты

---

## Что нужно логировать

Каждый шаг агента:

```python
@dataclass
class AgentStep:
    step_number: int
    timestamp: str
    thought: str               # что агент «думал»
    action: str                # какой инструмент вызвал
    action_args: dict          # с какими аргументами
    observation: str           # что вернул инструмент
    token_cost: float          # сколько стоило этот шаг
    duration_ms: int           # сколько занял
    guardrail_action: str      # block / confirm / allow
```

```python
class AgentLogger:
    def __init__(self):
        self.steps: list[AgentStep] = []
        self.total_cost = 0.0

    def log_step(self, step: AgentStep):
        self.steps.append(step)
        self.total_cost += step.token_cost

        # Вывод в реальном времени
        print(f"[{step.step_number}] {step.action} → {step.duration_ms}ms (${step.token_cost:.4f})")

    def summary(self) -> str:
        """Итоговый отчёт по сессии."""
        total_steps = len(self.steps)
        total_duration = sum(s.duration_ms for s in self.steps)
        tool_calls = Counter(s.action for s in self.steps)

        return f"""
Session Summary
═══════════════
Steps:      {total_steps}
Duration:   {total_duration / 1000:.1f}s
Cost:       ${self.total_cost:.4f}

Tool Calls:
{tool_calls.most_common()}

Guardrails:
{sum(1 for s in self.steps if s.guardrail_action == 'block')} blocked
{sum(1 for s in self.steps if s.guardrail_action == 'confirm')} confirmed
"""
```

---

## Трассировка (Traces)

Трассировка — это **полная история** одной сессии агента:

```json
{
  "session_id": "sess_abc123",
  "task": "find bug in auth.py",
  "model": "deepseek-reasoner",
  "total_cost": 0.042,
  "total_duration_ms": 32000,
  "steps": [
    {
      "step": 1,
      "thought": "need to find auth.py first",
      "action": "glob",
      "args": {"pattern": "**/auth.py"},
      "observation": "src/auth/auth.py",
      "cost": 0.002,
      "tokens_in": 1500,
      "tokens_out": 50
    },
    {
      "step": 2,
      "thought": "read the file to understand the bug",
      "action": "read",
      "args": {"path": "src/auth/auth.py"},
      "observation": "def login():...",
      "cost": 0.005,
      "tokens_in": 2000,
      "tokens_out": 100
    }
  ]
}
```

---

## Дебаггинг: что пошло не так

### Проблема 1: Агент зациклился

```python
def detect_loop(steps: list[AgentStep], window: int = 3) -> bool:
    """Детектит повторение одних и тех же действий."""
    recent = steps[-window:]
    if len(recent) < window:
        return False
    actions = [s.action for s in recent]
    return len(set(actions)) == 1  # всё время один инструмент
```

### Проблема 2: Агент сжёг слишком много токенов

```python
def detect_cost_anomaly(logger: AgentLogger, max_cost: float = 0.10) -> bool:
    """Срабатывает, если сессия превысила лимит."""
    return logger.total_cost > max_cost
```

### Проблема 3: LLM игнорирует guardrails

```python
def detect_guardrail_loops(logger: AgentLogger) -> bool:
    """Агент пытается делать заблокированное снова и снова."""
    blocks = [s for s in logger.steps if s.guardrail_action == "block"]
    if len(blocks) >= 3:
        # Агент упёрся — возможно, нужна смена подхода
        return True
    return False
```

---

## Что наблюдать в реальном времени

```python
LIVE_METRICS = """
┌──────────────────────────────────────────────┐
│  Agent Monitor                                │
├──────────────────────────────────────────────┤
│  Steps:      12/50                            │
│  Cost:       $0.042 / $0.50 limit             │
│  Duration:   32s / 120s limit                 │
│  Tools:      grep(5) read(4) write(2) bash(1) │
│  Status:     🟢 Working                       │
└──────────────────────────────────────────────┘
"""
```

---

## Anti-pattern: Логировать всё

```python
# ❌ Каждый символ, каждый токен, каждый чих
log_every_token(model_output)
# через 5 минут — гигабайт логов, ничего не найти

# ✅ Логировать только шаги (Thought → Action → Observation)
# + summary в конце
```

---

## Production Monitoring — инструменты

Observability в уроке 15.2—15.5 — это про **что** наблюдать. А production monitoring — это **чем** наблюдать в реальном проекте. Четыре слоя:

```
┌─────────────────────────────────────┐
│  1. Structured Logging (JSON)        │  ← что произошло
│     → Loki / ELK / Datadog Logs     │
├─────────────────────────────────────┤
│  2. Metrics (Prometheus)             │  ← сколько, как часто, как долго
│     → counters, histograms          │
├─────────────────────────────────────┤
│  3. Dashboards (Grafana)             │  ← визуализация
│     → панели, алерты                │
├─────────────────────────────────────┤
│  4. Distributed Tracing (OpenTelemetry)│  ← кто кого вызвал, где тормозит
│     → Jaeger / Tempo / Datadog APM  │
└─────────────────────────────────────┘
```

### Слой 1: Structured Logging

Вместо текстовых строк — логи в JSON. Каждая строка — машиночитаемый объект.

```python
import json, logging

class AgentJSONFormatter(logging.Formatter):
    """Форматирует логи как JSON-строки для отправки в систему сбора."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "step": getattr(record, "step", None),
            "cost": getattr(record, "cost", None),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        return json.dumps(log_entry, ensure_ascii=False)


logger = logging.getLogger("agent")
handler = logging.StreamHandler()
handler.setFormatter(AgentJSONFormatter())
logger.addHandler(handler)

# Использование
logger.info("agent_step", extra={
    "session_id": "sess_42",
    "step": 3,
    "cost": 0.005,
    "duration_ms": 1200,
})
# → {"timestamp": "2026-05-28T12:00:00", "level": "INFO", "message": "agent_step",
#    "session_id": "sess_42", "step": 3, "cost": 0.005, "duration_ms": 1200}
```

**Куда отправлять:**

| Система | Когда использовать |
|---------|------------------|
| **Loki** (Grafana) | Лёгкая, для стартапов. Бесплатно до 100GB |
| **ELK** (Elasticsearch + Logstash + Kibana) | Тяжёлая аналитика, сложные запросы |
| **Datadog Logs** | SaaS, всё в одном. Дорого, но удобно |
| **AWS CloudWatch** | Если уже на AWS |

```python
# Отправка в Loki через HTTP
import requests

def send_to_loki(log_entry: dict):
    payload = {
        "streams": [{
            "stream": {"service": "agent", "session_id": log_entry["session_id"]},
            "values": [[str(int(time.time() * 1e9)), json.dumps(log_entry)]],
        }]
    }
    requests.post("http://localhost:3100/loki/api/v1/push", json=payload)
```

### Слой 2: Metrics — Prometheus

Prometheus собирает числа и умеет считать: сколько вызовов, сколько ошибок, какие задержки.

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Counter — всегда растёт (количество вызовов)
agent_calls = Counter("agent_calls_total", "Всего вызовов агента", ["model", "status"])

# Histogram — распределение (задержки, стоимость)
agent_latency = Histogram(
    "agent_step_duration_seconds",
    "Длительность шага агента",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)
agent_cost = Histogram(
    "agent_step_cost_usd",
    "Стоимость шага агента",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
)

# Gauge — текущее значение (активные сессии)
active_sessions = Gauge("agent_active_sessions", "Активные сессии агента")


class MonitoredAgent:
    def __init__(self):
        self.logger = AgentLogger()

    def run(self, task: str) -> str:
        active_sessions.inc()
        with agent_latency.time():  # автоматически замеряет время
            result = self._execute(task)
        agent_calls.labels(model="deepseek-chat", status="success").inc()
        active_sessions.dec()
        return result

    def _execute(self, task: str) -> str:
        # симуляция работы
        import time, random
        time.sleep(random.uniform(0.1, 2.0))
        return f"Done: {task}"


# Prometheus HTTP endpoint (скребёт раз в 15 секунд)
start_http_server(8000)  # → http://localhost:8000/metrics
```

Чем отличаются:

| Тип метрики | Что показывает | Пример |
|-------------|---------------|--------|
| **Counter** | Количество событий | `agent_calls_total{status="error"} 42` |
| **Histogram** | Распределение значений | `agent_step_duration_seconds{le="1.0"} 120` |
| **Gauge** | Текущее значение | `agent_active_sessions 5` |

### Слой 3: Dashboards — Grafana

Grafana читает Prometheus (или Loki) и рисует панели. Пример дашборда для агента:

```
┌──────────────────────────────────────────────────────┐
│  [Agent Production Dashboard]                     [1h] │
├──────────────┬───────────────┬──────────────┬───────────┤
│  Calls/min   │  Error Rate   │  P95 Latency │  Cost/h   │
│      120     │     2.3%      │    3.2s      │  $0.42    │
├──────────────┴───────────────┴──────────────┴───────────┤
│                                                          │
│  Agent Steps (last 30 min)      ▂▂▃▄▅▇▅▄▃▂▁             │
│                                                          │
│  Tool Usage Distribution                                 │
│  ┌────────────┬──────────┬──────────┬────────────┐      │
│  │  search    │  read    │  write   │  bash      │      │
│  │  42%       │  28%     │  18%     │  12%       │      │
│  └────────────┴──────────┴──────────┴────────────┘      │
│                                                          │
│  Active Sessions              ▁▁▂▃▅▇▇▆▄▃▂▁              │
└──────────────────────────────────────────────────────────┘
```

**PromQL — язык запросов:**

```promql
# Запросы к Prometheus

# Сколько вызовов в минуту?
rate(agent_calls_total[5m])

# 95-й перцентиль задержки
histogram_quantile(0.95, rate(agent_step_duration_seconds_bucket[5m]))

# Стоимость за час
sum(rate(agent_step_cost_usd_sum[1h]))

# Процент ошибок
rate(agent_calls_total{status="error"}[5m])
/ rate(agent_calls_total[5m]) * 100
```

**Настройка алертов в Grafana:**

```
Alert: Error Rate > 5%
When:  rate(agent_calls_total{status="error"}[5m])
       / rate(agent_calls_total[5m]) * 100 > 5
For:   5 minutes
Action: Slack → #alerts-agent
```

### Слой 4: Distributed Tracing — OpenTelemetry

Когда агентов несколько (multi-agent), нужно знать, какой агент кого вызвал и где тормозит. OpenTelemetry — стандарт для трейсинга.

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Настройка провайдера
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces"))
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


class TracedAgent:
    """Агент с поддержкой распределённой трассировки."""

    async def process(self, task: str, context: dict = None):
        # Создаём span — единицу работы в трейсе
        with tracer.start_as_current_span("agent_process") as span:
            span.set_attribute("task", task)
            span.set_attribute("session_id", context.get("session_id", "unknown"))

            # Шаг 1: думаем
            with tracer.start_as_current_span("think") as think_span:
                thought = await self._think(task)
                think_span.set_attribute("thought_length", len(thought))

            # Шаг 2: вызываем инструмент (может быть другой агент!)
            with tracer.start_as_current_span("tool_call") as tool_span:
                tool_span.set_attribute("tool", "search_files")
                result = await self._call_tool("search_files", pattern="**/*.py")
                tool_span.set_attribute("result_count", len(result))

                # Если результат пришёл от другого агента —
                # его трейс будет связан через trace_id
                tool_span.add_event("tool_completed", {"files": len(result)})

            span.set_attribute("result_length", len(str(result)))
            return result

    async def _think(self, task: str) -> str:
        import random, time
        time.sleep(random.uniform(0.1, 0.5))
        return f"Need to search files related to {task}"

    async def _call_tool(self, name: str, **kwargs) -> list:
        import time
        time.sleep(0.3)
        return ["file1.py", "file2.py"]
```

**Визуализация трейсов (Jaeger / Grafana Tempo):**

```
Trace: agent_process (332ms)
├── think (150ms)
│   └── llm_call (120ms)           ← DeepSeek API
├── tool_call (180ms)
│   ├── search_files (150ms)
│   │   └── fs_readdir (100ms)     ← файловая система
│   └── tool_completed              ← событие
└── format_response (2ms)

Где узкое место: llm_call (120ms из 332ms = 36%)
Что делать: кэшировать повторные запросы к LLM
```

### Сводка инструментов

| Задача | Инструмент | Когда брать |
|--------|-----------|-------------|
| Сбор логов | Loki | Нет денег, маленький проект |
| Сбор логов | Datadog | Есть бюджет, нужно всё в одном |
| Сбор логов | ELK | Нужна сложная аналитика |
| Метрики | Prometheus + Grafana | Стандарт индустрии |
| Трейсинг | OpenTelemetry + Jaeger | Multi-agent системы |
| Трейсинг | OpenTelemetry + Grafana Tempo | Уже есть Grafana |
| Алерты | Grafana Alerting | Бесплатно |
| Алерты | PagerDuty / OpsGenie | Нужны on-call ротации |

---

## Резюме

```
Observability = логировать каждый шаг агента
                + детектить аномалии (циклы, перерасход)
                + показывать живую метрику
                + summary в конце

Production Monitoring (4 слоя):
  1. Structured Logging — JSON → Loki / ELK / Datadog
  2. Metrics — Prometheus (Counter, Histogram, Gauge)
  3. Dashboards — Grafana (PromQL, алерты)
  4. Distributed Tracing — OpenTelemetry + Jaeger / Tempo

Не логировать: каждый токен
Логировать:    Thought → Action → Observation → Cost → Duration
Мониторить:    calls/min, error rate, p95 latency, cost/hour
```

---

## Практическое задание

1. Реализуй класс `AgentLogger` для ReAct-агента. Логируй каждый шаг: `thought`, `action`, `observation`, `cost`, `duration`. Добавь метод `summary()`, который выводит итоговую статистику.

2. Напиши функцию `detect_loop(steps, window=3)`, которая находит зацикливание агента (повторение одного и того же инструмента N раз подряд). Протестируй на синтетических данных.

---

## Проверь себя

1. Какие поля должны быть в логе каждого шага агента?
2. Как детектить зацикливание агента?
3. Почему важно логировать cost на каждом шаге?
4. Чем Counter отличается от Histogram? От Gauge?
5. Что такое PromQL и зачем он нужен?
6. В каком сценарии нужен distributed tracing (OpenTelemetry)?
7. Когда выбрать Loki, а когда Datadog для логов?

---

## Ссылки

- Дальше: [[05-production/03-log-driven-development]]
- Назад: [[05-production/01-guardrails]]
- [[05-production/04-resilience]] — ретраи и circuit breaker для мониторинга
- [Prometheus docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) — PromQL язык запросов
- [Grafana Loki](https://grafana.com/oss/loki/) — сбор логов
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/) — трассировка
