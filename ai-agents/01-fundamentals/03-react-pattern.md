---
created: 2026-05-08
tags: [course/fundamentals, react, pattern, agent]
status: active
---

# Урок 3: Паттерн ReAct — Reasoning + Acting

> [!quote] Основа
> **ReAct** (Yao et al., 2022) — паттерн, в котором LLM **чередует рассуждения (Reasoning) и действия (Acting)** в одном цикле. Это базовый паттерн, на котором построены все современные агенты.

---

## Проблема, которую решает ReAct

До ReAct агенты работали по схеме: **Plan → Act**, то есть:
1. LLM составляет план действий
2. Выполняет все шаги плана
3. Возвращает результат

**Проблема:** план может быть неверным, а обратиться к плану и скорректировать его по ходу — нельзя.

ReAct предлагает другой подход: **рассуждай → действуй → наблюдай → рассуждай снова**.

---

## Как работает ReAct

```
Thought:  Мне нужно узнать погоду в Москве. Для этого я воспользуюсь поиском.
Action:   search(query="погода Москва сегодня")
Observation: "Москва, +15°C, облачно"
Thought:  Теперь, когда я знаю погоду, могу ответить пользователю.
Action:   answer("В Москве сегодня +15°C и облачно.")
```

Три ключевых элемента:

| Элемент | Формат | Описание |
|---------|--------|----------|
| **Thought** | `Thought: ...` | Рассуждение агента «вслух». Почему он делает то, что делает |
| **Action** | `Action: tool_name(args)` | Конкретный вызов инструмента |
| **Observation** | Результат тула | Что вернул инструмент (обычно не генерируется LLM, а приходит извне) |

### Формально:

```python
# Цикл ReAct
def react_loop(task: str, max_iterations=10):
    context = f"Задача: {task}\n\n"
    
    for i in range(max_iterations):
        # 1. LLM генерирует Thought + Action
        response = llm.generate(context + "Thought: ")
        
        thought = extract_thought(response)  # "Нужно найти файл..."
        action = extract_action(response)    # "grep('db_password')"
        
        if action is None:
            # Ответ готов
            return response
        
        # 2. Выполняем действие
        observation = execute_tool(action)
        
        # 3. Добавляем результат в контекст
        context += f"Thought: {thought}\n"
        context += f"Action: {action}\n"
        context += f"Observation: {observation}\n"
    
    return "Max iterations reached"
```

---

## ReAct vs. Plan-then-Execute

| Критерий | Plan → Execute | ReAct |
|----------|---------------|-------|
| Гибкость | Жёсткий план | Адаптивный цикл |
| Устойчивость к ошибкам | Низкая (ошибка в плане = провал) | Высокая (можно скорректировать) |
| Расход токенов | Меньше (один план) | Больше (итеративный цикл) |
| Скорость | Быстрее | Медленнее |
| Предсказуемость | Выше | Ниже |
| Сложность отладки | Проще | Сложнее (длинные логи) |

> [!important] Когда что использовать
> - **Plan → Execute**: задачи, где все шаги известны заранее (сборка проекта, деплой)
> - **ReAct**: задачи, где нужно исследовать, искать, пробовать (debugging, research, анализ)

---

## ReAct в современном API (Function Calling)

Современные LLM реализуют ReAct через **structured output / function calling**:

```python
# Современный ReAct (через API)
import json

messages = [
    {"role": "system", "content": "Ты — агент. Используй инструменты."},
    {"role": "user", "content": "Найди файлы, где есть слово 'password'"}
]

while True:
    response = client.chat.completions.create(
        model="deepseek-reasoner",  # или gpt-4, claude-3
        messages=messages,
        tools=TOOLS,  # список функций
        tool_choice="auto"
    )
    
    msg = response.choices[0].message
    
    if msg.tool_calls:
        for tc in msg.tool_calls:
            # Выполняем инструмент
            args = json.loads(tc.function.arguments)
            result = glob.glob(args["pattern"])
            
            # Добавляем результат в контекст
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str)
            })
    else:
        # Финальный ответ
        print(msg.content)
        break
```

---

## Пример: ReAct-агент для поиска багов

Представь, что ты даёшь агенту задачу: *«Найди, почему падает тест test_login_flow»*.

```
Thought: Нужно найти файл с тестом test_login_flow.
Action: grep("test_login_flow", path="tests/")
Observation: tests/test_auth.py:42: def test_login_flow():

Thought: Теперь прочитаю тест и найду ошибку.
Action: read("tests/test_auth.py", offset=42, limit=30)
Observation: def test_login_flow():
    user = create_user()
    response = client.login(user.email, "wrong_pass")
    assert response.status_code == 200  # <-- БАГ: wrong_pass, а ждёт 200

Thought: Ошибка найдена. Тест использует wrong_pass, но ожидает status 200.
Должен ожидать 401. Исправлю.
Action: replace("tests/test_auth.py", 
  "assert response.status_code == 200",
  "assert response.status_code == 401")

Thought: Исправление готово. Сообщу пользователю.
Final: Ошибка найдена в tests/test_auth.py:47 — wrong_pass ожидает 200, исправил на 401.
```

Это и есть ReAct в действии: **думает → ищет → читает → анализирует → исправляет → сообщает**.

---

## Ограничения ReAct

1. **Дорого.** Каждый шаг = вызов LLM. 10 шагов = 10 вызовов
2. **Потеря фокуса.** Без хорошего system prompt агент может «зациклиться» или уйти не в ту сторону
3. **Нет стратегического планирования.** ReAct хорош в тактике («что делать на этом шаге»), но плох в стратегии («какой общий план из 10 шагов»)
4. **Чувствителен к формату.** Если модель не умеет в форматированный вывод (JSON), ReAct сломается

**Решение для проблемы 3:** Plan-and-Solve — сначала составить план, потом выполнять шаги ReAct. Тема [[02-agent-patterns/01-plan-and-solve]].

---

## Резюме

```
ReAct = Reasoning + Acting в одном цикле

Thought → Action → Observation → Thought → Action → ... → Final Answer

Плюсы: гибкость, устойчивость к ошибкам, адаптивность
Минусы: дорого, нет стратегического планирования, чувствителен к формату
```

---

## Практическое задание

Попробуй дать своему агенту (OpenCode) задачу, которая требует **минимум 3 шага**:

```
Найди все файлы с расширением .py, подсчитай в них строки кода,
выяви файл с максимальным количеством строк,
и запиши результат в файл report.txt
```

Обрати внимание на **Thought** агента — видно ли, как он рассуждает? Если нет — попроси его «думать вслух».

---

## Проверь себя

1. Какие три элемента образуют цикл ReAct?
2. Почему ReAct лучше Plan→Execute для исследовательских задач?
3. В чём главный недостаток ReAct?
4. Какой паттерн решает проблему отсутствия стратегического планирования в ReAct?

---

## Дополнительные материалы

- Оригинальная бумага: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (Yao et al., 2022)
- Больше о паттернах: [[02-agent-patterns/01-plan-and-solve]]
