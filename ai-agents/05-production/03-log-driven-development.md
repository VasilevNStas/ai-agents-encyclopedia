---
created: 2026-05-09
tags: [course/production, ldd, logging, observability, ai-assisted]
status: active
---

# Урок 18: Log Driven Development (LDD)

> [!quote] Ключевая идея
> Обычно логи пишут «потом» — когда что-то сломалось. LDD переворачивает подход: логи проектируются **до** кода, как контракт между системой и AI. Агент читает логи так же естественно, как человек читает документы.

---

## Проблема: логи — это свалка

Типичная картина:

```python
# ❌ Логи «на потом»
def process_order(order_id):
    logger.info(f"Processing order {order_id}")
    try:
        result = do_something(order_id)
        logger.info(f"Done: {result}")
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
```

В production:

```
[INFO] Processing order 123
[INFO] Processing order 456
[ERROR] Error: connection timeout
[INFO] Processing order 789
[INFO] Done: 789 processed
```

**AI не может с этим работать:**
- Нет структуры — всё в одной строке
- Нет контекста — что такое order? какой шаг упал?
- Нет связей — где начало и конец обработки одного order?
- Нет метрик — сколько времени занял каждый шаг?

---

## Идея LDD: логи как контракт

**LDD (Log Driven Development)** — подход, при котором:

1. **Структура логов проектируется до кода**
2. **Каждый лог — это структурированное событие**, а не строка текста
3. **AI читает логи как API** — знает, какие поля ожидать
4. **Логи — это тесты**: если лог не соответствует контракту — система работает неверно

### Принципы LDD

```
До LDD:            код → логи (от балды)
После LDD:         контракт логов → код → AI-анализ

Контракт определяет:
- Какие события логируются
- Структура каждого события
- Какие поля обязательны
- Какие метрики агрегируются
- Как AI интерпретирует результат
```

### Пример контракта

```yaml
# contract/order-processing.yaml
events:
  order.received:
    fields:
      order_id: string (required)
      timestamp: datetime (required)
      source: string (enum: web, api, batch)
    metrics:
      - latency_ms
      - total_orders
  
  order.validation:
    fields:
      order_id: string (required)
      status: string (enum: passed, failed)
      reason: string (required if failed)
    metrics:
      - validation_time_ms
  
  order.processed:
    fields:
      order_id: string (required)
      result: string (required)
      attempts: int
    metrics:
      - processing_time_ms

  order.failed:
    fields:
      order_id: string (required)
      error: string (required)
      step: string (required)
      recoverable: bool
```

---

## Реализация LDD

### Шаг 1: Определить контракт

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    RECEIVED = "order.received"
    VALIDATED = "order.validation"
    PROCESSED = "order.processed"
    FAILED = "order.failed"

@dataclass
class LogEvent:
    """Структурированное событие для AI."""
    event: str
    order_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_log(self) -> dict:
        """Превращает в JSON для лога — AI читает JSON."""
        return {
            "event": self.event,
            "order_id": self.order_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "metrics": self.metrics,
            "tags": self.tags,
        }
```

### Шаг 2: Писать код под контракт

```python
class OrderProcessor:
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def process(self, order_id: str) -> str:
        start = time.time()
        
        # Событие: заказ получен
        self.logger.emit(LogEvent(
            event=OrderStatus.RECEIVED,
            order_id=order_id,
            data={"source": "web"},
        ))
        
        # Валидация
        t0 = time.time()
        valid = self.validate(order_id)
        self.logger.emit(LogEvent(
            event=OrderStatus.VALIDATED,
            order_id=order_id,
            data={"status": "passed" if valid else "failed"},
            metrics={"validation_time_ms": (time.time() - t0) * 1000},
        ))
        
        if not valid:
            self.logger.emit(LogEvent(
                event=OrderStatus.FAILED,
                order_id=order_id,
                data={
                    "error": "validation failed",
                    "step": "validation",
                    "recoverable": False,
                },
            ))
            return "failed"
        
        # Обработка
        t0 = time.time()
        result = self.execute(order_id)
        self.logger.emit(LogEvent(
            event=OrderStatus.PROCESSED,
            order_id=order_id,
            data={"result": result, "attempts": 1},
            metrics={"processing_time_ms": (time.time() - t0) * 1000},
        ))
        
        return result
```

### Шаг 3: AI-анализ логов

```python
def analyze_logs(logs: list[dict]) -> str:
    """AI анализирует структурированные логи."""

    prompt = f"""
    Проанализируй логи обработки заказов.
    
    Формат: JSON-события с полями:
    - event: тип события
    - order_id: ID заказа
    - data: контекст
    - metrics: числовые метрики (время в ms)
    
    Логи:
    {json.dumps(logs, indent=2)}
    
    Ответь:
    1. Сколько заказов обработано успешно?
    2. Сколько упало и на каком шаге?
    3. Какие шаги самые медленные?
    4. Есть ли аномалии?
    """
    
    return llm.generate(prompt, temperature=0)
```

---

## LDD в цикле агента

LDD особенно эффективен при разработке агентов: логи — единственный способ понять, что происходило «в голове» у LLM.

```python
class LDDebugger:
    """
    Дебаггер для ReAct-цикла.
    Каждый шаг — структурированное событие.
    """
    
    def __init__(self):
        self.events: list[dict] = []
        self.contract = self._load_contract()
    
    def log_step(self, step: int, thought: str, action: str, 
                 args: dict, result: str, cost: float):
        event = {
            "event": "agent.step",
            "step": step,
            "thought": thought,
            "action": action,
            "args": args,
            "result_preview": result[:200],
            "cost": cost,
            "duration_ms": 0,
        }
        self.events.append(event)
    
    def ai_debug(self) -> str:
        """AI находит проблему в логах."""
        
        return llm.generate(f"""
        Ты — дебаггер AI-агента.
        
        Логи шагов:
        {json.dumps(self.events, indent=2)}
        
        Найди проблемы:
        1. Зациклился ли агент?
        2. Бьёт ли в пустую (повторяет одно и то же)?
        3. Расходует ли слишком много токенов?
        4. Где можно оптимизировать?
        
        Для каждой проблемы — причину и способ исправления.
        """)
```

### Пример: AI находит проблему по логам

```
Логи агента:
[step 1] glob **/*.py → нашёл 15 файлов
[step 2] read auth.py → 200 строк
[step 3] read db.py → 150 строк
[step 4] read config.py → 30 строк
[step 5] read main.py → 100 строк
[step 6] read auth.py → 200 строк (снова!)
[step 7] read db.py → 150 строк (снова!)
[step 8] read main.py → 100 строк (снова!)

AI-анализ:
⚠️ Агент зациклился на чтении файлов.
Причина: нет контекстного кеша — агент забывает, что уже читал.
Решение: добавить кеш прочитанных файлов или GRACE.
```

**Без LDD** этот цикл остался бы незамеченным до production.

---

## LDD + Observability (урок 15)

Урок 15 заложил базу: логировать каждый шаг. LDD идёт дальше:

| Аспект | Observability (урок 15) | LDD (урок 16) |
|--------|------------------------|----------------|
| Когда проектируем | После кода | До кода |
| Формат | Свободный текст | JSON-контракт |
| Кто читает | Человек | AI в первую очередь |
| Структура | Шаг агента | Событие + метрики + теги |
| Цель | Понять, что случилось | Предсказать и предотвратить |

**Вместе они образуют полную картину:**

1. **Observability** даёт API для логирования
2. **LDD** даёт контракт для структуры
3. **AI** анализирует логи в реальном времени
 4. **Resilience** (урок 17) реагирует на аномалии

---

## Anti-patterns LDD

### 1. Слишком детальный контракт

```yaml
# ❌ Каждый if-else — отдельное событие
events:
  loop.start:
  loop.iteration.enter:
  loop.iteration.check:
  loop.iteration.exit:
  loop.end:
  # через неделю — 500 событий, никто не читает

# ✅ Только значимые события
events:
  order.processed:
  order.failed:
  order.timeout:
```

### 2. Логи без контекста

```python
# ❌ Событие без контекста
{"event": "error"}

# ✅ Событие с контекстом для AI
{"event": "order.failed", "order_id": "123", "error": "timeout", "step": "payment"}
```

### 3. AI как единственный читатель

```python
# ❌ Писать только для AI
log = {"e": "proc", "oid": 123}  # человек не поймёт

# ✅ Человек тоже должен уметь читать
log = {"event": "order.processed", "order_id": 123, "result": "ok"}
```

---

## Когда LDD избыточен

| Проект | Нужен ли LDD |
|--------|-------------|
| Скрипт на 50 строк | Нет, достаточно `print()` |
| Простой API (CRUD) | Нет, обычного логирования хватит |
| ReAct-агент с 3 шагами | Желательно |
| Мультиагентная система с 10+ агентами | Обязательно |
| Production-система с AI-анализом | Обязательно |

---

## Резюме

```
Без LDD:     написали код → добавили логи → AI пытается разобрать
С LDD:       спроектировали контракт логов → написали код → AI анализирует

Логи — это интерфейс между системой и AI.
Проектируй их так же тщательно, как API.
```

---

## Практическое задание

1. Возьми ReAct-агента из [[assets/build_your_agent.py]]
2. Спроектируй контракт логов для его шагов
3. Добавь структурированное логирование по контракту
4. Напиши AI-функцию, которая анализирует логи и находит проблемы
5. Запусти агента на задаче, сломай её, проверь — находит ли AI проблему?

---

## Проверь себя

1. Чем LDD отличается от обычного логирования?
2. Что такое «контракт логов» и из чего он состоит?
3. Как AI использует структурированные логи?
4. Как LDD связан с Observability и Resilience?
5. В каких проектах LDD обязателен, а в каких избыточен?

---

## Ссылки

- [[05-production/02-observability]] — Observability (урок 17)
- [[05-production/04-resilience]] — Resilience (урок 19)
- [[05-production/05-agent-testing]] — Testing & Evaluation (урок 20)
- [[03-memory-and-rag/04-grace]] — GRACE (урок 10, GraphRAG для кода)
- [[wiki/ldd-discussion]] — обсуждение LDD
