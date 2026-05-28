---
created: 2026-05-09
tags: [course/prompt-engineering, structured-output, json, function-calling]
status: active
---

# Урок 23: Structured Output — JSON, Function Calling и Grammar

> [!quote] Ключевая идея
> LLM по умолчанию возвращает текст. Но для агента нужны **структурированные данные**: JSON с именами инструментов, аргументами, флагами. Structured Output — это способ заставить LLM вернуть то, что можно распарсить.

---

## Почему структура важна

```
❌ LLM вернула: "я думаю что баг в файле auth.py на строке 42"
   Парсер должен угадать: какой файл, какая строка

✅ LLM вернула: {"file": "auth.py", "line": 42, "severity": "high"}
   Парсер: готово, можно работать
```

Без структуры каждый ответ LLM — это текст, который нужно **парсить и угадывать**. Со структурой — данные готовы к использованию.

---

## JSON mode

Самый простой способ: попросить LLM вернуть JSON.

```python
prompt = """
Извлеки информацию из текста.
Ответь строго в JSON:

{
    "name": "<имя>",
    "age": <возраст>,
    "city": "<город>"
}

Текст: "Меня зовут Иван, мне 25 лет, я из Москвы"
"""

response = llm.generate(prompt, response_format={"type": "json_object"})
# {"name": "Иван", "age": 25, "city": "Москва"}
```

**Проблема:** LLM может «забыть» закрыть скобку или добавить лишний текст до/после JSON. Решение — `response_format` в API (поддерживают DeepSeek, OpenAI, Claude).

---

## Function Calling

Function Calling — это JSON mode, встроенный в API.

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Поиск файлов по glob-паттерну",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob-паттерн, например '**/*.py'"
                    },
                    "path": {
                        "type": "string",
                        "description": "Директория для поиска"
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]

# API сам вызывает функцию, парсить не нужно
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[{"role": "user", "content": "найди все Python файлы"}],
    tools=tools,
    tool_choice="auto"
)
```

**Преимущества:**
- Схема задаётся через JSON Schema — модель не может «ошибиться»
- API сам определяет, когда вызывать функцию
- Парсинг встроен в SDK

---

## JSON Schema для сложных форматов

```python
from pydantic import BaseModel

class BugReport(BaseModel):
    file: str
    line: int
    severity: str  # low, medium, high, critical
    description: str
    suggested_fix: str | None = None

class CodeReview(BaseModel):
    files_reviewed: list[str]
    bugs_found: list[BugReport]
    score: int  # 1-10
    summary: str

# LLM возвращает строго по схеме
review = llm.generate(
    prompt="Проверь код в src/auth.py",
    response_model=CodeReview  # библиотека instructor / outlines
)
```

---

## Grammar-based (llama.cpp)

Для локальных моделей — грамматика в GBNF формате:

```python
from llama_cpp import Llama

grammar = """
root ::= "{" ws "name" ws ":" ws string ws "," ws "age" ws ":" ws number ws "}"
ws ::= [ \t\n]*
string ::= "\"" [^\"]* "\""
number ::= [0-9]+
"""

llm = Llama(model_path="model.gguf")
response = llm.generate(
    prompt="Расскажи о себе",
    grammar=grammar
)
# {"name": "Alice", "age": 30} — гарантированно валидный JSON
```

---

## Ошибки Structured Output

### 1. Слишком сложная схема
```python
# ❌ 20 вложенных полей — модель путается
# ✅ 3-5 полей на уровень
```

### 2. Нет description для полей
```python
# ❌ Модель не понимает, что писать в поле
"data": {"type": "string"}

# ✅ Описание помогает модели
"data": {"type": "string", "description": "base64 encoded image"}
```

### 3. Обязательные поля без значений по умолчанию
```python
# ❌ Если обязательного поля нет — упадёт
"file": {"type": "string"}  # обязательно
# ✅ Опционально с fallback
"file": {"type": "string", "default": "unknown"}
```

---

## Резюме

```
Методы structured output:

1. JSON mode:     попросить LLM вернуть JSON (response_format)
2. Function       JSON Schema в API — модель вызывает функцию
   Calling:
3. Grammar-based: GBNF грамматика — для локальных моделей

Правила:
  - 3-5 полей на уровень
  - Description для каждого поля
  - Всегда указывай default для опциональных полей
  - Валидируй ответ после получения
```

---

## Практическое задание

1. Определи Pydantic-модель `BugReport` с полями: `file: str`, `line: int`, `severity: str` (low/medium/high/critical), `description: str`. Напиши промпт, который просит LLM вернуть JSON по этой схеме.

2. Перепиши вызов инструмента `search_files` через Function Calling: опиши JSON Schema с параметрами `pattern` (string, required) и `path` (string, optional). Вызови через SDK.

---

## Проверь себя

1. Чем JSON mode отличается от Function Calling?
2. Зачем нужен description для поля в JSON Schema?
3. В чём преимущество Grammar-based подхода?
4. Почему сложная схема (20 полей) — плохая идея?

---

## Ссылки

- [[06-prompt-engineering/02-few-shot-cot]] — предыдущий урок
- [[06-prompt-engineering/01-system-prompts]] — system prompt design
- Библиотека: [instructor](https://github.com/jxnl/instructor) — structured output для Python
