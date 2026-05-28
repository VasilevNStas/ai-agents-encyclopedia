#!/usr/bin/env python3
"""Демонстрация: JSON mode vs Function Calling — разница в ответах.

Запуск:
    export DEEPSEEK_API_KEY="sk-..."
    python3 structured_output_demo.py
"""

import json
import os
import sys
from urllib import request

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"


def call_deepseek(messages, **kwargs):
    """Прямой вызов DeepSeek API."""
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0,
        **kwargs,
    }

    req = request.Request(
        API_URL,
        data=json.dumps(data).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    resp = json.loads(request.urlopen(req).read())
    return resp["choices"][0]["message"]


def demo_json_mode():
    """JSON mode — просим модель вернуть JSON."""
    print("=" * 60)
    print("1. JSON MODE")
    print("   Просим модель вернуть JSON в тексте")
    print("   Надёжность: 60-80%")
    print("=" * 60)

    messages = [
        {
            "role": "user",
            "content": (
                "Извлеки информацию из текста и верни строго в JSON:\n"
                "{\n"
                '  "name": "<имя>",\n'
                '  "age": <возраст>,\n'
                '  "city": "<город>"\n'
                "}\n\n"
                'Текст: "Меня зовут Иван, мне 25 лет, я из Москвы"'
            ),
        }
    ]

    response = call_deepseek(messages)

    print(f"Ответ модели (raw):\n{response['content']}\n")

    # Пробуем распарсить
    try:
        text = response["content"].strip()
        # Ищем JSON в тексте
        if "{" in text:
            json_start = text.index("{")
            json_end = text.rindex("}") + 1
            parsed = json.loads(text[json_start:json_end])
            print(f"Распарсено: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ JSON не найден в ответе")
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ Ошибка парсинга: {e}")

    print()


def demo_function_calling():
    """Function Calling — модель возвращает строгий вызов."""
    print("=" * 60)
    print("2. FUNCTION CALLING")
    print("   Модель возвращает структурированный tool_call")
    print("   Надёжность: 99%+")
    print("=" * 60)

    messages = [
        {
            "role": "user",
            "content": 'Извлеки информацию: "Меня зовут Анна, мне 30 лет, я из Казани"',
        }
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_person",
                "description": "Извлекает имя, возраст и город из текста",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Имя человека"},
                        "age": {
                            "type": "integer",
                            "description": "Возраст в годах",
                        },
                        "city": {
                            "type": "string",
                            "description": "Город проживания",
                        },
                    },
                    "required": ["name", "age", "city"],
                },
            },
        }
    ]

    response = call_deepseek(messages, tools=tools, tool_choice="auto")

    if response.get("tool_calls"):
        tc = response["tool_calls"][0]
        print(f"Имя функции: {tc['function']['name']}")
        print(f"Аргументы (raw): {tc['function']['arguments']}")
        parsed = json.loads(tc["function"]["arguments"])
        print(f"Распарсено: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
        print(f"Тип age: {type(parsed['age']).__name__} (integer — как в схеме)")
    else:
        print(f"❌ tool_calls нет. Ответ: {response['content'][:100]}")
    print()


def main():
    if not API_KEY:
        print("❌ Установи DEEPSEEK_API_KEY")
        print("   export DEEPSEEK_API_KEY='sk-...'")
        sys.exit(1)

    demo_json_mode()
    demo_function_calling()

    print("=" * 60)
    print("ИТОГ:")
    print("  JSON mode:        ответ — текст, парсинг — твоя забота")
    print("  Function Calling: ответ — структура, парсинг — API")
    print("=" * 60)


if __name__ == "__main__":
    main()
