---
created: 2026-05-08
tags: [course/memory, rag, architecture]
status: active
---

# Урок 7: Три слоя памяти агента

> [!quote] Ключевая идея
> LLM stateless — у неё нет памяти. Вся «память» агента — это **внешние структуры данных**, которые ты проектируешь. Три слоя: **short-term** (контекст), **working** (текущая задача), **long-term** (между сессиями).

---

## Память — это не свойство LLM

Повторим ключевой факт из урока 1:

> LLM не помнит предыдущий запрос. Каждый запрос — чистый лист.

Всё, что агент «помнит» — это то, что ты **кладешь в контекст** перед каждым вызовом. Если ты не положил — модель этого «не знает».

```
Ты:         "Меня зовут Вася"
LLM:        "Привет, Вася!"
                    ↓
Ты:         "Как меня зовут?"  ← БЕЗ контекста
LLM:        "Я не знаю"
                    ↓
Ты:         "Как меня зовут?"  ← С контекстом (предыдущий диалог)
LLM:        "Вас зовут Вася"
```

Память агента — это **инженерная задача**, а не свойство модели.

---

## Три слоя памяти

```
┌─────────────────────────────────────────────────┐
│                   Long-term                       │
│  (файлы, векторные БД, графы, wiki)              │
│  сохраняется между сессиями, не ограничена         │
├─────────────────────────────────────────────────┤
│                   Working                         │
│  (scratchpad, plan, context.json, заметки)        │
│  живёт пока выполняется задача                    │
├─────────────────────────────────────────────────┤
│                   Short-term                      │
│  (контекстное окно — messages[], 128k токенов)   │
│  живёт один запрос                                │
└─────────────────────────────────────────────────┘
```

### Short-term memory

Это **контекстное окно**. Всё, что ты передаёшь модели в messages[]:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "напиши функцию"},
    {"role": "assistant", "content": "вот код..."},
    {"role": "tool", "content": "результат выполнения"},
]
```

**Характеристики:**
- Ограничена (4k — 2M токенов)
- Исчезает после запроса
- Самая быстрая (данные уже «в модели»)

**Проблема:** когда messages переполняются — теряется начало (lost-in-the-middle).

### Working memory

Это **черновик** текущей задачи. Данные, которые агент пишет и читает по ходу выполнения:

```python
working_memory = {
    "task": "найти баг в авторизации",
    "plan": [
        "1. Найти файлы auth",
        "2. Прочитать тесты",
        "3. Найти вызовы login()",
        "4. Проверить обработку ошибок"
    ],
    "findings": ["баг в auth.py:42 — не проверяется токен"],
    "current_step": 3,
    "attempts": 1
}
```

Где хранить:
- JSON-файл на диске (`workspace/context.json`)
- Переменная в Python (если агент — программа)
- Отдельное сообщение в контексте (`{"role": "system", "content": f"Текущее состояние: {wm}"}`)

**Характеристики:**
- Живёт, пока выполняется задача
- Структурирована (JSON лучше текста)
- Не теряется при переполнении контекста (лежит в файле)

### Long-term memory

Знания, которые агент сохраняет **между сессиями**. Три основных типа:

| Тип | Формат | Пример |
|-----|--------|--------|
| **Файлы** | Markdown, JSON | Wiki-страницы, заметки |
| **Векторные БД** | Embeddings | Поиск по смыслу |
| **Графы знаний** | Nodes + Edges | Связи между понятиями |

```python
# Long-term: запись
def remember(topic: str, content: str):
    """Сохраняет знание в долговременную память."""
    
    # Вариант 1: Markdown-файл (LLM Wiki)
    with open(f"wiki/{topic}.md", "w") as f:
        f.write(f"# {topic}\n\n{content}")
    
    # Вариант 2: Векторная БД
    embedding = embed(content)
    vector_db.insert(topic, embedding, content)
    
    # Вариант 3: Граф знаний
    graph.add_node(topic, content)
```

---

## Как слои работают вместе

```python
class AgentMemory:
    def __init__(self, wiki_path: str = "wiki/"):
        self.short_term = []       # messages[]
        self.working = {           # текущий контекст
            "task": None,
            "plan": [],
            "step": 0,
            "notes": []
        }
        self.wiki_path = wiki_path  # long-term
    
    def load_long_term(self, topic: str) -> str:
        """Достать знание из долговременной памяти."""
        path = f"{self.wiki_path}/{topic}.md"
        if os.path.exists(path):
            return open(path).read()
        return None
    
    def save_long_term(self, topic: str, content: str):
        """Сохранить знание."""
        os.makedirs(self.wiki_path, exist_ok=True)
        with open(f"{self.wiki_path}/{topic}.md", "w") as f:
            f.write(content)
    
    def build_context(self) -> list:
        """Собирает messages[] для запроса к LLM:
        system prompt + working memory + short-term history.
        """
        context = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем working memory как контекст
        if self.working["task"]:
            context.append({
                "role": "system",
                "content": f"Текущая задача: {self.working['task']}"
            })
            context.append({
                "role": "system",
                "content": f"План: {json.dumps(self.working['plan'])}"
            })
        
        # Добавляем short-term (но не больше лимита)
        context.extend(self._trim_history(self.short_term))
        
        return context
```

---

## Пример: debugging-сессия с памятью

```
СЕССИЯ 1
────────
Задача: "найди баг в login"
Агент ищет, находит баг → сохраняет в long-term:
  wiki/login-bug.md:
    "Баг: неверный порядок проверки токена в auth.py:42"
  → закрывает сессию

СЕССИЯ 2 (на следующий день)
────────
Задача: "почини баг в login"
Working memory загружается заново (новая задача)
Short-term — пустой (новая сессия)
Long-term:
  → агент читает wiki/login-bug.md
  → вспоминает, где баг
  → не тратит время на перепоиск
```

---

## Anti-patterns памяти

### 1. Всё в short-term
```python
# ❌ Хранить ВСЮ историю сессии в messages[]
messages.append(every_single_tool_call)
# контекст переполнится через 5 шагов
```

### 2. Всё в long-term
```python
# ❌ Сохранять КАЖДЫЙ шаг в wiki
save_to_wiki(step_1)  # через неделю — 1000 файлов, ничего не найти
save_to_wiki(step_2)
# wiki превращается в свалку
```

### 3. Нет working memory
```python
# ❌ Агент не помнит, на каком он шаге
# Каждый вызов LLM — "с чистого листа"
# Потеря контекста задачи на каждом шаге
```

### 4. Не синхронизировать слои
```python
# ❌ Агент нашёл ответ, но не сохранил в long-term
# В следующей сессии — ищет заново
```

---

## Когда какой слой использовать

| Сценарий | Short-term | Working | Long-term |
|----------|-----------|---------|-----------|
| Текущий диалог | ✅ | ✅ | — |
| План задачи | — | ✅ | — |
| Промежуточные результаты | ✅ | ✅ | — |
| Найденный баг | — | — | ✅ |
| Архитектура проекта | — | — | ✅ |
| Прошлые сессии | — | — | ✅ |
| Инструкции агента | ✅ | — | ✅ |

---

## Резюме

```
Short-term:  messages[] — живёт один запрос
Working:     context.json — живёт пока выполняется задача
Long-term:   wiki/*.md — живёт между сессиями

Short-term — быстрая, но маленькая
Working    — структурированная, для текущей задачи
Long-term  — медленная, но безграничная
```

---

## Практическое задание

Посмотри на нашу текущую сессию и определи:

1. Что здесь является short-term памятью?
2. Что могло бы быть working memory?
3. Что из этого диалога стоило бы сохранить в long-term (wiki)?

---

## Проверь себя

1. Почему у LLM нет «своей» памяти?
2. Какие 3 слоя памяти существуют в архитектуре агента?
3. Чем working memory отличается от short-term?
4. Какой anti-pattern возникает, если не разделять слои?

---

## Ссылки

- [[01-fundamentals/01-how-llms-work]] — напоминание: LLM stateless
- [[03-memory-and-rag/02-rag-advanced]] — следующий урок: RAG 2.0
- [[03-memory-and-rag/03-llm-wiki]] — LLM Wiki — подход Карпати к long-term
