---
created: 2026-05-09
tags: [course/memory, rag, graph, grace, code-engineering]
status: active
---

# Урок 10: GRACE — Graph-RAG Anchored Code Engineering

> [!quote] Ключевая идея
> Обычный RAG ищет «похожие куски текста». GraphRAG строит граф сущностей и связей. GRACE — это GraphRAG, «пришвартованный» к коду: он понимает архитектуру проекта, зависимости между модулями и историю изменений.

> [!info] Статус технологии
> GRACE — экспериментальный подход от сообщества (Владимир Иванов). Это не промышленный стандарт, а демонстрация концепции. Для production-кода используй Microsoft GraphRAG или LightRAG. GRACE включён как иллюстрация идеи «что можно сделать, если пойти дальше RAG».

---

## От RAG к GraphRAG

В уроке 8 мы разобрали RAG 2.0 — пайплайн с rewriting, hybrid search, reranking. Но у него есть фундаментальное ограничение:

**RAG работает с «мешком кусков».** Он не знает, как куски связаны между собой.

```python
# RAG: нашёл 3 куска — склеил — отправил LLM
chunks = search(query)  # list[str], связи между кусками потеряны
context = "\n".join(chunks)
```

**GraphRAG** (Microsoft, 2024) решает эту проблему:

```
Текст: "DeepSeek выпустила R1 в 2025. R1 использует MoE."

RAG найдёт кусок с "R1" и кусок с "MoE".
GraphRAG построит: [DeepSeek] --выпустила--> [R1] --использует--> [MoE]

Вопрос: "Что использует DeepSeek R1?"
RAG: "R1 использует MoE" (если кусок попал в контекст)
GraphRAG: идёт по графу DeepSeek → R1 → MoE → MoE (всегда)
```

**Когда GraphRAG выигрывает:**
| Сценарий | RAG | GraphRAG |
|----------|-----|----------|
| «Найди документ про налоги» | ✅ | ✅ |
| «Как связаны модуль A и модуль B?» | ❌ | ✅ |
| «Почему этот код вызывает ошибку?» | ❌ | ✅ |
| «Какая архитектура у проекта?» | ❌ | ✅ |

---

## GRACE: GraphRAG для кода

**GRACE (Graph-RAG Anchored Code Engineering)** — реализация GraphRAG, заточенная под **анализ кодовой базы**. Её создал Владимир Иванов (@turboplanner).

### Чем GRACE отличается от обычного GraphRAG

Обычный GraphRAG строит граф из любых документов. GRACE строит граф **из кода**:

```
Исходный код:                    Граф GRACE:
                                ┌─────────────┐
src/                            │ auth.py      │
├── auth.py      ──────────────►│   ├── login()│
│   def login():  entities      │   ├── logout()│
│   def logout():              │   └── hash_pwd│
├── db.py         entities      ├─────────────┤
│   class DB:     ─────────────►│ db.py        │
│   def query():               │   ├── DB     │
└── config.py                   │   └── query()│
                                ├─────────────┤
                                │ config.py    │
                                └─────────────┘
                                
                                Связи:
                                auth.py ──imports──> db.py
                                auth.py ──imports──> config.py
```

**Типы узлов в графе GRACE:**

| Узел | Пример | Что содержит |
|------|--------|-------------|
| Модуль | `auth.py` | Весь файл как единица кода |
| Функция | `login()` | Сигнатура + документация |
| Класс | `class DB` | Сигнатура + docstring |
| Зависимость | `import db` | Ссылка на другой модуль |
| Конфиг | `.env`, `config.yaml` | Параметры окружения |

**Типы связей:**

| Связь | Значение |
|-------|----------|
| `—defines—>` | Модуль определяет функцию/класс |
| `—imports—>` | Зависимость от другого модуля |
| `—calls—>` | Вызов функции из другого модуля |
| `—inherits—>` | Наследование |
| `—references—>` | Упоминание сущности |

### Зачем это нужно

Агент, работающий с кодом через GRACE, может:

1. **Понять архитектуру проекта** — не читая каждый файл
2. **Найти все места, связанные с багом** — через граф зависимостей
3. **Не сломать соседний модуль** — видит, какие функции зависят от изменяемой
4. **Ответить на вопрос «почему»** — граф хранит не только что, но и как связано

```python
# Без GRACE: агент читает файлы вслепую
files = glob("**/*.py")
for f in files:
    content = read(f)
    # сам ищет связи в голове — ошибается

# С GRACE: агент получает граф
graph = grace_query("show dependencies for auth.py")
# → auth.py imports db.py, config.py
# → auth.py defines: login(), logout()
# → login() calls db.query()
```

---

## Как работает GRACE

### Шаг 1: Индексация кода

GRACE анализирует файлы проекта и строит граф:

```python
def index_project(project_path: str) -> Graph:
    """Строит граф кодовой базы."""
    graph = Graph()
    
    for file_path in glob(f"{project_path}/**/*.py"):
        module = parse_module(file_path)
        
        # Добавляем модуль как узел
        module_node = graph.add_node(
            id=file_path,
            type="module",
            content=module.text,
            embedding=embed(module.text)
        )
        
        # Добавляем функции как узлы
        for func in module.functions:
            func_node = graph.add_node(
                id=f"{file_path}::{func.name}",
                type="function",
                content=func.docstring or func.signature,
                embedding=embed(func.signature)
            )
            
            # Связь: модуль → функция
            graph.add_edge(module_node, func_node, type="defines")
        
        # Добавляем импорты как связи между модулями
        for imp in module.imports:
            target = find_module(imp, project_path)
            if target:
                graph.add_edge(module_node, target, type="imports")
    
    return graph
```

### Шаг 2: Query-тайм анкоринг

«Anchored» (пришвартованный) означает, что запрос агента **привязывается к конкретной точке графа**:

```python
def grace_query(graph: Graph, query: str) -> list[Node]:
    """
    1. Превращает запрос в embedding
    2. Находит стартовую точку в графе
    3. Идёт по связям на 1-2 уровня
    4. Возвращает релевантные узлы
    """
    # Semantic search по всем узлам
    start_nodes = graph.semantic_search(query, top_k=5)
    
    # Traverse: идём по связям
    result = set(start_nodes)
    for node in start_nodes:
        neighbors = graph.traverse(node, depth=2)
        result.update(neighbors)
    
    return list(result)
```

**Пример:** агент спрашивает «как работает логин?»

1. `start_node = graph.semantic_search("как работает логин")` → находит `auth.py`, `login()`
2. `graph.traverse(auth_node, depth=2)` → `auth.py imports db.py`, `auth.py imports config.py`
3. Результат: `[auth.py, login(), db.py, DB, query(), config.py]`

Агент получает не просто кусок текста, а **связный контекст**: модуль, его функции, зависимости, базу данных и конфиг.

### Шаг 3: Контекст для LLM

Собранные узлы превращаются в структурированный промпт:

```markdown
## Архитектура модуля auth.py

**Файл:** src/auth/auth.py
**Назначение:** аутентификация пользователей

**Функции:**
- `login(username, password)` → token
  - вызывает: db.query()
  - использует: config.SECRET_KEY
- `logout(token)` → None
- `hash_password(password)` → hash

**Зависимости:**
- `db.py` → DB.query() — проверка credentials
- `config.py` → SECRET_KEY — подпись токенов

**Где используется:**
- api/routes.py → login_route()
- tests/test_auth.py → test_login_success()
```

С таким контекстом LLM не гадает — она видит точную архитектуру.

---

## GRACE vs RAG: когда что

```python
# RAG — для вопросов по документации
context = rag_search("Как настроить деплой?")
# Ответ: "Используй docker-compose up"

# GRACE — для вопросов по коду
context = grace_query("Как связаны auth и db?")
# Ответ: файлы + функции + импорты + граф вызовов
```

| Сценарий | Инструмент |
|----------|-----------|
| «Найди в документации про API ключи» | RAG |
| «Почему этот тест падает?» | GRACE (связь тест → код) |
| «Что делает функция X?» | GRACE (функция + её вызовы) |
| «Напиши миграцию для БД» | GRACE (схема + зависимости) |
| «Какие есть альтернативы библиотеке Y?» | RAG |
| «Не сломается ли модуль A, если я изменю B?» | GRACE |

**Правило:** RAG — для знаний (документация, статьи, FAQ). GRACE — для кода (архитектура, импорты, вызовы).

---

## Интеграция GRACE в агента

```python
class GraceReActAgent:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.context = []
    
    def think(self, task: str):
        # 1. Получаем контекст из GRACE
        nodes = grace_query(self.graph, task)
        
        # 2. Строим промпт
        context = self._build_context(nodes)
        
        # 3. ReAct-цикл с граф-контекстом
        prompt = f"""
        Контекст кодовой базы:
        {context}
        
        Задача: {task}
        
        Думай и действуй шаг за шагом:
        """
        
        return llm.generate(prompt)
    
    def act(self, thought: str):
        # Агент может уточнять запрос к GRACE:
        if "#graph" in thought:
            nodes = grace_query(self.graph, thought)
            self.context.extend(nodes)
            return self.think(thought)
        
        # ... обычный цикл инструментов
```

Ключевое отличие: агент может делать `#graph`-запросы — уточнять архитектуру прямо во время работы, а не полагаться на предзагруженный контекст.

---

## Инструменты GRACE

| Инструмент | Описание |
|-----------|----------|
| [GRACE Marketplace](https://github.com/osovv/grace-marketplace) | Маркетплейс готовых GRACE-агентов |
| [grace-docx](https://github.com/xronocode/grace-docx) | Документация и bootstrap |

**Как начать:**

```bash
# 1. Склонировать marketplace
git clone https://github.com/osovv/grace-marketplace
cd grace-marketplace

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Запустить агента с GRACE
python agent.py --project /path/to/your/code
```

---

## Резюме

```
RAG 2.0:        rewrite → search → rerank → generate
                (для текстов, документации)

GraphRAG:       entities → relations → traverse → generate
                (когда важны связи между фактами)

GRACE:          parse code → build graph → anchor → traverse
                (когда работаешь с кодом)

GRACE — это не замена RAG, а дополнение.
RAG для знаний, GRACE для кода.
```

---

## Практическое задание

1. Установи GRACE из marketplace
2. Запусти на небольшом проекте (10-20 файлов)
3. Сравни: что GRACE находит такого, чего не нашёл бы RAG?
4. Попробуй интегрировать GRACE в ReAct-цикл агента

---

## Проверь себя

1. Чем GRACE отличается от обычного RAG?
2. Что значит «Anchored» в названии GRACE?
3. Какие типы узлов и связей строит GRACE?
4. В каких сценариях GRACE бесполезен?
5. Как GRACE помогает агенту не сломать соседний код?

---

## Ссылки и материалы

### GRACE и сообщество
- [GRACE Marketplace](https://github.com/osovv/grace-marketplace)
- [GRACE Docx (bootstrap)](https://github.com/xronocode/grace-docx/blob/main/grace-docx-bootstrap.md)
- Канал Владимира Иванова: https://t.me/turboproject

### GraphRAG — реальные технологии
- [Microsoft GraphRAG](https://www.microsoft.com/en-us/research/project/graphrag/) — оригинальная реализация от Microsoft Research (2024)
- [LightRAG](https://github.com/HKUDS/LightRAG) — лёгкая альтернатива на OpenAI-эмбеддингах
- [Nano-GraphRAG](https://github.com/gusye1234/nano-graphrag) — минималистичная реализация для изучения
- [Neo4j + LLM Graph Builder](https://neo4j.com/labs/genai-ecosystem/llm-graph-builder/) — построение графа знаний из неструктурированных данных

### Ключевые концепции
- [GraphRAG: Unlocking LLM Discovery on Narrative Private Data](https://arxiv.org/abs/2404.16130) — оригинальная статья Microsoft
- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130) — тот же подход, другая формулировка
- [Graph of Thoughts: Solving Elaborate Problems with Large Language Models](https://arxiv.org/abs/2308.09687) — альтернативный подход (GoT) для графовых рассуждений

### Внутренние ссылки
- [[03-memory-and-rag/02-rag-advanced]] — RAG 2.0 (урок 8)
- [[03-memory-and-rag/03-llm-wiki]] — LLM Wiki (урок 9)
- [[wiki/grace-discussion]] — обсуждение GRACE
