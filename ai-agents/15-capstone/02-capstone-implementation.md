---
created: 2026-05-28
tags: [course/capstone, project, implementation, deployment, testing]
status: active
---

# Урок 52: Capstone — Реализация, Тестирование, Deploy

> [!quote] Ключевая идея
> Архитектура без кода — мечта. Код без тестов — риск. Всё вместе — production.

---

## От ADR к коду

Предположим, твои ADR-решения из урока 51:

| Решение | Выбор |
|---------|-------|
| Паттерн | ReAct (max 3 шага) |
| Топология | Single-agent + Supervisor escalation |
| RAG | RAG 2.0 (query re-write + re-rank) |
| Guardrails | Input sanitizer + Output validator + Budget tracker |
| Модель | GPT-4o-mini (main) + GPT-4o (escalation) |
| Observability | OpenTelemetry → Loki + Grafana |
| Eval | LLM-as-judge на 200 reference тикетов |
| Deploy | Docker Compose → Cloud Run |

Твоя задача: реализовать это. Ниже — каркас системы и чеклист.

---

## Структура проекта

```
support-flow/
├── agent/
│   ├── __init__.py
│   ├── core.py              # ReAct цикл
│   ├── guardrails.py         # Input/Output/Data guardrails
│   ├── router.py             # Model router (pro vs cheap)
│   └── escalation.py         # Supervisor escalation logic
├── rag/
│   ├── __init__.py
│   ├── indexer.py            # Build vector index
│   ├── retriever.py          # Query rewrite + search + re-rank
│   └── knowledge_base.py     # KB management
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── schemas.py            # Request/Response models
│   └── middleware.py          # Auth, rate limit, tracing
├── eval/
│   ├── __init__.py
│   ├── dataset.py            # Reference tickets
│   ├── metrics.py            # Accuracy, relevance, toxicity
│   └── runner.py             # Batch eval
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── cloudrun.yaml
│   └── .env.example
├── tests/
│   ├── test_agent.py
│   ├── test_rag.py
│   ├── test_guardrails.py
│   └── test_api.py
├── monitoring/
│   ├── otel-collector-config.yaml
│   ├── loki-config.yaml
│   └── grafana-dashboard.json
└── requirements.txt
```

---

## Core Agent — ReAct с guardrails

```python
"""core.py — ReAct цикл с guardrails и budget control."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable
import time
import tiktoken


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETE = "complete"
    ESCALATED = "escalated"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class Step:
    thought: str
    action: str
    observation: str
    tokens_used: int
    duration_ms: float


@dataclass
class Session:
    ticket_id: str
    messages: list[dict]
    steps: list[Step]
    total_tokens: int
    total_cost: float
    state: AgentState
    user_feedback: str | None = None


class TokenBudget:
    """Контроль бюджета на сессию."""

    def __init__(self, max_tokens: int = 4000, max_cost: float = 0.05):
        self.max_tokens = max_tokens
        self.max_cost = max_cost

    def check(self, session: Session) -> bool:
        if session.total_tokens > self.max_tokens:
            session.state = AgentState.BUDGET_EXCEEDED
            return False
        if session.total_cost > self.max_cost:
            session.state = AgentState.BUDGET_EXCEEDED
            return False
        return True


class ReActAgent:
    """ReAct цикл с ограничением шагов и бюджетом."""

    def __init__(
        self,
        llm: Any,
        tools: dict[str, Callable],
        guardrails: list[Callable],
        budget: TokenBudget | None = None,
        max_steps: int = 3,
    ):
        self.llm = llm
        self.tools = tools
        self.guardrails = guardrails
        self.budget = budget or TokenBudget()
        self.max_steps = max_steps

    def run(self, ticket: dict) -> Session:
        session = Session(
            ticket_id=ticket["id"],
            messages=[{"role": "system", "content": self._system_prompt()}],
            steps=[],
            total_tokens=0,
            total_cost=0.0,
            state=AgentState.IDLE,
        )

        session.messages.append({
            "role": "user", "content": ticket["message"],
        })

        for _ in range(self.max_steps):
            session.state = AgentState.THINKING
            start = time.time()

            response = self.llm.generate(messages=session.messages)
            tokens = self._count_tokens(response)
            cost = self._estimate_cost(tokens)

            session.total_tokens += tokens
            session.total_cost += cost
            session.state = AgentState.ACTING

            if not self.budget.check(session):
                break

            # Input guardrails
            for guard in self.guardrails:
                if guard(response, stage="input"):
                    session.state = AgentState.ESCALATED
                    break

            action = self._parse_action(response)
            if not action or action["type"] == "final_answer":
                session.state = AgentState.COMPLETE
                break

            observation = self.tools[action["type"]](**action.get("args", {}))
            session.state = AgentState.OBSERVING

            # Output guardrails
            for guard in self.guardrails:
                if guard(observation, stage="output"):
                    session.state = AgentState.ESCALATED
                    break

            duration = (time.time() - start) * 1000
            session.steps.append(Step(
                thought=response,
                action=str(action),
                observation=observation,
                tokens_used=tokens,
                duration_ms=duration,
            ))

            session.messages.append({"role": "assistant", "content": response})
            session.messages.append({"role": "user", "content": str(observation)})

        return session

    def _system_prompt(self) -> str:
        return """Ты — SupportFlow Agent. Отвечай на тикеты клиентов.

Правила:
1. Используй базу знаний (tool: search_kb)
2. Если не уверен — не выдумывай, эскалируй
3. Ответ должен быть на языке запроса
4. Указывай источник информации (URL документа)
5. Если тикет содержит PII — маскируй

Формат ответа (JSON):
{"type": "search_kb" | "final_answer" | "escalate",
 "thought": "...",
 "answer": "..." | "query": "...",
 "confidence": 0.0-1.0}
"""

    def _parse_action(self, response: str) -> dict | None:
        """Парсинг JSON из ответа модели."""
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"type": "final_answer", "answer": response}

    def _count_tokens(self, text: str) -> int:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    def _estimate_cost(self, tokens: int) -> float:
        return tokens * 0.00000015  # gpt-4o-mini: $0.15/M tokens
```

> [!warning] Этот код — основа
> В реальном проекте добавь: retry logic, rate limiting, circuit breaker, кэширование LLM ответов, async обработку.

---

## Guardrails

```python
"""guardrails.py — три слоя защиты."""

import re


class InputGuardrail:
    """Проверка входящего запроса."""

    def __call__(self, text: str, stage: str) -> bool:
        if stage != "input":
            return False
        threats = [
            r"ignore\s+(all\s+)?(previous|prior)",
            r"system\s+prompt",
            r"you\s+are\s+(now|not)",
            r"<[^>]+>.*?</[^>]+>",
            r"sudo|rm\s+-rf|eval\(.*\)",
        ]
        for pattern in threats:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class OutputGuardrail:
    """Проверка ответа перед отправкой пользователю."""

    PII_PATTERNS = [
        r"\b\d{16}\b",          # credit card
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    ]

    def __call__(self, text: str, stage: str) -> bool:
        if stage != "output":
            return False
        for pattern in self.PII_PATTERNS:
            if re.search(pattern, text):
                return True
        return False


class BudgetGuardrail:
    """Проверка превышения лимитов."""

    def __init__(self, max_tokens: int = 4000, max_cost: float = 0.05):
        self.max_tokens = max_tokens
        self.max_cost = max_cost

    def __call__(self, session: Any, stage: str) -> bool:
        if stage != "budget":
            return False
        return (
            session.total_tokens > self.max_tokens
            or session.total_cost > self.max_cost
        )
```

---

## RAG с рерайтингом запроса

```python
"""retriever.py — RAG 2.0: query re-writing + search + re-ranking."""

from typing import Any


class RAGRetriever:
    """Поиск с переформулировкой запроса."""

    def __init__(self, llm: Any, vector_db: Any, top_k: int = 5):
        self.llm = llm
        self.db = vector_db
        self.top_k = top_k

    def retrieve(self, query: str, language: str = "en") -> list[dict]:
        """Поиск с query rewriting."""

        # Шаг 1: Переформулировать запрос под поиск
        rewritten = self.llm.generate(
            f"Переформулируй запрос для поиска в базе знаний. "
            f"Удали лишнее, оставь ключевые термины.\n"
            f"Запрос: {query}\n"
            f"Язык: {language}"
        )

        # Шаг 2: Semantic search
        results = self.db.similarity_search(rewritten, k=self.top_k * 2)

        # Шаг 3: Re-ranking (LLM)
        ranked = self._rerank(query, results)

        return ranked[:self.top_k]

    def _rerank(self, query: str, docs: list[dict]) -> list[dict]:
        prompt = f"Запрос: {query}\n\nДокументы:\n"
        for i, doc in enumerate(docs):
            prompt += f"\n[{i}] {doc['content'][:200]}..."
        prompt += "\n\nОтранжируй документы по релевантности. Ответь номерами через запятую."

        response = self.llm.generate(prompt)
        indices = [int(i) for i in response.split(",") if i.strip().isdigit()]
        return [docs[i] for i in indices if i < len(docs)]
```

---

## Тесты

```python
"""tests/test_agent.py"""

import pytest
from agent.core import ReActAgent, Session, AgentState


class MockLLM:
    def generate(self, messages, **kwargs):
        return '{"type": "final_answer", "thought": "ok", "answer": "Hello"}'

    async def generate_async(self, messages, **kwargs):
        return self.generate(messages, **kwargs)


class TestReActAgent:
    @pytest.fixture
    def agent(self):
        return ReActAgent(
            llm=MockLLM(),
            tools={"search_kb": lambda **_: "doc result"},
            guardrails=[],
        )

    def test_returns_session(self, agent):
        ticket = {"id": "T-001", "message": "How to reset password?"}
        result = agent.run(ticket)
        assert isinstance(result, Session)
        assert result.ticket_id == "T-001"

    def test_budget_exceeded(self, agent):
        agent.budget.max_tokens = 1
        ticket = {"id": "T-002", "message": "Test"}
        result = agent.run(ticket)
        assert result.state == AgentState.BUDGET_EXCEEDED
```

```python
"""tests/test_rag.py"""

import pytest
from rag.retriever import RAGRetriever


class TestRAGRetriever:
    @pytest.fixture
    def retriever(self):
        return RAGRetriever(
            llm=MockLLM(),
            vector_db=MockVectorDB(),
        )

    def test_retrieve_returns_list(self, retriever):
        results = retriever.retrieve("How to reset password?")
        assert isinstance(results, list)

    def test_retrieve_respects_top_k(self, retriever):
        results = retriever.retrieve("test", top_k=3)
        assert len(results) <= 3
```

---

## Deployment Checklist

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```yaml
# docker-compose.yml
version: "3.9"
services:
  agent:
    build: .
    ports: ["8080:8080"]
    env_file: .env
    depends_on:
      - qdrant
      - redis
    deploy:
      resources:
        limits: {cpus: "1", memory: "512M"}

  qdrant:
    image: qdrant/qdrant:latest
    volumes: ["./data/qdrant:/storage"]

  redis:
    image: redis:7-alpine
```

### Cloud Run

```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: support-flow-agent
spec:
  template:
    spec:
      containers:
        - image: gcr.io/support-flow/agent
          env:
            - name: MODEL_API_KEY
              valueFrom:
                secretKeyRef: {name: api-keys, key: openai}
          resources:
            limits: {memory: "512Mi", cpu: "1"}
          startupProbe:
            tcpSocket: {port: 8080}
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/

  deploy:
    needs: test
    steps:
      - run: |
          gcloud builds submit --tag gcr.io/${{ vars.PROJECT }}/agent
          gcloud run deploy support-flow-agent \
            --image gcr.io/${{ vars.PROJECT }}/agent \
            --platform managed
```

---

## Monitoring

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols: {grpc: {endpoint: 0.0.0.0:4317}}
exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
service:
  pipelines:
    logs: {receivers: [otlp], exporters: [loki]}
```

### Ключевые метрики для Grafana

| Метрика | Источник | Alert |
|---------|----------|-------|
| `agent_response_time_ms` | OpenTelemetry | > 3000ms |
| `agent_cost_per_session` | Application | > $0.05 |
| `agent_escalation_rate` | Application | > 30% |
| `rag_recall@5` | Eval pipeline | < 0.7 |
| `user_feedback_negative` | API | > 10%/day |

---

## Финальный чеклист

До релиза:

- [ ] Все unit-тесты проходят
- [ ] Eval dataset (200 тикетов) — accuracy > 80%
- [ ] Guardrails не пропускают PII
- [ ] Budget control работает
- [ ] Rate limiting включён
- [ ] Docker image собирается
- [ ] CI/CD пайплайн зелёный
- [ ] OpenTelemetry экспортирует логи
- [ ] Dashboard построена
- [ ] Load test: 100 concurrent users, p95 < 3s
- [ ] Security scan (SAST) пройден
- [ ] Rollback plan готов

После релиза:

- [ ] Мониторинг 24h
- [ ] Сбор user feedback
- [ ] Daily cost report
- [ ] Weekly eval run
- [ ] Bi-weekly guardrails update

---

## Практическое задание

Реализуй критический компонент SupportFlow — систему guardrails и budget control:

1. **InputGuardrail**: заблокируй промпт-инъекции (detect `ignore system`, `sudo`, `rm -rf`, HTML-теги)
2. **OutputGuardrail**: проверь, что ответ не содержит PII (email, телефон, кредитные карты через regex)
3. **BudgetGuardrail**: останови агента если превышено 3 шага ReAct цикла или $0.05 на сессию
4. Напиши тесты: 3 теста на input guardrail, 3 на output, 2 на budget
5. Собери всё в `guardrails.py` и импортируй в `core.py` как список `guardrails=[InputGuardrail(), OutputGuardrail(), BudgetGuardrail()]`

Требования: guardrails должны быть callable-объектами, которые можно передать в `ReActAgent` из урока. Тесты — pytest без внешних зависимостей.

---

## Проверь себя

1. Какие 3 guardrails критичны для SupportFlow?
2. Почему в production нужен rate limiting и budget control?
3. Что будет, если RAG retriever вернёт пустой результат?
4. Как понять, что агент деградирует, до жалоб пользователей?
5. Какой deployment strategy выбрать: blue-green или canary?

---

## Резюме

```
Capstone Part 2: реализовать SupportFlow

Что делаем:
  1. ReAct цикл с guardrails и бюджетом
  2. RAG 2.0 с рерайтингом и реранкингом
  3. API (FastAPI)
  4. Тесты (unit + integration)
  5. Docker + Cloud Run
  6. CI/CD
  7. Monitoring + Alerts

Результат: работающий агент в production
Критерий: ты защитил каждое решение ADR кодом
```

---

## Ссылки

- [[15-capstone/01-capstone-design]] — ADR и архитектура
- [[05-production/05-agent-testing]] — стратегия тестирования
- [[05-production/03-log-driven-development]] — LDD для debugging
- [[13-ecosystem-operations/02-agent-lifecycle]] — Docker + K8s lifecycle
- [[12-quality-evolution/01-agent-evaluation]] — eval пайплайн
- [[12-quality-evolution/02-ab-testing]] — A/B тестирование агента
- [[13-ecosystem-operations/01-agent-frameworks]] — фреймворки
