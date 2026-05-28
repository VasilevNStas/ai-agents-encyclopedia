#!/usr/bin/env python3
"""
token_watch.py — наблюдение и управление контекстным окном агента

Использование:
  python token_watch.py                    # интерактивная демонстрация
  python token_watch.py --monitor          # режим реального времени
  python token_watch.py "текст"            # посчитать токены в тексте

Зависимости: tiktoken (опционально, без него — приблизительный подсчёт)
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# ─── Конфигурация ──────────────────────────────────────────────────

# Лимиты для popular моделей (в токенах)
MODEL_LIMITS = {
    "gpt-4": 8_192,
    "gpt-4-turbo": 128_000,
    "gpt-4o": 128_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "deepseek-v2": 128_000,
    "deepseek-r1": 128_000,
    "gemini-1.5-pro": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
}

SYSTEM_PROMPT_TEMPLATE = """
Ты — полезный ассистент. Отвечай на русском языке.
Контекст предыдущих шагов:
{compressed_history}
"""

# Пороги срабатывания (в процентах от лимита)
WARN_AT_PCT = 0.7   # 70% — предупреждение
CRIT_AT_PCT = 0.85  # 85% — критично, пора сжимать
MAX_AT_PCT = 0.95   # 95% — стоп, больше некуда

# ─── Подсчёт токенов ──────────────────────────────────────────────

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Подсчёт токенов. С tiktoken — точно, без — приблизительно."""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except (ImportError, KeyError):
        # Приблизительно: 1 токен ≈ 0.75 слова для EN, ~0.5 для RU
        # Консервативная оценка: 4 символа на токен
        return len(text) // 4


def count_messages_tokens(messages: list[dict], model: str = "gpt-4") -> int:
    """Подсчёт токенов в списке сообщений (формат OpenAI)."""
    total = 0
    for msg in messages:
        total += count_tokens(json.dumps(msg, ensure_ascii=False), model)
        # Overhead на роль сообщения (system/user/assistant/tool)
        total += 4
    return total + 3  # overhead на общий запрос


# ─── Монитор контекста ────────────────────────────────────────────

@dataclass
class ContextMonitor:
    """Следит за контекстным окном и подсказывает, когда сжимать."""

    model: str = "deepseek-v2"
    messages: list[dict] = field(default_factory=list)
    max_tokens: int = None
    _last_count: int = 0

    def __post_init__(self):
        self.max_tokens = MODEL_LIMITS.get(self.model, 128_000)

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    @property
    def used(self) -> int:
        self._last_count = count_messages_tokens(self.messages, self.model)
        return self._last_count

    @property
    def pct(self) -> float:
        return self.used / self.max_tokens

    @property
    def status(self) -> str:
        p = self.pct
        if p >= MAX_AT_PCT:
            return "🔴 CRITICAL"
        if p >= CRIT_AT_PCT:
            return "🟠 COMPRESS"
        if p >= WARN_AT_PCT:
            return "🟡 WARN"
        return "🟢 OK"

    def summary(self) -> str:
        return (
            f"[{self.status}] {self.used:>7,} / {self.max_tokens:,} токенов "
            f"({self.pct:.1%}) — модель {self.model}"
        )

    def should_compress(self) -> bool:
        return self.pct >= CRIT_AT_PCT

    def compress(self, keep_last: int = 5) -> str:
        """Сжимает историю: заменяет старые сообщения на резюме.

        Возвращает сообщение, которое нужно показать LLM с просьбой
        сжать историю. Само сжатие делает LLM — мы только просим.
        """
        if len(self.messages) <= keep_last + 1:
            return None  # нечего сжимать

        # Старые сообщения (все, кроме keep_last последних и system prompt)
        old = self.messages[1:-keep_last] if self.messages[0]["role"] == "system" else self.messages[:-keep_last]

        summary_prompt = {
            "role": "system",
            "content": (
                "Сожми следующие сообщения в краткое резюме (макс 300 токенов). "
                "Сохрани: какие инструменты вызывались, какие результаты получены, "
                "какие решения приняты. Только факты, без воды.\n\n"
                + json.dumps(old, ensure_ascii=False, indent=2)
            ),
        }
        return summary_prompt

    def apply_compression(self, summary: str, keep_last: int = 5):
        """Применяет сжатие: заменяет старые сообщения на резюме."""
        system = self.messages[0] if self.messages[0]["role"] == "system" else None
        last_msgs = self.messages[-keep_last:] if system else self.messages[-keep_last:]

        compressed = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(compressed_history=summary)}]

        if system and system["role"] == "system":
            compressed[0] = system  # сохраняем оригинальный system prompt
            # добавляем compressed history отдельным сообщением
            compressed.append({"role": "system", "content": f"Сжатая история: {summary}"})

        compressed.extend(last_msgs)
        self.messages = compressed


# ─── Демонстрация ──────────────────────────────────────────────────

def demo():
    """Показывает работу token_watch на симулированном диалоге."""
    monitor = ContextMonitor(model="deepseek-v2")
    monitor.add("system", "Ты — ассистент для кодинга.")

    print("=" * 60)
    print("Демонстрация ContextMonitor")
    print("=" * 60)
    print()
    print(f"Модель: {monitor.model}")
    print(f"Лимит:  {monitor.max_tokens:,} токенов")
    print(f"Пороги: WARN={WARN_AT_PCT:.0%}, COMPRESS={CRIT_AT_PCT:.0%}, CRITICAL={MAX_AT_PCT:.0%}")
    print()

    # Симулируем диалог: добавляем сообщения, пока не достигнем лимита
    dummy_messages = [
        ("user", "Напиши функцию для сортировки массива"),
        ("assistant", "Вот функция сортировки пузырьком:\n\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr"),
        ("tool", '{"result": "success", "lines": 8}'),
        ("user", "А теперь оптимизируй до O(n log n)"),
        ("assistant", "Вот быстрая сортировка:\n\ndef quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr)//2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)"),
    ]

    for role, content in dummy_messages:
        monitor.add(role, content)
        print(f"  + {role}: {content[:50]}...")
        print(f"  {monitor.summary()}\n")

    # Симулируем много вызовов инструментов (раздувание контекста)
    print("--- Раздуваем контекст вызовами инструментов ---")
    for i in range(15):
        tool_result = json.dumps({
            "file_read": f"/src/module_{i}.py",
            "lines": i * 100,
            "content": f"# module_{i}\n" * 50,
        }, ensure_ascii=False)
        monitor.add("tool", tool_result)
        print(f"  Шаг {i+1}: {monitor.summary()}")

        if monitor.should_compress():
            print()
            print("  ⚡ Нужно сжатие! Статус CRITICAL или COMPRESS.")
            print(f"  → Запрос к LLM на сжатие истории...")
            compression_prompt = monitor.compress(keep_last=3)
            if compression_prompt:
                print(f"  → LLM вернула сжатое резюме (имитация)")
                monitor.apply_compression(
                    "Пользователь просил написать и оптимизировать функции сортировки. "
                    "Были созданы bubble_sort и quick_sort. Вызовы инструментов: read_file "
                    "для модулей 0-9. Агент анализировал код.",
                    keep_last=3,
                )
                print(f"  → После сжатия: {monitor.summary()}")
            print()

    print()
    print("=" * 60)
    print("Итог: контекст управляется, лимит не превышен")
    print("=" * 60)


# ─── Мониторинг в реальном времени ────────────────────────────────

def live_monitor():
    """Режим реального времени: вводишь текст — видишь токены."""
    print("Режим мониторинга. Вводи текст (Ctrl+C для выхода):")
    print()

    total = 0
    model = os.environ.get("TOKEN_MODEL", "deepseek-v2")
    limit = MODEL_LIMITS.get(model, 128_000)

    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            tokens = count_tokens(line.rstrip(), model)
            total += tokens
            pct = total / limit
            bar = "█" * int(pct * 40) + "░" * (40 - int(pct * 40))

            if pct >= CRIT_AT_PCT:
                status = "🟠 COMPRESS"
            elif pct >= WARN_AT_PCT:
                status = "🟡 WARN"
            else:
                status = "🟢 OK"

            print(f"\r  [{status}] {bar} {total:>7,}/{limit:,} ({pct:.1%})", end="")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print()

    print(f"\nВсего: {total:,} токенов (модель: {model})")


# ─── CLI ───────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="token_watch — управление контекстным окном агента",
    )
    parser.add_argument("text", nargs="?", help="Текст для подсчёта токенов")
    parser.add_argument("--monitor", action="store_true", help="Режим мониторинга в реальном времени")
    parser.add_argument("--model", default="deepseek-v2", choices=list(MODEL_LIMITS.keys()), help="Модель")
    parser.add_argument("--demo", action="store_true", help="Демонстрация")

    args = parser.parse_args()

    if args.demo:
        return demo()
    if args.monitor:
        return live_monitor()
    if args.text:
        tokens = count_tokens(args.text, args.model)
        limit = MODEL_LIMITS.get(args.model, 128_000)
        print(f"{tokens:,} токенов ({tokens/limit:.1%} от лимита {args.model})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
