---
created: 2026-05-08
tags: [course/multi-agent, anti-patterns, architecture]
status: active
---

# Урок 14: Антипаттерны мультиагентных систем

> [!quote] Ключевая идея
> Мультиагентные системы — это сила, но и источник новых видов ошибок. Лучше учиться на чужих ошибках, чем на своих.

---

## Антипаттерн №1: Слишком много агентов

```python
# ❌ 20 агентов для задачи «напиши hello world»
agents = [CodeAgent(), TestAgent(), ReviewAgent(), LintAgent(),
          DocAgent(), DeployAgent(), MonitorAgent(), ...]
```

**Проблема:** каждый агент жрёт контекст, время и деньги. 90% из них будут просто ждать.

**Решение:** начинай с одного агента. Добавляй нового ТОЛЬКО когда есть конкретная причина:

```
1 агент  → не справляется? → 2 агента (разделение труда)
2 агента → путаются?       → Supervisor
Supervisor → тормозит?      → асинхронная коммуникация
```

---

## Антипаттерн №2: Агент-дублер

```
CodeAgent 1: пишет функцию
CodeAgent 2: пишет ту же функцию (не знает, что Agent1 уже пишет)
```

**Проблема:** два агента делают одно и то же. Удвоенный расход токенов, конфликты при merge.

**Решение:** каждая задача имеет владельца. Supervisor назначает и не дублирует.

```python
task_registry = {}

def assign_task(task_id: str, description: str, agent_name: str):
    """Назначает задачу агенту. Если задача уже назначена — ошибка."""
    if task_id in task_registry:
        raise ValueError(f"Задача {task_id} уже выполняется {task_registry[task_id]}")
    task_registry[task_id] = agent_name
```

---

## Антипаттерн №3: Агенты ждут друг друга (deadlock)

```
Agent1: ждёт результат Agent2
Agent2: ждёт результат Agent1
→ оба ждут вечно
```

**Проблема:** циклическая зависимость. Никто не работает.

**Решение:** граф зависимостей + timeout.

```python
# Обнаружение циклических зависимостей
def detect_cycle(dependencies: dict[str, list[str]]) -> bool:
    """DFS на циклы в графе зависимостей агентов."""
    visited = set()
    in_stack = set()

    def dfs(node):
        if node in in_stack:
            return True  # cycle found
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for dep in dependencies.get(node, []):
            if dfs(dep):
                return True
        in_stack.remove(node)
        return False

    for node in dependencies:
        if dfs(node):
            return True
    return False
```

---

## Антипаттерн №4: Все агенты имеют доступ ко всему

```
CodeAgent: может деплоить, может удалять файлы, может писать в БД
DebugAgent: может деплоить
TestAgent: может деплоить
```

**Проблема:** если один агент скомпрометирован или ошибается — ущерб максимален.

**Решение:** принцип минимальных привилегий (least privilege):

```python
AGENT_PERMISSIONS = {
    "code_agent":  ["read", "write", "git_commit"],
    "debug_agent": ["read", "grep", "run_tests"],
    "deploy_agent": ["deploy", "restart", "rollback"],
    "test_agent":  ["read", "run_tests", "write_test_files"],
}
```

Каждый агент имеет доступ ТОЛЬКО к тому, что нужно для его работы.

---

## Антипаттерн №5: Потеря контекста при передаче

```
Agent1 (знает: "баг в auth.py:42") → передаёт Agent2
Agent2 (видит: "почини баг") ← контекст потерян
Agent2 ищет баг заново → тратит токены
```

**Решение:** передавать контекст явно и структурированно:

```python
handoff = {
    "task": "fix bug in auth.py:42",
    "context": {
        "what_is_broken": "token validation skipped before DB query",
        "already_tried": ["checked line 40-45", "confirmed bug exists"],
        "relevant_files": ["auth.py:42", "db.py:15"],
        "suggested_fix": "add `if not token: return 401` at line 40"
    },
    "constraints": {
        "must_pass_tests": True,
        "no_new_dependencies": True
    }
}
```

---

## Антипаттерн №6: Нет мониторинга

```python
while True:
    agent.run(task)  # никто не смотрит, что происходит
```

Агент может:
- Зациклиться
- Сжечь $1000 за минуту
- Удалить важные файлы
- Выдать неверный ответ, который никто не проверит

**Решение:** observability ([[05-production/02-observability]])

---

## Резюме

```
Топ-6 антипаттернов мультиагентных систем:

1. Слишком много агентов     → начинай с 1, добавляй по необходимости
2. Агент-дублёр              → task registry, каждая задача — один владелец
3. Deadlock (ждут друг друга) → граф зависимостей + timeout
4. Всё доступно всем         → least privilege для каждого агента
5. Потеря контекста          → структурированный handoff
6. Нет мониторинга           → observability
```

---

## Практическое задание

Проанализируй код ниже и исправь в нём антипаттерны:

```python
# Код с антипаттернами
class BuggySystem:
    def __init__(self):
        self.agents = [Agent() for _ in range(10)]
        self.results = []

    def run_all(self, task):
        for agent in self.agents:
            result = agent.run(task)  # все делают одно и то же
            self.results.append(result)

    def deploy(self):
        self.agents[0].deploy()  # всё доступно всем
```

1. Найди в коде минимум 3 антипаттерна из урока
2. Перепиши код, исправив их:
   - Уменьши количество агентов до необходимого минимума
   - Добавь task registry для исключения дублирования
   - Реализуй принцип минимальных привилегий
3. Добавь timeout на выполнение задачи и fallback

Требования: исправленный код должен быть рабочим, каждый антипаттерн — явно устранён с комментарием.

---

## Проверь себя

1. Какие 6 антипаттернов мультиагентных систем описаны в уроке?
2. Почему начинать нужно с 1 агента, а не с 10?
3. Как обнаружить циклическую зависимость между агентами?
4. Какой принцип защищает от катастрофы, если один агент ошибся?

---

## Ссылки

- Назад: [[04-multi-agent/02-communication]]
- Дальше: [[05-production/01-guardrails]]
