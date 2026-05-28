#!/usr/bin/env python3
"""
Build Your Agent — конструктор ReAct-агента из 150 строк.

Этот скрипт собирает полноценного агента с нуля:
  - System prompt
  - ReAct цикл (Thought → Action → Observation)
  - 4 инструмента (grep, read, write, python)
  - Память (short-term + working)
  - Guardrails
  - Observability (лог + cost)

Использование:
  export DEEPSEEK_API_KEY="sk-..."
  python3 build_your_agent.py "найди все .py файлы и посчитай строки"

Без API-ключа работает в режиме симуляции.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

# ─── 1. КОНФИГУРАЦИЯ ──────────────────────────────────────────────

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = "deepseek-chat"
MAX_STEPS = 15
MAX_COST = 0.10  # бюджет сессии

# ─── 2. ИНСТРУМЕНТЫ ───────────────────────────────────────────────

def tool_grep(pattern: str, path: str = ".") -> str:
    """Поиск текста в файлах."""
    import subprocess
    try:
        result = subprocess.run(
            ["grep", "-rn", pattern, path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return "\n".join(lines[:20])  # max 20 строк
        return "ничего не найдено"
    except Exception as e:
        return f"ошибка: {e}"


def tool_read(path: str) -> str:
    """Чтение файла."""
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"ошибка: {e}"


def tool_write(path: str, content: str) -> str:
    """Запись файла (с подтверждением)."""
    print(f"\n  ⚠ write({path}) — подтвердите (y/n): ", end="")
    confirm = input()
    if confirm.lower() != "y":
        return "отменено пользователем"
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"записано {len(content)} символов"
    except Exception as e:
        return f"ошибка: {e}"


def tool_python(code: str) -> str:
    """Выполнение Python кода."""
    try:
        local_vars = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)
        # Возвращаем результат, если есть
        result = [v for v in local_vars.values()
                  if not v.__class__.__name__.startswith("__")]
        return str(result[-1]) if result else "код выполнен"
    except Exception as e:
        return f"ошибка: {e}"


TOOLS = {
    "grep": {"fn": tool_grep, "type": "read",
             "description": "Поиск текста в файлах (grep). Чтение — безопасно."},
    "read": {"fn": tool_read, "type": "read",
             "description": "Чтение содержимого файла. Чтение — безопасно."},
    "write": {"fn": tool_write, "type": "write",
              "description": "Запись файла. Требует подтверждения пользователя."},
    "python": {"fn": tool_python, "type": "compute",
               "description": "Выполнение Python кода. Вычисления."},
}

# ─── 3. GUARDRAILS ────────────────────────────────────────────────

DANGEROUS_COMMANDS = ["rm ", "sudo ", "eval(", "exec(", "__import__"]
BLOCKED_PATHS = ["/etc", "/usr", "/bin", "~/.ssh", "~/.aws"]


def guardrail_tool(name: str, args: dict) -> tuple[bool, str]:
    """Проверка безопасности перед выполнением инструмента."""

    if name == "write":
        path = args.get("path", "")
        for blocked in BLOCKED_PATHS:
            if blocked in os.path.expanduser(path):
                return False, f"путь {blocked} заблокирован"
        return True, "allow"

    if name == "python":
        code = args.get("code", "")
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in code:
                return False, f"команда {dangerous} заблокирована"
        return True, "allow"

    return True, "allow"


def sanitize_output(name: str, result: str) -> str:
    """Фильтр на выходе: скрываем потенциальные секреты."""
    # Скрываем длинные строки, похожие на ключи
    if re.search(r"[A-Za-z0-9_-]{40,}", result):
        return "[возможный секрет скрыт]"
    return result


# ─── 4. ПАМЯТЬ (Short-term + Working) ────────────────────────────

@dataclass
class AgentStep:
    step: int
    thought: str
    action: str
    action_args: dict
    observation: str
    cost: float
    duration_ms: int
    guardrail: str


class AgentMemory:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.short_term = []      # messages[]
        self.working = {"task": "", "plan": [], "step": 0}
        self.steps: list[AgentStep] = []
        self.total_cost = 0.0

    def build_context(self) -> list[dict]:
        """Собирает messages[] для запроса к LLM."""
        context = [{"role": "system", "content": self.system_prompt}]

        # Working memory как контекст
        if self.working["plan"]:
            context.append({
                "role": "system",
                "content": f"План: {json.dumps(self.working['plan'])}"
            })

        # Short-term (последние 20 сообщений)
        context.extend(self.short_term[-20:])
        return context

    def add_message(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content})

    def log_step(self, step: AgentStep):
        self.steps.append(step)
        self.total_cost += step.cost

    def summary(self) -> str:
        total_duration = sum(s.duration_ms for s in self.steps)
        return f"""
═══════════════════════════════════════
  Agent Session Summary
═══════════════════════════════════════
  Steps:    {len(self.steps)}
  Duration: {total_duration / 1000:.1f}s
  Cost:     ${self.total_cost:.4f}
  Tools:    {', '.join(s.action for s in self.steps)}
"""


# ─── 5. LLM ВЫЗОВ ────────────────────────────────────────────────

def call_llm(messages: list[dict]) -> str:
    """Вызов DeepSeek API или симуляция."""

    if not API_KEY:
        return simulate_llm(messages)

    from urllib import request

    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.3,
    }).encode()

    req = request.Request(
        "https://api.deepseek.com/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    resp = json.loads(request.urlopen(req).read())
    return resp["choices"][0]["message"]["content"]


def simulate_llm(messages: list[dict]) -> str:
    """Симуляция LLM без API-ключа."""
    last_msg = messages[-1]["content"].lower() if messages else ""

    if "grep" in last_msg or "найди" in last_msg or "поищи" in last_msg:
        return "Thought: Нужно найти файлы. Использую grep.\nAction: grep('TODO')"
    if "read" in last_msg or "прочитай" in last_msg:
        return "Thought: Прочитаю файл.\nAction: read('example.py')"
    if "write" in last_msg or "запиши" in last_msg or "создай" in last_msg:
        return "Thought: Запишу результат в файл.\nAction: write('result.txt', 'готово')"
    if "python" in last_msg or "вычисли" in last_msg:
        return "Thought: Выполню вычисление.\nAction: python('2 + 2')"

    return "Thought: Задача выполнена. Могу ответить.\nFinal: Готово!"


def parse_react(response: str) -> dict:
    """Парсит ReAct формат: Thought / Action / Final."""

    if "Final:" in response:
        final = response.split("Final:")[-1].strip()
        return {"type": "final", "content": final}

    thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final:|$)", response, re.DOTALL)
    action_match = re.search(r"Action:\s*(\w+)\((.*)\)", response)

    result = {"type": "action"}
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    if action_match:
        result["tool"] = action_match.group(1)
        # Парсим аргументы (упрощённо)
        args_str = action_match.group(2)
        try:
            result["args"] = json.loads(f"{{{args_str}}}")
        except:
            result["args"] = {"query": args_str} if "query" in args_str else {"content": args_str}

    return result


# ─── 6. SYSTEM PROMPT ─────────────────────────────────────────────

SYSTEM_PROMPT = """
Ты — агент, работающий с файловой системой.

У тебя есть инструменты:
- grep(pattern, path) — поиск текста
- read(path) — чтение файла
- write(path, content) — запись файла (с подтверждением)
- python(code) — выполнение Python

Формат ответа:
Thought: <рассуждение>
Action: tool_name(args)

ИЛИ если задача выполнена:
Thought: <рассуждение>
Final: <ответ пользователю>

ПРАВИЛА:
1. Всегда читай файл перед изменением
2. Не выполняй опасные команды (rm, sudo, exec, eval)
3. Если что-то пошло не так — скажи об этом
4. Ответ давай на русском языке
"""


# ─── 7. ЦИКЛ АГЕНТА ──────────────────────────────────────────────

class ReActAgent:
    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self.memory = AgentMemory(system_prompt)

    def run(self, task: str) -> str:
        self.memory.working["task"] = task
        self.memory.add_message("user", task)

        for step in range(1, MAX_STEPS + 1):
            # Проверка бюджета
            if self.memory.total_cost >= MAX_COST:
                return f"❌ Бюджет исчерпан (${self.memory.total_cost:.4f})"

            start = time.time()

            # 1. LLM думает
            context = self.memory.build_context()
            response = call_llm(context)
            parsed = parse_react(response)

            duration = int((time.time() - start) * 1000)

            # 2. Если финальный ответ — возвращаем
            if parsed["type"] == "final":
                self.memory.log_step(AgentStep(
                    step=step,
                    thought=parsed.get("thought", ""),
                    action="final",
                    action_args={},
                    observation="",
                    cost=estimate_cost(context, response),
                    duration_ms=duration,
                    guardrail="allow",
                ))
                return parsed["content"]

            # 3. Выполняем инструмент
            tool_name = parsed.get("tool", "")
            tool_args = parsed.get("args", {})
            tool = TOOLS.get(tool_name)

            if not tool:
                obs = f"инструмент '{tool_name}' не найден"
                guardrail_action = "block"
            else:
                # Guardrail
                allowed, reason = guardrail_tool(tool_name, tool_args)
                if not allowed:
                    obs = f"guardrail: {reason}"
                    guardrail_action = "block"
                else:
                    # Выполняем
                    raw_result = tool["fn"](**tool_args)
                    obs = sanitize_output(tool_name, raw_result)
                    guardrail_action = "allow"

            # 4. Логируем шаг
            cost = estimate_cost(context, response)
            self.memory.log_step(AgentStep(
                step=step,
                thought=parsed.get("thought", ""),
                action=tool_name,
                action_args=tool_args,
                observation=obs[:200],  # обрезаем для памяти
                cost=cost,
                duration_ms=duration,
                guardrail=guardrail_action,
            ))

            # 5. Добавляем результат в контекст
            self.memory.add_message("assistant", response)
            self.memory.add_message("tool",
                json.dumps({"result": obs[:500]}, ensure_ascii=False))

            # Вывод в реальном времени
            thought = parsed.get("thought", "")[:80]
            print(f"  [{step}] {tool_name}(...) — {duration}ms (${cost:.4f})")
            print(f"    → {thought}...")

            self.memory.working["step"] = step

        return "❌ Достигнут лимит шагов"


def estimate_cost(messages: list[dict], response: str) -> float:
    """Приблизительная стоимость вызова."""
    total_chars = sum(len(m["content"]) for m in messages if "content" in m)
    input_tokens = total_chars // 4
    output_tokens = len(response) // 4
    return (input_tokens * 0.0000005 + output_tokens * 0.000002)  # deepseek-chat rates


# ─── 8. ЗАПУСК ────────────────────────────────────────────────────

def main():
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "найди все .py файлы в текущей директории и подсчитай количество строк в каждом"

    print("=" * 60)
    print("🤖 ReAct Agent v1.0")
    print("=" * 60)
    print(f"\n📋 Задача: {task}")
    print(f"💰 Бюджет: ${MAX_COST}")
    print(f"🔄 Макс. шагов: {MAX_STEPS}")

    if not API_KEY:
        print("  ⚠ Режим симуляции (без API-ключа)")
        print("  Установи DEEPSEEK_API_KEY для реальных запросов")
    print()

    agent = ReActAgent()
    result = agent.run(task)

    print()
    print("=" * 60)
    print("📬 Результат:")
    print("=" * 60)
    print(result)
    print(agent.memory.summary())


if __name__ == "__main__":
    main()
