---
created: 2026-05-28
tags: [course/ecosystem, lifecycle, deploy, rollback, canary, versioning]
status: active
---

# Урок 47: Agent Lifecycle — деплой, canary, rollback

> [!quote] Ключевая идея
> Деплой агента — это не «залил новый код и перезапустил». Агент недетерминирован: новый промпт может улучшить 90% сценариев и сломать 10%. Без canary-раскатки, автоматического rollback и версионирования ты узнаешь о проблеме от пользователей. Lifecycle management — это release engineering для недетерминированных систем.

---

## Чем агент сложнее обычного софта

| Аспект | Обычный софт | AI-агент |
|--------|-------------|----------|
| Детерминизм | Да (один код = один результат) | Нет (тот же промпт → разный ответ) |
| Причина сбоя | Баг в коде | Баг в промпте, модели, данных |
| Тестирование | Unit / integration тесты | Evals + LLM-as-Judge |
| Rollback | Переключить версию | Semantic cache хранит старые ответы |
| Мониторинг | HTTP 200/500, latency | Completion rate, hallucination rate |

```python
# Разница в подходе к релизам
SOFTWARE_RELEASE = "проверил diff → запустил тесты → задеплоил"
AGENT_RELEASE = "запустил evals → canary 1% → 24h → 10% → 24h → 50% → 12h → 100%"
```

---

## Что версионировать

Агент — это не только код. В релизный артефакт входят **пять компонентов**:

```yaml
# agent-manifest.yaml — релизный манифест
version: 2.1.0
created: 2026-05-28

components:
  prompts:                       # Системный промпт, все инструкции
    system: "prompts/v2.1/system.md"
    tools: "prompts/v2.1/tools.md"

  tool_definitions:              # Схемы инструментов
    search: "tools/search.json"
    database: "tools/database.json"

  model:                         # Зафиксированная модель (не "latest"!)
    provider: anthropic
    model_id: claude-sonnet-4.6
    temperature: 0.3

  memory_schema:                 # Структура памяти агента
    short_term: "memory/st.json"
    long_term: "memory/lt.json"

  configuration:                 # Все параметры
    max_tokens: 4096
    timeout_s: 30
    retry_policy: "exponential_backoff"

rollout:
  strategy: canary
  stages:
    - { traffic: 1,  duration: "30m" }
    - { traffic: 10, duration: "2h"  }
    - { traffic: 50, duration: "6h"  }
    - { traffic: 100 }
  guardrails:
    task_success_rate: { min: 0.97 }
    p95_latency_ms:    { max: 8000 }
    cost_delta:        { max: 0.15 }
  auto_rollback_on_failure: true
```

> [!warning] Никогда не используй "latest" модель
> `model: gpt-5.4-latest` — сегодня GPT-5.4, завтра GPT-5.5. Модель сменилась, поведение изменилось, ты не знаешь почему. Всегда фиксируй версию: `gpt-5.4-2026-05-15`.

---

## Стратегии деплоя

### Shadow deployment (zero user impact)

Запросы идут к **двум** версиям: production (отвечает пользователю) и candidate (только логируем). Сравниваем ответы, не влияя на пользователя.

```
User → Production Agent → response (user sees this)
     → Candidate Agent  → log only (we see this)
```

```python
class ShadowDeployer:
    """
    Запускает candidate-версию «в тени» production.
    Сравнивает ответы, не влияя на пользователей.
    """
    def __init__(self, production, candidate):
        self.prod = production
        self.candidate = candidate
        self.comparisons = []

    async def handle(self, request):
        prod_response = await self.prod.run(request)
        cand_response = await self.candidate.run(request)

        self.comparisons.append({
            "request": request,
            "prod": prod_response,
            "candidate": cand_response,
            "match": prod_response == cand_response,
            "score": self._evaluate(prod_response, cand_response),
        })

        return prod_response  # пользователь видит только production

    def report(self) -> dict:
        total = len(self.comparisons)
        matches = sum(1 for c in self.comparisons if c["match"])
        return {
            "total": total,
            "identical": matches,
            "different": total - matches,
            "avg_eval_score": sum(c["score"] for c in self.comparisons) / total,
        }
```

**Длительность:** 24-72 часа. Стоимость: ~2x (два вызова LLM на каждый запрос).

### Canary deployment

Новая версия получает 1-5% реального трафика. Если метрики стабильны — доля растёт.

```python
class CanaryDeployer:
    """
    Поэтапная раскатка с автоматической проверкой метрик на каждом шаге.
    """

    STAGES = [
        {"traffic_pct": 1,  "duration_h": 24, "eval": "per_rubric_match"},
        {"traffic_pct": 10, "duration_h": 24, "eval": "statistical_significance"},
        {"traffic_pct": 25, "duration_h": 12, "eval": "metrics_vs_baseline"},
        {"traffic_pct": 50, "duration_h": 12, "eval": "full_guardrails"},
        {"traffic_pct": 100, "duration_h": 72, "eval": "stability_window"},
    ]

    def __init__(self, metrics_client):
        self.metrics = metrics_client
        self.current_stage = 0

    async def promote(self, candidate_version: str):
        """Проводит canary-раскатку с авто-откатом."""
        for stage in self.STAGES:
            print(f"Stage {stage['traffic_pct']}% — {stage['duration_h']}h")
            self._route_traffic(candidate_version, stage["traffic_pct"])

            await asyncio.sleep(stage["duration_h"] * 3600)

            if not self._check_metrics(stage):
                await self._rollback(candidate_version)
                return False

        print(f"Full rollout: {candidate_version}")
        return True

    def _check_metrics(self, stage) -> bool:
        """Проверяет метрики за время этапа."""
        metrics = self.metrics.query(
            window_h=stage["duration_h"],
            version="candidate",
        )
        return (
            metrics["task_success_rate"] >= 0.97
            and metrics["p95_latency_ms"] <= 8000
            and metrics["cost_delta"] <= 0.15
        )

    async def _rollback(self, version: str):
        """Автоматический откат — переключает трафик на stable."""
        self._route_traffic("stable", 100)
        self._clear_semantic_cache()
        print(f"Rollback: {version} → stable")

    def _clear_semantic_cache(self):
        """Очищает semantic cache — старые ответы не должны жить после rollback."""
        redis.flushall()
        print("Semantic cache cleared")
```

**Ключевой момент:** кандидат сравнивается с **7-дневным baseline** production, а не с «вчера». Учитываются дневные и недельные паттерны трафика.

### Blue-Green deployment

Два идентичных environments: Blue (текущий production) и Green (новая версия). Переключение трафика — мгновенное.

```
┌─────────┐    ┌─────────┐
│  Blue   │    │  Green  │
│ (prod)  │◄───┤ (v2.1)  │
│  v2.0   │    │         │
└─────────┘    └─────────┘
      ▼             ▼
  Rollback:    Switch:
  v2.1→v2.0    v2.0→v2.1
  за 1 сек     за 1 сек
```

**Когда выбирать:**
- Shadow → когда риск высокий и цена 2x приемлема
- Canary → стандартный выбор для production
- Blue-Green → когда rollback должен быть мгновенным

---

## Rollback — почему он сложнее, чем в обычном софте

В обычном софте rollback = переключить версию. У агентов — нет:

```python
# Почему простой rollback не работает:
AGENT_ROLLBACK_PROBLEMS = [
    "Semantic cache хранит ответы от новой версии — пользователи видят старые ответы",
    "Downstream системы могли получить некорректные данные — они не откатятся",
    "Пользователи видели ответы новой версии — откат не удалит их память",
    "Метрики могут не показать проблему сразу — лаг до 24h",
]
```

### Правильный rollback:

```python
class AgentRollback:
    """
    Полный rollback агента. Не просто переключение версии.
    """

    def rollback(self, from_version: str, to_version: str):
        # 1. Переключить трафик
        self.traffic_router.route(to_version, 100)

        # 2. Очистить semantic cache (старые ответы от проблемной версии)
        self.cache.clear_all()

        # 3. Проверить, что rollback сработал
        if not self._verify_recovery(to_version):
            self._escalate("Rollback verification failed!")

        # 4. Заблокировать rollout этой версии
        self.release_gate.lock(from_version)

        # 5. Записать в audit log
        self.audit.log({
            "action": "rollback",
            "from": from_version,
            "to": to_version,
            "reason": self.failure_reason,
        })

    def _verify_recovery(self, version: str) -> bool:
        """Post-rollback health check (10 минут стабильности)."""
        end = time.time() + 600
        while time.time() < end:
            metrics = self.metrics.current()
            if metrics["error_rate"] > 0.05:
                return False
            time.sleep(60)
        return True

    def _escalate(self, message: str):
        """Если rollback сам не сработал — зовём человека."""
        pager.send(message, priority="P1")
```

---

## Feature Flags для агентов

Feature flags позволяют включать/выключать функциональность без деплоя:

```python
class AgentFeatureFlags:
    """
    Feature flags для агента. Позволяют точечно включать фичи.
    """
    def __init__(self):
        self.flags = {}

    def is_enabled(self, feature: str, user_id: str = None) -> bool:
        """Проверяет, включена ли фича (опционально для конкретного пользователя)."""
        flag = self.flags.get(feature)
        if not flag:
            return False
        if flag.get("rollout") == 100:
            return True
        if user_id and hash(f"{user_id}:{feature}") % 100 < flag.get("rollout", 0):
            return True
        return False

    def enable_for_user(self, feature: str, user_id: str):
        """Включает фичу для конкретного пользователя (beta-тест)."""
        self.flags[feature] = {"rollout": 100, "users": [user_id]}
```

**Примеры использования:**
- Включить новый инструмент поиска для 10% пользователей
- Тестировать новый system prompt на internal team
- Отключить сломанную фичу без деплоя

---

## Continuous Deployment Pipeline

```yaml
# .github/workflows/agent-cd.yml
name: Agent CD
on:
  push:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - run: python run_evals.py --dataset golden
      - run: python run_evals.py --dataset adversarial
      - run: python check_quality_gates.py

  shadow:
    needs: [eval]
    runs-on: ubuntu-latest
    steps:
      - run: python shadow_deploy.py --duration 24h
      - run: python analyze_shadow.py --threshold 0.95

  canary:
    needs: [shadow]
    runs-on: ubuntu-latest
    steps:
      - run: python canary_deploy.py --stage 1  # 1%, 24h
      - run: python canary_deploy.py --stage 2  # 10%, 24h
      - run: python canary_deploy.py --stage 3  # 50%, 12h

  full_rollout:
    needs: [canary]
    runs-on: ubuntu-latest
    steps:
      - run: python full_rollout.py --version ${{ github.sha }}
      - run: python verify_deployment.py
```

---

## Containerization (Docker)

Деплой агента начинается с контейнеризации. Без контейнера — «на моей машине работает».

### Dockerfile для AI-агента

```dockerfile
# Multi-stage Dockerfile для AI-агента
# Stage 1: build — устанавливаем зависимости
FROM python:3.13-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime — только нужное, без кэша pip
FROM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Код агента
COPY agent/ ./agent/
COPY config/ ./config/
COPY prompts/ ./prompts/

# Non-root пользователь
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=info

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["python", "-m", "agent.main"]
```

**Ключевые решения:**
- **Multi-stage** — финальный образ не содержит компиляторов, pip-кэша, тестов
- **Non-root user** — контейнер не имеет прав на запись в свою файловую систему
- **Healthcheck** — K8s и оркестраторы используют его для перезапуска
- **Prompts и config отдельно** — можно смонтировать ConfigMap поверх (см. K8s)

### docker-compose: локальная разработка

```yaml
version: "3.9"

services:
  agent:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_API_KEY=${LLM_API_KEY:?required}
      - LLM_MODEL=${LLM_MODEL:-gpt-4o}
      - LOG_LEVEL=${LOG_LEVEL:-debug}
      - VECTOR_DB_URL=http://qdrant:6333
    volumes:
      - ./config:/app/config:ro
      - ./prompts:/app/prompts:ro
      - agent_data:/app/data
    depends_on:
      qdrant:
        condition: service_healthy
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.12
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]

volumes:
  qdrant_data:
  agent_data:
```

**Комментарии:**
- `LLM_API_KEY:?required` — если переменная не задана, контейнер не запустится
- `./config:ro` — конфиги монтируются read-only: агент не может переписать свой конфиг через инструменты
- `condition: service_healthy` — агент не стартует, пока не готова векторная БД

### Лучшие практики Docker для агентов

| Практика | Почему |
|----------|--------|
| Фиксируй версию Python (не `slim`) | Обновление базового образа — неявный баг |
| Не храни API-ключи в образе | Переменные окружения или secrets manager |
| Healthcheck на endpoint | K8s перезапустит упавший агент |
| Read-only файловая система | Агент не запишет вредоносный файл |
| Логи — в stdout/stderr | Агент не должен писать логи в файлы |
| Один процесс на контейнер | Не запускай агент + RAG + gateway в одном контейнере |

### Сборка и публикация

```bash
# Сборка с тегом версии
docker build -t agent-registry/ai-agent:2.1.0 .
docker tag agent-registry/ai-agent:2.1.0 agent-registry/ai-agent:latest

# Публикация
docker push agent-registry/ai-agent:2.1.0
docker push agent-registry/ai-agent:latest

# Запуск
docker run -d \
  -p 8080:8080 \
  -e LLM_API_KEY=$LLM_API_KEY \
  -e LLM_MODEL=claude-sonnet-4.6 \
  agent-registry/ai-agent:2.1.0
```

---

## Kubernetes Deployment

Для production-агента с несколькими репликами, auto-scaling и zero-downtime деплоем.

### ConfigMap: выносим промпты и конфиг из образа

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
data:
  system-prompt.md: |
    Ты — AI-агент поддержки. Отвечай вежливо и по делу.
    Используй только предоставленные инструменты.
    Если не знаешь ответа — скажи, что не знаешь.

  agent.yaml: |
    model: claude-sonnet-4.6
    temperature: 0.3
    max_tokens: 4096
    timeout_seconds: 30
```

**Зачем:** можно изменить промпт без пересборки образа. `kubectl apply -f configmap.yaml` и rolling restart.

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-agent
  labels:
    app: ai-agent
    version: v2.1.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # zero-downtime
  selector:
    matchLabels:
      app: ai-agent
  template:
    metadata:
      labels:
        app: ai-agent
        version: v2.1.0
    spec:
      containers:
        - name: agent
          image: agent-registry/ai-agent:2.1.0
          ports:
            - containerPort: 8080
              protocol: TCP
          env:
            - name: LLM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-secrets
                  key: api-key
            - name: LLM_MODEL
              value: "claude-sonnet-4.6"
          envFrom:
            - configMapRef:
                name: agent-config
          volumeMounts:
            - name: config
              mountPath: /app/config/agent.yaml
              subPath: agent.yaml
            - name: config
              mountPath: /app/prompts/system-prompt.md
              subPath: system-prompt.md
            - name: tmp
              mountPath: /tmp
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: agent-config
        - name: tmp
          emptyDir: {}
```

**Комментарии:**
- `maxUnavailable: 0` — rolling update без прерывания трафика
- `envFrom: configMapRef` — вся конфигурация из ConfigMap
- `secretKeyRef` — API-ключи из K8s Secrets (не в образе!)
- `livenessProbe` — K8s перезапустит контейнер, если агент завис
- `readinessProbe` — K8s не отправляет трафик на непрогретый pod

### Service и Ingress

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-agent
spec:
  selector:
    app: ai-agent
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-agent
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
    - host: agent.mycompany.com
      http:
        paths:
          - path: /api/agent
            pathType: Prefix
            backend:
              service:
                name: ai-agent
                port: 8080
```

### Horizontal Pod Autoscaling (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-agent-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-agent
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: agent_queue_depth  # кастомная метрика: длина очереди
        target:
          type: AverageValue
          averageValue: 5
```

**Агент-специфичный HPA:** длина очереди запросов > CPU. Агенты могут ждать LLM (IO-bound), а не считать.

### Blue-Green через Service Selector

```yaml
# Шаг 1: деплоим Green (новую версию)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-agent-green
  labels:
    app: ai-agent
    version: v2.1.0
    track: green
# ... (тот же spec, что у blue)

# Шаг 2: переключаем Service на Green
apiVersion: v1
kind: Service
metadata:
  name: ai-agent
spec:
  selector:
    app: ai-agent
    track: green  # ← меняем с blue на green
```

### Canary через Service Mesh (Istio)

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ai-agent
spec:
  hosts:
    - agent
  http:
    - match:
        - headers:
            x-canary:
              exact: "true"
      route:
        - destination:
            host: ai-agent
            subset: v2_1
    - route:
        - destination:
            host: ai-agent
            subset: v2_0
          weight: 90
        - destination:
            host: ai-agent
            subset: v2_1
          weight: 10
```

### K8s best practices для агентов

| Практика | Почему |
|----------|--------|
| Readiness probe на /ready | Не отправляем трафик на агента без загруженного model cache |
| Resource limits (CPU/memory) | Агент с `while True` не убьёт ноду |
| Pod Anti-Affinity | Разные версии агента не должны быть на одной ноде |
| PDB (PodDisruptionBudget) | Хотя бы 1 pod должен быть alive во время maintenance |
| NetworkPolicy | Агент не должен ходить в произвольные внешние адреса |
| ConfigMap для промптов | Поменять поведение без деплоя |

---

## Serverless Deployment

Не все агенты требуют 24/7. Serverless — для event-driven сценариев: обработка файла, ответ на email, webhook.

### AWS Lambda + API Gateway

```python
# lambda_handler.py
import json
import os
from agent.core import Agent


# Cold-start: агент инициализируется один раз
_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        # Загружаем конфиг из переменных окружения
        _agent = Agent.from_config({
            "model": os.environ["LLM_MODEL"],
            "api_key": os.environ["LLM_API_KEY"],
            "system_prompt": os.environ.get("SYSTEM_PROMPT", ""),
        })
    return _agent


def handler(event: dict, context) -> dict:
    """
    Lambda handler для AI-агента.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        agent = get_agent()

        result = agent.run(
            task=body["task"],
            context=body.get("context", {}),
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"result": result}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
```

```yaml
# serverless.yml
service: ai-agent

provider:
  name: aws
  runtime: python3.13
  timeout: 30  # у LLM latency может быть большой
  environment:
    LLM_MODEL: claude-haiku-4.6     # для Lambda — дешёвая модель
    LLM_API_KEY: ${env:LLM_API_KEY}

functions:
  agent:
    handler: lambda_handler.handler
    events:
      - http:
          path: agent
          method: post
          # API Key для защиты
      - sqs:                              # альтернатива: из очереди
          arn: !GetAtt AgentQueue.Arn
          batchSize: 1
```

**Когда Lambda подходит:**
- Обработка одного запроса за раз (не мультиагент)
- Event-driven: файл загрузился → агент обработал
- Низкая частота запросов (не держать сервер 24/7)

**Когда НЕ подходит:**
- Долгие сессии (10+ LLM вызовов) — timeout 15 min
- Мультиагент с состоянием
- Супер-дешёвая модель не нужна, но холодный старт терпим

### Google Cloud Run

```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ai-agent
spec:
  template:
    spec:
      containers:
        - image: agent-registry/ai-agent:2.1.0
          ports:
            - containerPort: 8080
          env:
            - name: LLM_MODEL
              value: claude-haiku-4.6
          resources:
            limits:
              memory: "1Gi"
              cpu: "2"
      containerConcurrency: 5  # макс одновременных запросов
      timeoutSeconds: 300      # 5 минут на запрос
```

### Containers vs Serverless: decision

| Критерий | K8s (Deployment) | Lambda / Cloud Run |
|----------|:----------------:|:------------------:|
| Cold start | Нет | 500ms-2s (Python) |
| Max duration | Неограниченно | 15min / 60min |
| Concurrency | Любая | Ограничена |
| State | Persistent volumes | Stateless (S3/DynamoDB) |
| Cost | Фикс (за ресурсы) | За запросы (дешевле при простое) |
| Когда брать | Production, HA | Event-driven, low-volume |

**Эмпирическое правило:** если агент отвечает пользователю в реальном времени → контейнер (K8s). Если агент обрабатывает фоновые задачи → serverless.

---

## Environment & Secrets Management

### Три окружения

```yaml
# config/dev/agent.yaml
model: claude-haiku-4.6
temperature: 0.7
max_tokens: 2048
log_level: debug

# config/staging/agent.yaml
model: claude-sonnet-4.6
temperature: 0.3
max_tokens: 4096
log_level: info

# config/prod/agent.yaml
model: claude-sonnet-4.6
temperature: 0.3
max_tokens: 4096
log_level: warning
max_tools_per_step: 5
rate_limit_per_user: 10
```

**Правило:** чем ближе к production, тем больше ограничений (rate limit, max tools, strict model).

### Secrets

```yaml
# K8s Secret
apiVersion: v1
kind: Secret
metadata:
  name: llm-secrets
type: Opaque
stringData:
  api-key: sk-...       # Только в development!
  # В production: sealed-secrets / external-secrets / vault
---
# External Secrets Operator (production)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: llm-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
  target:
    name: llm-secrets
  data:
    - secretKey: api-key
      remoteRef:
        key: secret/agent/prod
        property: api-key
```

```bash
# Проверка: ключи не должны быть в образе
docker scan agent-registry/ai-agent:2.1.0
docker history agent-registry/ai-agent:2.1.0  # ищем переменные
```

### API Key Rotation

```python
class KeyRotationManager:
    """
    Ротация API-ключей без downtime.
    """
    def __init__(self):
        self.active_key: str | None = None
        self.next_key: str | None = None
        self.rotation_in_progress = False

    async def check_expiry(self, key: str, expiry_days: int = 30) -> bool:
        """Проверяет, не истекает ли ключ."""
        import base64, json
        # JWT-like декодирование payload
        payload_b64 = key.split('.')[1]
        payload = json.loads(base64.b64decode(payload_b64 + '=='))
        created = datetime.fromtimestamp(payload.get("iat", 0))
        return (datetime.now() - created).days >= expiry_days - 3

    async def rotate(self):
        """Бесшовная ротация: старый ключ жив, новый подхватывается."""
        self.rotation_in_progress = True
        self.next_key = await self._fetch_new_key()

        # Даём время: новые запросы используют next_key, старые — active_key
        await asyncio.sleep(60)

        self.active_key = self.next_key
        self.next_key = None
        self.rotation_in_progress = False
```

---

## Практическое задание

Реализуй canary-раскатку агента с авто-откатом:

1. Создай две версии агента: `v1.0` (стабильная) и `v2.0` (candidate) — пусть они отличаются system prompt-ом
2. Реализуй `CanaryDeployer`, который направляет 10% трафика на candidate
3. Добавь метрики: `task_success_rate`, `p95_latency_ms`, `cost_delta`
4. Если candidate показывает ухудшение хотя бы по одной метрике (отклонение > 5% от baseline production за 24ч) — автоматический rollback
5. При rollback очисти semantic cache и заблокируй повторный деплой этой версии

Требования: реализация `CanaryDeployer` с авто-откатом, симуляция 20 запросов с разными метриками, демонстрация rollback при падении метрик.

---

## Проверь себя

1. Какие 5 компонентов должны быть в релизном манифесте агента?
2. Чем shadow deployment отличается от canary?
3. Почему обычный rollback не работает для агентов?
4. Что такое feature flag для агента и зачем он нужен?
5. Почему нельзя использовать "latest" в model_id?
6. Как clean semantic cache при rollback?
7. Зачем в Dockerfile multi-stage? Что даёт non-root user?
8. Почему ConfigMap для промптов лучше, чем вшивать их в Docker-образ?
9. Чем liveness probe отличается от readiness probe в K8s?
10. Когда HPA по длине очереди (agent_queue_depth) лучше HPA по CPU?
11. В чём разница Blue-Green через K8s Service Selector vs через Istio VirtualService?
12. Когда serverless (Lambda) подходит для агента, а когда нет?
13. Как организовать бесшовную ротацию API-ключа без downtime?
14. Какие три окружения (dev/staging/prod) должны быть у агента и чем они отличаются?

---

## Резюме

```
Agent Lifecycle = versioning + shadow + canary + rollback
                  + docker + k8s + serverless + secrets

Версионировать (5 компонентов):
  prompts + tool_defs + model + memory + config → единый манифест

Stage gate (4 этапа):
  Shadow (24-72h) → Canary 1% → Canary 10-50% → Full (72h)

Rollback:
  traffic switch → clear cache → verify → lock gate → audit

Docker:
  multi-stage, non-root, healthcheck, read-only configs

Kubernetes:
  ConfigMap для промптов, RollingUpdate (maxUnavailable=0),
  HPA по queue depth, Blue-Green через selector,
  Canary через Istio (10% → 50% → 100%)

Serverless:
  Lambda / Cloud Run для event-driven задач
  Cold start + timeout ограничения

Secrets:
  Никогда в образе! External Secrets → Vault / AWS Secrets Manager
  Бесшовная ротация ключей

Правило: не latest-model.
         не latest-image.
         ConfigMap — не в образ.
         read-only fs в контейнере.
         auto-rollback на каждом этапе canary.
```

---

## Ссылки

- [[04-multi-agent/01-orchestration]] — мультиагентная оркестрация
- [[05-production/02-observability]] — monitoring агента
- [[12-quality-evolution/03-continuous-improvement]] — continuous improvement cycle
- [[12-quality-evolution/02-ab-testing]] — A/B тестирование агентов
- [[../assets/deployment/README|Deployment assets]] — готовые Dockerfile, docker-compose, K8s манифесты
- [Agent Rollout Strategies 2026](https://futureagi.com/blog/agent-rollout-strategies-2026/)
- [Agent Versioning, Rollback & Blue-Green](https://rapidclaw.dev/blog/ai-agent-versioning-rollback)
- [Kubernetes Production Best Practices](https://kubernetes.io/docs/setup/best-practices/)
- [External Secrets Operator](https://external-secrets.io/) — управление секретами в K8s
- [AWS Lambda for AI workloads](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
