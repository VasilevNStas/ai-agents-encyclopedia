#!/usr/bin/env python3
"""Демонстрация: один скрипт — два вызова к разным моделям.

Это не про OpenCode. Это про то, как выглядит настоящий агент.

Использование:
    export DEEPSEEK_API_KEY="sk-..."
    python3 two_models_demo.py
    
Если нет ключа — скрипт покажет "как это работает" в симуляции.
"""

import json
import os
import sys
from urllib import request

# ─── Одна функция для любой модели OpenAI-совместимого API ────────

def ask_llm(model: str, prompt: str, api_key: str = None) -> str:
    """Вызвать любую LLM через совместимый API.

    Работает с: DeepSeek, OpenAI, Together, Groq, OpenRouter...
    """
    if not api_key:
        return None  # симуляция

    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
    }).encode()

    req = request.Request(
        "https://api.deepseek.com/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    resp = json.loads(request.urlopen(req).read())
    return resp["choices"][0]["message"]["content"]


# ─── Симуляция (без ключа) ────────────────────────────────────────

def simulate(model: str, prompt: str) -> str:
    """Имитация ответа LLM, когда нет API-ключа."""
    responses = {
        "reasoning": (
            "1. Пользователь просит функцию сортировки\n"
            "2. Нужно реализовать quicksort\n"
            "3. Также просит найти баг\n"
            "4. Баг: неверное имя переменной в config.py → main.py\n"
            "Вывод: нужны обе задачи"
        ),
        "compression": (
            "Пользователь попросил написать сортировку. "
            "Агент создал quicksort. "
            "Затем искал баг — нашёл опечатку DB_HOST → DBHOST в main.py. "
            "Исправлено."
        ),
    }

    if "сожми" in prompt.lower():
        return responses["compression"]
    return responses["reasoning"]


# ─── Главная логика ──────────────────────────────────────────────

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")

    # ШАГ 1: основная задача — дорогая модель (R1)
    print("=" * 60)
    print("Вызов 1: DeepSeek-R1 (рассуждение)")
    print("Стоимость: ~$2/M токенов")
    print("-" * 60)

    r1_prompt = (
        "Задача: напиши quicksort на Python. "
        "Плюс найди баг: переменная DB_HOST не доходит до main.py. "
        "Распиши ход мыслей."
    )

    r1_response = ask_llm("deepseek-reasoner", r1_prompt, api_key)
    if r1_response is None:
        r1_response = simulate("reasoning", r1_prompt)

    print(r1_response)
    print()

    # ШАГ 2: сжатие — дешёвая модель (V2)
    print("=" * 60)
    print("Вызов 2: DeepSeek-V2 (лёгкое сжатие)")
    print("Стоимость: ~$0.5/M токенов (в 4 раза дешевле R1)")
    print("-" * 60)

    v2_prompt = (
        "Сожми следующие размышления в 2-3 предложения. "
        "Только факты, без деталей:\n\n" + r1_response
    )

    v2_response = ask_llm("deepseek-chat", v2_prompt, api_key)
    if v2_response is None:
        v2_response = simulate("compression", v2_prompt)

    print(v2_response)
    print()

    # ИТОГ
    print("=" * 60)
    print("Один скрипт → два разных вызова → две модели")
    print(f"Первый вызов:   {len(r1_response)} символов (R1 — дорого)")
    print(f"Второй вызов:   {len(v2_response)} символов (V2 — дёшево)")
    print("=" * 60)


if __name__ == "__main__":
    main()
