---
created: 2026-05-08
tags: [course/agent-patterns, tools, function-calling]
status: active
---

# Урок 6: Tool Use — как агент взаимодействует с миром

> [!quote] Ключевая идея
> Без инструментов LLM — это «говорящая голова», которая может только генерировать текст. Инструменты — это **органы чувств и руки** агента. Через них он читает файлы, пишет код, ищет в интернете и меняет реальность.

---

## Почему инструменты — это не «дополнительная фича»

LLM знает только то, что было в её обучающих данных (срез знаний на дату обучения). Она не может:

- Прочитать файл на твоём компьютере
- Выполнить код и увидеть результат
- Поискать в интернете свежую информацию
- Отправить запрос к API
- Изменить содержимое файла

**Всё это делают инструменты.** Без них агент — это красивый, но бесполезный собеседник.

---

## Как LLM вызывает инструменты

### Способ 1: Текстовый протокол (ReAct style)

LLM пишет вызов инструмента в тексте, парсер извлекает:

```
Action: search("погода Москва")
```

```python
def parse_action(text: str) -> tuple[str, dict]:
    """Извлекает вызов инструмента из текста."""
    import re
    match = re.search(r"Action:\s*(\w+)\((.*)\)", text)
    if match:
        name = match.group(1)
        args = eval("{" + match.group(2) + "}")  # упрощённо
        return name, args
    return None, None
```

### Способ 2: Function Calling (современный стандарт)

LLM возвращает структурированный JSON с именем функции и аргументами:

```python
# API-запрос
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[...],
    tools=[{
        "type": "function",
        "function": {
            "name": "search",
            "description": "Поиск в интернете",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос"
                    }
                },
                "required": ["query"]
            }
        }
    }]
)

# Ответ модели
# {
#   "tool_calls": [{
#     "id": "call_123",
#     "function": {
#       "name": "search",
#       "arguments": "{\"query\": \"погода Москва\"}"
#     }
#   }]
# }
```

**Function Calling надёжнее**, потому что:
- Формат жёстко задан схемой (JSON Schema)
- Модель не может «забыть» закрыть скобку
- Парсинг не ломается от опечаток в тексте

---

## Как проектировать инструменты

### Принципы хорошего инструмента:

```python
# ❌ Плохо: слишком широкий инструмент
tool = {
    "name": "execute",
    "description": "Выполняет любую команду",
    "parameters": {
        "command": {"type": "string"}
    }
}
# Агент может выполнить rm -rf / — и сделает это уверенно
```

```python
# ✅ Хорошо: узкий, безопасный, предсказуемый
tool = {
    "name": "search_files",
    "description": "Поиск файлов по имени (glob pattern). Безопасно: только чтение.",
    "parameters": {
        "pattern": {
            "type": "string",
            "description": "Glob-паттерн, например *.py",
            "pattern": "^[a-zA-Z0-9_*?.\\\\/]+$"  # ограничение
        },
        "path": {
            "type": "string",
            "description": "Директория для поиска"
        }
    }
}
```

### Правила проектирования:

| Правило | Почему |
|---------|--------|
| **Один инструмент — одно действие** | Агент должен выбирать осознанно |
| **Название говорит, что делает** | `delete_file()`, а не `modify()` |
| **Описание — контекст для модели** | Модель выбирает по description |
| **Параметры — с ограничениями** | regex, enum, min/max |
| **Возврат — структурирован** | JSON, а не просто "ok" |

---

## Категории инструментов

```
ЧТЕНИЕ (Read-Only)
├── search_files / glob     — поиск файлов
├── read_file               — чтение файлов
├── grep                    — поиск текста
├── query_database          — SQL/BQ запросы
├── web_search              — интернет
├── web_fetch               — конкретная страница
└── list_directory          — содержимое папки

ЗАПИСЬ (Write)
├── write_file              — создание/перезапись
├── edit_file               — замена фрагмента
├── create_directory        — создание папки
└── rename / move           — перемещение

ВЫЧИСЛЕНИЯ (Compute)
├── run_code                — Python/JS/Bash
├── calculate               — арифметика
└── chart / plot            — визуализация

ОПАСНЫЕ (Dangerous — требуют guardrails)
├── delete_file / rm        — удаление
├── execute_sql             — запись в БД
├── send_email              — отправка писем
├── deploy                  — деплой на сервер
└── sudo / admin            — привилегированные операции
```

---

## Tool Use + Memory = Agent

Когда инструменты соединяются с памятью, рождается архитектура:

```python
class AgentWithTools:
    def __init__(self):
        self.tools = self._register_tools()
        self.memory = ContextMemory(max_tokens=100_000)
    
    def _register_tools(self):
        return {
            # Read-only
            "grep": {"fn": grep, "type": "read"},
            "read": {"fn": read_file, "type": "read"},
            "glob": {"fn": glob_files, "type": "read"},
            # Write
            "write": {"fn": write_file, "type": "write"},
            "edit": {"fn": edit_file, "type": "write"},
            # Execute
            "bash": {"fn": run_bash, "type": "compute"},
            "python": {"fn": run_python, "type": "compute"},
        }
    
    def execute_tool(self, name: str, args: dict):
        tool = self.tools[name]
        
        # Read-only инструменты можно вызывать без подтверждения
        if tool["type"] in ("read", "compute"):
            return tool["fn"](**args)
        
        # Write и Dangerous — требуют подтверждения
        # (или guardrails — тема [[05-production/01-guardrails]])
        if self._confirm(f"Выполнить {name}?"):
            return tool["fn"](**args)
        return {"error": "cancelled"}
    
    def run(self, task: str):
        self.memory.add("user", task)
        
        for step in range(MAX_STEPS):
            response = llm.generate(
                self.memory.context(),
                tools=self.tools
            )
            
            if response.tool_call:
                result = self.execute_tool(
                    response.tool_call.name,
                    response.tool_call.args
                )
                self.memory.add("tool", result)
            else:
                return response.content
```

---

## Anti-patterns инструментов

### 1. Инструмент-швейцарский нож

```python
# ❌ Всё в одном
"do_anything": {
    "description": "Выполняет любую операцию",
    "parameters": {"code": {"type": "string"}}
}
```

Модель не понимает, когда и зачем его использовать. Лучше 10 узких инструментов, чем 1 широкий.

### 2. Инструмент без описания

```python
# ❌ Модель не знает, зачем этот инструмент
"fx": { "parameters": {...} }
# vs
"calculate_tax": { 
    "description": "Рассчитывает налог на прибыль по ставке 20%",
    "parameters": {...}
}
```

Описание — это единственный способ модели понять, для чего инструмент.

### 3. Слишком много инструментов

Если у агента 50+ инструментов, модель тратит токены на их перебор. **Лимит:** 10-15 на одного агента. Если нужно больше — группируй в под-агентов (тема [[04-multi-agent/01-orchestration]]).

### 4. Инструмент без валидации результата

```python
# ❌
result = bash("rm -rf /project")  # модель могла ошибиться
return result

# ✅
result = bash("rm -rf /project")
if "error" in result.lower() or not result:
    return {"error": "опасная операция заблокирована"}
if "project" not in result:  # проверка: удалили то, что нужно?
    return {"warning": "результат не соответствует ожиданиям"}
return result
```

---

## Как OpenCode использует инструменты (пример)

Весь этот диалог — демонстрация Tool Use. Каждый раз, когда я:

- `grep("agent", "*.md")` — вызываю инструмент **grep**
- `read("01-fundamentals/")` — вызываю инструмент **read**
- `write("assets/report.txt")` — вызываю инструмент **write**

— я использую тот же паттерн Function Calling/Tool Use, который описан в этом уроке.

---

## Резюме

```
Инструменты — это «руки» агента.
Без них — LLM может только говорить.
С ними — LLM может читать, писать, считать, искать и менять мир.

Правило: один инструмент — одно действие.
         узкий инструмент лучше широкого.
         описание важнее названия.
```

---

## Практическое задание

Посмотри на инструменты, которые были использованы в этом диалоге (grep, read, write, glob, bash). Попробуй определить:

1. Какие из них read-only, какие write?
2. Какие требуют guardrails?
3. Как бы ты спроектировал инструмент `edit_file` так, чтобы он был безопасным?

---

## Проверь себя

1. Чем Function Calling отличается от текстового протокола ReAct?
2. Почему инструмент должен быть узким, а не «швейцарским ножом»?
3. Какие 3 метаданных должны быть у каждого инструмента?
4. Почему read-only инструменты безопаснее write?

---

## Ссылки

- Спецификация: [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- Toolformer: [LLMs Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761)
- Назад: [[02-agent-patterns/02-reflexion]]
- Дальше: [[03-memory-and-rag/01-memory-types]] — три слоя памяти агента
