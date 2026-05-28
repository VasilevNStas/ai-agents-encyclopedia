---
created: 2026-05-28
tags: [course/capstone, project, design, architecture]
status: active
---

# Урок 51: Capstone — Архитектура системы

> [!quote] Ключевая идея
> Capstone — это экзамен. Ты не читаешь, ты строишь. Весь курс был подготовкой к этому моменту: спроектировать production-агента от идеи до мониторинга.

---

## Постановка задачи

Ты — AI-архитектор в SaaS-компании **SupportFlow**, которая управляет support-тикетами 5000+ B2B-клиентов.

### Бизнес-требования

| Требование | Описание |
|------------|----------|
| Автоответ | Агент отвечает на 70% тикетов без участия человека |
| Эскалация | Сложные запросы передаются senior-агенту с контекстом |
| База знаний | Ответы основаны на документации продукта (50+ страниц) |
| Мультиязычность | Клиенты пишут на EN, RU, DE, FR |
| Аналитика | Еженедельный отчёт: темы, тон, SLA, пропущенные кейсы |
| Бюджет | $500/мес на API моделей |
| Время ответа | < 3 секунд для 95% запросов |
| Безопасность | Никакие данные клиентов не покидают VPC |

### Твоя роль

Спроектировать систему. Через 1 неделю — код. Через 2 недели — deploy в production.

> [!warning] Реалистичные ограничения
> - Нет budget на fine-tuning (только prompting + RAG)
> - DevOps-опыт команды — базовый Docker
> - В production уже есть Postgres + Redis

---

## Фреймворк принятия решений

Каждое архитектурное решение должно быть явным. Используй формат ADR (Architecture Decision Record):

```markdown
## ADR-001: Выбор паттерна агента

**Контекст:** Нам нужен баланс скорости и качества ответов
**Рассмотрено:** ReAct, Plan-and-Solve, Reflexion, простой LLM-call
**Решение:** ReAct (итеративный цикл наблюдение→действие)
**Обоснование:** 
  - Plan-and-Solve избыточен для тикетов (90% — простые запросы)
  - Reflexion нужен только для эскалированных тикетов
  - ReAct даёт best-effort с возможностью tool-use
**Последствия:**
  - Нужен guardrail на количество шагов цикла (max 3)
  - Дороже простого LLM-call на 2-3x (extra tokens на chain-of-thought)
```

### Шаблон ADR для Capstone

Для каждого решения ниже заполни свой ADR:

1. **Problem** — что решаем
2. **Options** — что рассматривали
3. **Decision** — что выбрали и почему
4. **Consequences** — к чему это ведёт

---

## Архитектурные решения

### Решение 1: Паттерн агента

Варианты:
- **ReAct** — наблюдение → мысль → действие → наблюдение
- **Plan-and-Solve** — сначала план, потом исполнение
- **Reflexion** — с самооценкой и повторными попытками
- **Простой LLM-call** — один запрос без цикла

> [!question] Вопрос
> Какой паттерн выберешь для основного цикла? Что будет критерием выбора?

### Решение 2: Multi-agent vs Single-agent

| Критерий | Single-agent | Multi-agent |
|----------|-------------|-------------|
| Сложность | Низкая | Высокая |
| Стоимость | 1 LLM call | N LLM calls |
| Отказоустойчивость | Одна точка отказа | Graceful degradation |
| Специализация | Универсал | Эксперты |
| Debugging | Простой | Сложный |

> [!question] Вопрос
> Нужна ли мультиагентность для SupportFlow? Если да — Supervisor или Peer-to-Peer?

### Решение 3: RAG стратегия

Какие данные индексировать:
- Product docs (50 страниц, Markdown)
- FAQ (200 записей)
- Historical tickets (10000+ примеров)
- Known issues (из Jira)

Варианты:
- **Naive RAG** — один поиск, один контекст
- **RAG 2.0** — query rewriting + re-ranking + fusion
- **Agentic RAG** — агент сам решает, когда и что искать
- **LLM Wiki** — пре-процессинг документации (Karpathy)

> [!question] Вопрос
> Какую стратегию RAG выберешь? Как быть с мультиязычностью?

### Решение 4: Guardrails

| Слой | Угроза | Решение |
|------|--------|--------|
| Input | Prompt injection | Input sanitizer + classifier |
| Output | Halucination, PII leak | Output validator + fact-check |
| Data | Утечка контекста | Data guardrail на RAG контекст |
| Budget | Overspend | Cost guardrail (max tokens per session) |

> [!question] Вопрос
> Какие guardrails критичны для SupportFlow? Какие можно отложить?

### Решение 5: Model Selection

Условия:
- Латентность < 3 сек
- Бюджет $500/мес
- Мультиязычность (EN, RU, DE, FR)
- Сложные инструкции (JSON mode, function calling)

> [!question] Вопрос
> Какую модель выберешь? Один model или model router (pro + cheap)?

### Решение 6: Observability

Что нужно знать в production:
- Качество ответов (какой % принят пользователем?)
- Cost per ticket
- Латентность
- Топ-10 тем
- Эскалации (почему?)

> [!question] Вопрос
> Что будешь логировать? Какие метрики собирать? Какой инструмент?

### Решение 7: Evaluation

До релиза:
- Unit-тесты (изолированные компоненты)
- Integration-тесты (RAG + LLM)
- Eval dataset (200 тикетов с reference answer)
- A/B тест (агент vs человек)

В production:
- User feedback (👍/👎 на каждый ответ)
- Automated eval (LLM as judge)
- Дрифт-детектор

> [!question] Вопрос
> Какой eval-датасет соберёшь? Какие метрики качества?

### Решение 8: Развёртывание

| Вариант | Pros | Cons |
|---------|------|------|
| Docker Compose | Простота | Нет auto-scaling |
| K8s (EKS/GKE) | Масштабирование | Сложность ops |
| Serverless (Lambda) | Нет ops | Cold starts |
| Cloud Run | Баланс | Ограничения по времени |

> [!question] Вопрос
> Куда деплоить SupportFlow с бюджетом $500/мес и базовым DevOps?

---

## Результат Capstone (Part 1)

Ты должен создать документ `15-capstone/adr-supportflow.md` с:

1. **System Context Diagram** — текстовый ascii
2. **Все ADR** (минимум 5 из 8)
3. **Data Flow** — как движется запрос от пользователя до ответа
4. **Cost Estimation** — token burn rate, monthly projection
5. **Milestones** — план на 2 недели

### Пример структуры ADR-документа

```markdown
# SupportFlow — Architecture Decision Record

## Контекст
...

## ADR-001: ReAct
...

## ADR-002: Single-agent
...

## Data Flow
User → API Gateway → Guardrails → Agent → RAG → LLM → Output Validation → Response
         ↑                                                                ↓
         └────────── Observability (logs, metrics, traces) ──────────────┘
```

---

## Практическое задание

Составь минимум 5 ADR (Architecture Decision Records) для SupportFlow:

1. **ADR-001: Паттерн агента** — обоснуй выбор ReAct / Plan-and-Solve / Reflexion
2. **ADR-002: RAG стратегия** — какой RAG пайплайн и почему
3. **ADR-003: Модель** — одна модель или router; почему укладываешься в $500/мес
4. **ADR-004: Guardrails** — какие 3 guardrails ставишь в первую очередь
5. **ADR-005: Deployment** — куда деплоишь и почему (Docker Compose / Cloud Run / K8s)

Для каждого ADR используй формат: Контекст → Рассмотрено → Решение → Обоснование → Последствия.
Сохрани результат в `15-capstone/adr-supportflow.md`.

Требования: каждое решение должно быть защищено цифрами (cost, latency, complexity). ADR должны быть согласованы между собой (одно решение не должно противоречить другому).

---

## Проверь себя

1. Почему ADR — обязательный артефакт архитектора?
2. Какой критический guardrail нужен для ReAct цикла?
3. Как оценить, нужен ли multi-agent?
4. Как RAG 2.0 отличается от Naive RAG в контексте support?
5. Как уложиться в $500/мес при 5000 клиентах?

---

## Резюме

```
Capstone Part 1: спроектировать SupportFlow

Что делаем:
  1. Выбрать паттерн агента
  2. Решить single vs multi-agent
  3. Выбрать RAG стратегию
  4. Спроектировать guardrails
  5. Выбрать модель
  6. Спроектировать observability
  7. Выбрать eval strategy
  8. Выбрать deployment target

Результат: ADR-документ с обоснованием каждого решения
Критерий: каждое решение можно защитить перед твоим tech lead
```

---

## Ссылки

- [[04-multi-agent/01-orchestration]] — 6 топологий мультиагентных систем
- [[05-production/01-guardrails]] — guardrails для агента
- [[08-decision-architecture/02-model-selection]] — выбор модели
- [[08-decision-architecture/03-cost-optimization]] — бюджет
- [[09-advanced-rag-agents/01-agentic-rag]] — RAG для агента
- [[13-ecosystem-operations/01-agent-frameworks]] — фреймворки для реализации
- [[13-ecosystem-operations/03-production-operations]] — production ops
