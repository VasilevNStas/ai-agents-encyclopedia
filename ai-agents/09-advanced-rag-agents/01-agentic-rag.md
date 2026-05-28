---
created: 2026-05-28
tags: [course/advanced-rag, agentic-rag, agents]
status: active
---

# Урок 33: Agentic RAG

> [!quote] Ключевая идея
> Passive RAG просто ищет документы по запросу. Agentic RAG — это агент, который **сам решает**, как искать, когда переформулировать запрос и когда признать, что ответа нет в базе знаний.

---

## Что такое Agentic RAG

**Passive RAG** (обычный RAG):

```
Запрос → embed → поиск → LLM → ответ
```

Один проход, никаких решений. Нашёл — ответил. Не нашёл — галлюцинирует или молчит.

**Agentic RAG** — RAG, управляемый агентом. Агент решает:

- **Когда искать** (может не искать, если знает ответ)
- **Что искать** (переформулирует запрос)
- **Как искать** (какой инструмент: векторный поиск, BM25, SQL, API)
- **Когда достаточно** (останавливается, когда ответ найден)
- **Что делать, если не нашёл** (меняет стратегию)

```
Запрос
  │
  ▼
┌──────────────────────┐
│  Agent               │
│                      │
│  ┌──────────────────┐│
│  │  Reasoning Loop  ││
│  │  ┌──────────┐    ││
│  │  │ Think    │────┼│──→ "Нужно уточнить запрос"
│  │  └──────────┘    ││
│  │  ┌──────────┐    ││
│  │  │ Search   │────┼│──→ vector_db.search(...)
│  │  └──────────┘    ││
│  │  ┌──────────┐    ││
│  │  │ Evaluate │────┼│──→ "Достаточно? Или ещё поискать?"
│  │  └──────────┘    ││
│  │  ┌──────────┐    ││
│  │  │ Answer   │────┼│──→ "Вот ответ"
│  │  └──────────┘    ││
│  └──────────────────┘│
└──────────────────────┘
```

### Ключевые отличия от Passive RAG

| Характеристика | Passive RAG | Agentic RAG |
|----------------|-------------|-------------|
| Количество поисков | 1 | N (пока не удовлетворён) |
| Формулировка запроса | Как есть | Может переформулировать |
| Стратегия поиска | Фиксированная | Выбирает из инструментов |
| Оценка результата | Нет | Оценивает: ответ найден? |
| Обработка неудачи | "Не знаю" / галлюцинация | Меняет стратегию |
| Контроль качества | Нет | Проверяет факты |

> [!important] Agentic RAG — это не замена RAG, а надстройка. Векторный поиск всё ещё основа. Агент — дирижёр, оркестр — поисковые инструменты.

---

## Multi-hop Retrieval

**Multi-hop Retrieval** — разбиение сложного вопроса на подвопросы, каждый из которых требует отдельного поиска.

### Пример

```
Вопрос: "В какой компании работает CEO стартапа, который купила NVIDIA в 2024 году?"

Хоп 1: Какие стартапы купила NVIDIA в 2024?
  → Поиск: "NVIDIA acquisitions 2024"
  → Ответ: "Deci AI, Run:ai"

Хоп 2: Кто CEO Run:ai?
  → Поиск: "Run:ai CEO"
  → Ответ: "Omri Geller"

Хоп 3: Где сейчас работает Omri Geller?
  → Поиск: "Omri Geller current position 2025"
  → Ответ: "VP of AI Infrastructure at NVIDIA"

Финальный ответ: "NVIDIA"
```

### Реализация

```python
from typing import Any
import json


class MultiHopRAGAgent:
    """Агент, разбивающий сложный вопрос на подвопросы."""

    def __init__(self, search_tool: Any, llm: Any):
        self.search = search_tool
        self.llm = llm

    def _decompose(self, question: str) -> list[str]:
        """Разбить вопрос на последовательные подвопросы."""

        prompt = f"""
        Разбей сложный вопрос на последовательность простых подвопросов.
        Каждый подвопрос должен быть самодостаточным для поиска.

        Вопрос: {question}

        Формат ответа (JSON):
        {{"sub_questions": ["подвопрос 1", "подвопрос 2", ...]}}

        Правила:
        - Подвопросы должны идти в логическом порядке
        - Ответ на предыдущий подвопрос может быть нужен для следующего
        - Не более 5 подвопросов
        """

        result = self.llm.generate(prompt, response_format="json")
        return json.loads(result)["sub_questions"]

    def _answer_sub_question(self, sub_q: str, context: str) -> str:
        """Ищет ответ на подвопрос с учётом предыдущего контекста."""

        docs = self.search.search(sub_q, top_k=3)
        search_context = "\n".join(d.text for d in docs)

        answer_prompt = f"""
        Предыдущий контекст: {context}

        Результаты поиска по запросу "{sub_q}":
        {search_context}

        Ответь на подвопрос на основе найденной информации.
        Если информации недостаточно — ответь "NEED_MORE_INFO".
        """

        return self.llm.generate(answer_prompt, temperature=0)

    def run(self, question: str) -> str:
        sub_questions = self._decompose(question)
        context = ""
        final_answer = ""

        for i, sub_q in enumerate(sub_questions, 1):
            print(f"[Хоп {i}] Подвопрос: {sub_q}")
            answer = self._answer_sub_question(sub_q, context)
            context += f"\n{sub_q}: {answer}"
            print(f"[Хоп {i}] Ответ: {answer}")

        # Финальная сборка
        synthesis_prompt = f"""
        Исходный вопрос: {question}

        Собранная информация:
        {context}

        Дай полный ответ на исходный вопрос.
        """

        return self.llm.generate(synthesis_prompt, temperature=0)
```

### Когда Multi-hop необходим

| Сценарий | Пример | Нужен Multi-hop? |
|----------|--------|------------------|
| Прямой факт | "Столица Франции?" | Нет |
| Цепочка фактов | "Кто основал компанию, сделавшую X?" | Да |
| Сравнение | "У какой компании выручка больше: A или B?" | Да |
| Агрегация | "Сколько всего проектов у команды X?" | Зависит (может один SQL) |
| Многосоставной | "Как повлиял закон Y на рынок Z в 2025?" | Да |

---

## Self-Query: динамическая переформулировка

**Self-Query** — агент переформулирует поисковый запрос на основе предыдущих результатов. Не разбивает на подвопросы (как multi-hop), а **уточняет один и тот же запрос**.

```
Запрос: "новости про ИИ"

Поиск 1: "новости про ИИ" → [статья про GPT-5, статья про роботов, статья про регуляции]

Оценка: "Слишком широко. Пользователь, вероятно, про модели, а не про роботов"
→ Переформулировка: "новые модели ИИ 2026"

Поиск 2: "новые модели ИИ 2026" → [DeepSeek R2, Claude 4, Gemini Ultra]

Оценка: "Отлично, теперь можно ответить"
→ Ответ: "В 2026 вышли DeepSeek R2, Claude 4 и Gemini Ultra..."
```

```python
class SelfQueryRAGAgent:
    """Агент с динамической переформулировкой запросов."""

    def __init__(self, search_tool: Any, llm: Any, max_iters: int = 3):
        self.search = search_tool
        self.llm = llm
        self.max_iters = max_iters

    def _evaluate_results(self, query: str, results: list) -> str:
        """Оценить, достаточно ли результатов для ответа."""

        context = "\n".join(r.text for r in results)

        prompt = f"""
        Запрос: {query}
        Найденные документы:
        {context}

        Оцени по шкале от 0 до 10:
        - Насколько полно документы отвечают на запрос?
        - Есть ли явные пробелы?

        Если оценка >= 8, ответь "SUFFICIENT".
        Если < 8, ответь "INSUFFICIENT: <причина>".
        """

        return self.llm.generate(prompt, temperature=0)

    def _reformulate(self, query: str, results: list, evaluation: str) -> str:
        """Переформулировать запрос на основе результатов."""

        context = "\n".join(r.text for r in results)

        prompt = f"""
        Исходный запрос: {query}

        Найденные документы:
        {context}

        Причина неудовлетворительности: {evaluation}

        Переформулируй запрос так, чтобы найти недостающую информацию.
        Ответь ТОЛЬКО новым запросом.
        """

        return self.llm.generate(prompt, temperature=0.3)

    def run(self, query: str) -> str:
        current_query = query
        all_results = []

        for i in range(self.max_iters):
            print(f"[Итерация {i + 1}] Поиск: {current_query}")

            results = self.search.search(current_query, top_k=5)
            all_results.extend(results)

            evaluation = self._evaluate_results(current_query, all_results)

            if evaluation.startswith("SUFFICIENT"):
                print("[Оценка] Информации достаточно")
                break

            print(f"[Оценка] {evaluation}")

            if i < self.max_iters - 1:
                current_query = self._reformulate(
                    current_query, all_results, evaluation
                )
                print(f"[Переформулировка] → {current_query}")

        return self.llm.generate(
            f"Вопрос: {query}\n\nКонтекст:\n"
            + "\n".join(r.text for r in all_results)
            + "\n\nДай развёрнутый ответ.",
            temperature=0,
        )
```

> [!warning] Граница переформулировок
> Self-query эффективен, только если информация **существует в базе знаний**, но её трудно найти с первой попытки. Если данных нет — никакая переформулировка не поможет.

---

## Self-Correcting RAG

**Self-Correcting RAG** — агент, который проверяет свой ответ по фактам и исправляет ошибки. Если ответа нет в контексте — не галлюцинирует, а меняет стратегию.

### Ключевые проверки

1. **Faithfulness** — ответ не противоречит контексту?
2. **Relevance** — ответ отвечает на вопрос?
3. **Completeness** — все части вопроса покрыты?
4. **Evidence** — каждое утверждение подтверждено источником?

```python
class SelfCorrectingRAGAgent:
    """Агент с самопроверкой и коррекцией ответа."""

    def __init__(self, search_tool: Any, llm: Any, max_retries: int = 2):
        self.search = search_tool
        self.llm = llm
        self.max_retries = max_retries

    def _generate_answer(self, question: str, context: str) -> str:
        prompt = f"""
        Ответь на вопрос на основе контекста.
        Если ответа нет в контексте — напиши "NOT_FOUND".

        Контекст:
        {context}

        Вопрос: {question}
        """

        return self.llm.generate(prompt, temperature=0)

    def _check_faithfulness(self, answer: str, context: str) -> list[str]:
        """Проверить, что каждое утверждение подтверждено контекстом."""

        prompt = f"""
        Контекст: {context}
        Ответ: {answer}

        Разбей ответ на отдельные утверждения.
        Для каждого утверждения укажи:
        - "SUPPORTED", если оно подтверждено контекстом
        - "UNSUPPORTED", если контекст не содержит такого

        Формат:
        Утверждение: <текст>
        Статус: <SUPPORTED|UNSUPPORTED>
        """

        result = self.llm.generate(prompt, temperature=0)
        return self._parse_check(result)

    def _check_completeness(self, question: str, answer: str) -> str:
        """Проверить, полностью ли ответ покрывает вопрос."""

        prompt = f"""
        Вопрос: {question}
        Ответ: {answer}

        Вопрос содержит несколько частей/аспектов?
        Все ли они покрыты ответом?

        Если не все — перечисли недостающие аспекты.
        Если все — ответь "COMPLETE".
        """

        return self.llm.generate(prompt, temperature=0)

    def _search_missing_info(self, missing_aspect: str) -> str:
        """Найти недостающую информацию."""

        return self.search.search(missing_aspect, top_k=3)

    def run(self, question: str) -> str:
        # Первичный поиск
        docs = self.search.search(question, top_k=5)
        context = "\n".join(d.text for d in docs)

        for attempt in range(self.max_retries):
            print(f"[Попытка {attempt + 1}] Генерация ответа")

            answer = self._generate_answer(question, context)

            if answer == "NOT_FOUND":
                print("[Коррекция] Ответ не найден — меняем стратегию поиска")
                docs = self._alternative_search(question)
                context = "\n".join(d.text for d in docs)
                continue

            # Проверка фактов
            errors = self._check_faithfulness(answer, context)
            unsupported = [e for e in errors if "UNSUPPORTED" in e]

            if unsupported:
                print(f"[Коррекция] Найдено {len(unsupported)} неподтверждённых "
                      f"утверждений")
                # Удаляем неподтверждённые части и просим LLM переписать
                answer = self._remove_unsupported(answer, unsupported)

            # Проверка полноты
            completeness = self._check_completeness(question, answer)

            if completeness == "COMPLETE":
                print("[ОК] Ответ полный и фактологичный")
                return answer

            print(f"[Коррекция] Не хватает: {completeness}")
            extra_docs = self._search_missing_info(completeness)
            extra_context = "\n".join(d.text for d in extra_docs)

            # Дополняем ответ
            answer = self._supplement_answer(
                answer, completeness, extra_context
            )
            context += "\n" + extra_context

        return answer

    def _alternative_search(self, question: str) -> list:
        """Альтернативная стратегия поиска."""

        strategies = [
            lambda q: self.search.search(q, top_k=10),
            lambda q: self.search.search(
                self._keyword_extract(q), top_k=5
            ),
            lambda q: self.search.search(
                f"what is {q}", top_k=3
            ),
        ]

        all_results = []
        for strategy in strategies:
            results = strategy(question)
            all_results.extend(results)

        # Дедупликация
        seen = set()
        unique = []
        for r in all_results:
            if r.id not in seen:
                seen.add(r.id)
                unique.append(r)

        return unique[:10]

    def _keyword_extract(self, text: str) -> str:
        prompt = f"Извлеки ключевые слова из запроса: {text}"
        return self.llm.generate(prompt, temperature=0)

    def _remove_unsupported(self, answer: str, errors: list) -> str:
        prompt = f"""
        Ответ: {answer}

        Следующие утверждения не подтверждены контекстом: {errors}
        Перепиши ответ, удалив эти утверждения.
        """

        return self.llm.generate(prompt, temperature=0)

    def _supplement_answer(
        self, answer: str, missing: str, extra_context: str
    ) -> str:
        prompt = f"""
        Текущий ответ: {answer}

        Не хватает: {missing}

        Дополнительная информация:
        {extra_context}

        Дополни ответ, добавив недостающую информацию.
        """

        return self.llm.generate(prompt, temperature=0)

    def _parse_check(self, text: str) -> list[str]:
        return [line.strip() for line in text.split("\n") if "Утверждение:" in line or "Статус:" in line]
```

> [!important] Self-correcting ≠ бесконечный цикл
> Всегда ограничивай количество итераций коррекции. Либо `max_retries`, либо бюджеты токенов. Агент может "закопаться" в поиске идеального ответа.

---

## Сравнение подходов Agentic RAG

| Подход | Когда использовать | Риски |
|--------|-------------------|-------|
| **Multi-hop** | Цепочка фактов: A → B → C | Переусложнение простых вопросов |
| **Self-query** | Широкий запрос, который нужно уточнить | Зацикливание переформулировок |
| **Self-correcting** | Высокие требования к точности | Дорого (много LLM-вызовов) |
| **Комбинация** | Сложные задачи с требованиями к качеству | Сложность отладки |

---

## Anti-patterns Agentic RAG

### 1. Бесконечный цикл поиска

```python
# ❌ Нет ограничения на итерации
while not satisfied:
    results = search(query)
    answer = evaluate(query, results)
    # если оценка никогда не будет 10/10 — бесконечный цикл

# ✅ Всегда max_iters + fallback
for i in range(max_iters):
    # ...
return best_answer or "не удалось найти ответ"
```

### 2. Игнорирование контекста

```python
# ❌ LLM отвечает из головы, игнорируя найденные документы
answer = llm.generate(question)  # контекст даже не подан

# ✅ Строгое следование контексту
answer = llm.generate(f"Контекст: {context}\n\nВопрос: {question}\n\n"
                      "Ответь строго на основе контекста.")
```

### 3. Self-query без оценки

```python
# ❌ Переформулировка без проверки, помогло ли это
query = reformulate(query)
for _ in range(5):
    results = search(query)
    query = reformulate(query, results)
# Всё переформулируем, но не проверяем, стало ли лучше

# ✅ Оценка перед следующей итерацией
query = reformulate(query)
for _ in range(5):
    results = search(query)
    if is_sufficient(results):
        break
    query = reformulate(query, results)
```

### 4. Слишком глубокая декомпозиция

```python
# ❌ Вопрос "сколько времени" разбит на 5 подвопросов
sub_qs = decompose("Который час?")
# → "Какие часовые пояса существуют?"
# → "Какой часовой пояс у пользователя?"
# → "Как получать текущее время?"
# → ...

# ✅ Золотое правило: не больше подвопросов, чем нужно для ответа
```

> [!warning] Когда Agentic RAG не нужен
> Если база знаний маленькая (влезает в контекст) — не строй агента. Просто вставь документы в промпт. Agentic RAG — это решение для **больших и неструктурированных** баз знаний.

---

## Практическое задание

Возьми существующий RAG-пайплайн (или любой проект с документацией) и добавь в него слой Agentic RAG:

1. Реализуй `SelfQueryRAGAgent` для своего домена
2. Добавь `max_iters=3` и логирование каждой итерации
3. Протестируй на запросах разной сложности:
   - Простой факт (1 поиск)
   - Широкий запрос (нужна переформулировка)
   - Вопрос, на который нет ответа (должен остановиться)
4. Сравни качество ответов: passive RAG vs agentic RAG

---

## Проверь себя

1. В чём ключевое отличие Agentic RAG от Passive RAG?
2. Чем Self-query отличается от Multi-hop Retrieval?
3. Какие три проверки выполняет Self-Correcting RAG?
4. Какой антипаттерн возникает, если не ограничить максимальное количество итераций поиска?
5. В каком случае Agentic RAG избыточен и не нужен?

---

## Резюме

```
Agentic RAG = RAG + агентский цикл (think → search → evaluate → repeat)

Multi-hop:    разбить вопрос → искать по частям → собрать ответ
Self-query:   искать → оценить → переформулировать → искать снова
Self-correct: ответить → проверить факты → исправить → проверить полноту

Пассивный RAG:  один поиск → один ответ
Agentic RAG:    N поисков → оценка → коррекция → ответ

Главное правило: агент должен УМЕТЬ остановиться.
```

---

## Ссылки

- [[03-memory-and-rag/02-rag-advanced]] — основы RAG 2.0
- [[03-memory-and-rag/01-memory-types]] — три слоя памяти
- [[01-fundamentals/03-react-pattern]] — ReAct: база любого агента
- [[02-agent-patterns/01-plan-and-solve]] — планирование для агентов
- [[02-agent-patterns/02-reflexion]] — рефлексия и самокоррекция
