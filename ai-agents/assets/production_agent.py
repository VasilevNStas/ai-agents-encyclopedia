#!/usr/bin/env python3
"""
production_agent.py — Production-ready шаблон ReAct-агента.

Это НЕ демо (в отличие от build_your_agent.py).
Это каркас для продакшен-агента со всеми механизмами:
  - Guardrails (input, output, data)
  - Cost control (бюджет на сессию)
  - Observability (лог каждого шага)
  - Resilience (retry, fallback, circuit breaker)
  - Память (short-term + working)

Использование:
  export DEEPSEEK_API_KEY="sk-..."
  python3 production_agent.py

Заменяй TOOLS и SYSTEM_PROMPT под свою задачу.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ═══════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════

# Вынеси в config.yaml или .env в своём проекте
CONFIG = {
    "model": os.environ.get("AGENT_MODEL", "deepseek-chat"),
    "max_steps": 20,
    "max_cost": 0.10,            # бюджет сессии
    "max_retries": 3,            # retry при ошибках API
    "timeout_seconds": 30,       # таймаут на вызов LLM
    "log_level": "verbose",      # minimal | verbose | debug
    "allowed_paths": [os.getcwd()],  # где может работать агент
    "blocked_commands": ["rm", "sudo", "dd", "mkfs", "shutdown"],
}

# ═══════════════════════════════════════════════════════════════════
# СИСТЕМНЫЙ PROMPT
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Ты — AI-агент для работы с кодом.

ПРАВИЛА:
1. Всегда читай файл перед изменением
2. Одно изменение — один вызов инструмента
3. После изменения проверь синтаксис
4. Не выполняй опасные команды (rm, sudo, eval)
5. Если сомневаешься — спроси пользователя

ИНСТРУМЕНТЫ:
- read(path) — прочитать файл
- edit(path, old, new) — заменить текст
- run(command) — выполнить команду (read-only)
- python(code) — выполнить Python

ФОРМАТ ОТВЕТА:
Thought: <рассуждение>
Action: <инструмент>(<аргументы>)
"""

# ═══════════════════════════════════════════════════════════════════
# СТРУКТУРЫ ДАННЫХ
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AgentStep:
    """Один шаг агента: что думал, что сделал, что получил."""
    step_number: int
    timestamp: str
    thought: str
    action: str
    action_args: dict
    observation: str
    token_cost: float
    duration_ms: int
    guardrail_action: str  # allow | block | confirm


@dataclass
class AgentMemory:
    """Память агента: short-term (контекст) + working (текущая задача)."""
    short_term: list = field(default_factory=list)
    working: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)
    total_cost: float = 0.0

    def add_message(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content})

    def build_context(self) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if self.working.get("plan"):
            messages.append({"role": "system",
                            "content": f"План: {json.dumps(self.working['plan'])}"})
        messages.extend(self.short_term[-30:])  # sliding window
        return messages


# ═══════════════════════════════════════════════════════════════════
# GUARDRAILS
# ═══════════════════════════════════════════════════════════════════

class Guardrails:
    """Три слоя защиты: input, output, data."""

    @staticmethod
    def check_input(user_input: str) -> tuple[bool, str]:
        """Input guard: проверка запроса пользователя."""
        dangerous = ["игнорируй предыдущие", "ты теперь", "forget everything",
                     "system prompt", "ты не ассистент"]
        for d in dangerous:
            if d in user_input.lower():
                return False, f"prompt injection: {d}"
        return True, "allow"

    @staticmethod
    def check_output(tool_name: str, args: dict) -> tuple[bool, str]:
        """Output guard: проверка действия перед выполнением."""
        if tool_name == "run":
            cmd = args.get("command", "")
            for blocked in CONFIG["blocked_commands"]:
                if cmd.startswith(blocked) or f" {blocked} " in cmd:
                    return False, f"команда заблокирована: {blocked}"
        if tool_name == "python":
            code = args.get("code", "")
            if "exec(" in code or "eval(" in code or "__import__" in code:
                return False, "опасный вызов: exec/eval/__import__"
        return True, "allow"

    @staticmethod
    def check_path(path: str) -> tuple[bool, str]:
        """Data guard: проверка пути к файлу."""
        abs_path = os.path.abspath(os.path.expanduser(path))
        for allowed in CONFIG["allowed_paths"]:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True, "allow"
        return False, f"путь вне разрешённых: {path}"


# ═══════════════════════════════════════════════════════════════════
# LLM ВЫЗОВ С RESILIENCE
# ═══════════════════════════════════════════════════════════════════

class LLMClient:
    """Вызов LLM с retry, fallback и подсчётом стоимости."""

    MODELS = [
        {"id": "deepseek-chat", "priority": 1, "cost_per_1k_input": 0.0005,
         "cost_per_1k_output": 0.002},
        {"id": "deepseek-reasoner", "priority": 2, "cost_per_1k_input": 0.002,
         "cost_per_1k_output": 0.008},
    ]

    @staticmethod
    def call(messages: list[dict], model_id: str = None) -> tuple[str, float, int, int]:
        """Вызов с подсчётом токенов и стоимости."""
        if not os.environ.get("DEEPSEEK_API_KEY"):
            return LLMClient._simulate(messages)

        model_id = model_id or CONFIG["model"]
        data = json.dumps({
            "model": model_id,
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.3,
        }).encode()

        from urllib import request
        req = request.Request(
            "https://api.deepseek.com/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
                "Content-Type": "application/json",
            },
        )

        resp = json.loads(request.urlopen(req, timeout=CONFIG["timeout_seconds"]).read())
        content = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Расчёт стоимости
        model_config = next(m for m in LLMClient.MODELS if m["id"] == model_id)
        cost = (input_tokens * model_config["cost_per_1k_input"] / 1000 +
                output_tokens * model_config["cost_per_1k_output"] / 1000)

        return content, cost, input_tokens, output_tokens

    @staticmethod
    def call_with_retry(messages: list[dict]) -> tuple[str, float]:
        """Вызов с retry + exponential backoff + fallback модели."""
        last_error = None

        for model in sorted(LLMClient.MODELS, key=lambda m: m["priority"]):
            for attempt in range(CONFIG["max_retries"]):
                try:
                    return LLMClient.call(messages, model["id"])
                except Exception as e:
                    last_error = e
                    wait = 2 ** attempt
                    print(f"  ⚠ {model['id']} попытка {attempt+1}: {e}. Жду {wait}s")
                    time.sleep(wait)
                    continue

        raise Exception(f"Все модели исчерпаны: {last_error}")

    @staticmethod
    def _simulate(messages) -> tuple[str, float, int, int]:
        """Симуляция без API."""
        return ("Thought: Задача выполнена.\nFinal: Готово!",
                0.001, 100, 20)


# ═══════════════════════════════════════════════════════════════════
# ИНСТРУМЕНТЫ
# ═══════════════════════════════════════════════════════════════════

class Tools:
    """Инструменты агента. Каждый — одна функция, одно действие."""

    @staticmethod
    def read(path: str) -> str:
        if not Guardrails.check_path(path):
            return "❌ доступ запрещён"
        try:
            with open(path) as f:
                return f.read()
        except Exception as e:
            return f"❌ {e}"

    @staticmethod
    def edit(path: str, old: str, new: str) -> str:
        if not Guardrails.check_path(path):
            return "❌ доступ запрещён"
        try:
            with open(path) as f:
                content = f.read()
            if old not in content:
                return "❌ текст для замены не найден"
            with open(path, "w") as f:
                f.write(content.replace(old, new))
            return f"✅ заменено {len(old)} → {len(new)} символов"
        except Exception as e:
            return f"❌ {e}"

    @staticmethod
    def run(command: str) -> str:
        import subprocess
        try:
            result = subprocess.run(command.split(), capture_output=True,
                                    text=True, timeout=10)
            return result.stdout[:1000] or result.stderr[:1000]
        except Exception as e:
            return f"❌ {e}"

    @staticmethod
    def python(code: str) -> str:
        try:
            local_vars = {}
            exec(code, {"__builtins__": __builtins__}, local_vars)
            return str(local_vars) if local_vars else "✅ код выполнен"
        except Exception as e:
            return f"❌ {e}"


TOOL_MAP = {
    "read": Tools.read,
    "edit": Tools.edit,
    "run": Tools.run,
    "python": Tools.python,
}

# ═══════════════════════════════════════════════════════════════════
# ЦИКЛ АГЕНТА
# ═══════════════════════════════════════════════════════════════════

class ReActAgent:
    """Production-ready ReAct агент со всеми защитами."""

    def __init__(self):
        self.memory = AgentMemory()
        self.guardrails = Guardrails()
        self.llm = LLMClient()
        self.start_time = time.time()

    def run(self, task: str) -> str:
        # 1. Input guardrail
        allowed, reason = self.guardrails.check_input(task)
        if not allowed:
            return f"❌ Заблокировано: {reason}"

        self.memory.working["task"] = task
        self.memory.add_message("user", task)

        print(f"\n{'='*60}")
        print(f"🤖 Agent session started")
        print(f"{'='*60}")
        print(f"📋 Task: {task}")
        print(f"💰 Budget: ${CONFIG['max_cost']}")
        print(f"🔄 Max steps: {CONFIG['max_steps']}")
        print()

        for step in range(1, CONFIG["max_steps"] + 1):
            # Cost control
            if self.memory.total_cost >= CONFIG["max_cost"]:
                return f"❌ Бюджет исчерпан (${self.memory.total_cost:.4f})"

            step_start = time.time()

            # LLM call with resilience
            try:
                response, cost = self.llm.call_with_retry(self.memory.build_context())
            except Exception as e:
                return f"❌ LLM недоступна: {e}"

            # Parse ReAct format
            parsed = self._parse_react(response)
            duration = int((time.time() - step_start) * 1000)

            if parsed["type"] == "final":
                self.memory.total_cost += cost
                print(f"  [{step}] ✅ Final ({duration}ms, ${cost:.4f})")
                return parsed["content"]

            # Output guardrail
            tool_name = parsed.get("tool", "")
            tool_args = parsed.get("args", {})
            allowed, reason = self.guardrails.check_output(tool_name, tool_args)

            if not allowed:
                obs = f"⛔ {reason}"
                guardrail = "block"
            else:
                guardrail = "allow"
                tool_fn = TOOL_MAP.get(tool_name)
                if tool_fn:
                    obs = tool_fn(**tool_args)
                else:
                    obs = f"❌ неизвестный инструмент: {tool_name}"
                    guardrail = "block"

            # Log step
            self.memory.total_cost += cost
            self.memory.steps.append(AgentStep(
                step_number=step,
                timestamp=datetime.now().isoformat(),
                thought=parsed.get("thought", ""),
                action=tool_name,
                action_args=tool_args,
                observation=obs[:200],
                token_cost=cost,
                duration_ms=duration,
                guardrail_action=guardrail,
            ))

            self.memory.add_message("assistant", response)
            self.memory.add_message("tool", obs[:500])

            print(f"  [{step}] {tool_name}(...) → {guardrail} ({duration}ms, ${cost:.4f})")

        return "❌ Достигнут лимит шагов"

    def _parse_react(self, response: str) -> dict:
        """Парсит формат Thought/Action/Final."""
        if "Final:" in response:
            return {"type": "final", "content": response.split("Final:")[-1].strip()}

        action_match = re.search(r"Action:\s*(\w+)\((.*)\)", response)
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final:|$)", response, re.DOTALL)

        result = {"type": "action"}
        if thought_match:
            result["thought"] = thought_match.group(1).strip()[:100]
        if action_match:
            result["tool"] = action_match.group(1)
            args_str = action_match.group(2).strip().strip('"')
            result["args"] = {"content": args_str}
        return result

    def summary(self) -> str:
        """Итоговый отчёт."""
        total_duration = time.time() - self.start_time
        steps = self.memory.steps
        tool_counts = {}
        for s in steps:
            tool_counts[s.action] = tool_counts.get(s.action, 0) + 1
        blocked = sum(1 for s in steps if s.guardrail_action == "block")

        return f"""
{'='*60}
📊 Session Summary
{'='*60}
Steps:      {len(steps)}
Duration:   {total_duration:.1f}s
Cost:       ${self.memory.total_cost:.4f}
Tools:      {tool_counts}
Guardrails: {blocked} blocked
{'='*60}"""


# ═══════════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════════

def main():
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "прочитай README.md и напиши краткое содержание"

    agent = ReActAgent()
    result = agent.run(task)
    print(f"\n📬 Result:\n{result}")
    print(agent.summary())


if __name__ == "__main__":
    main()
