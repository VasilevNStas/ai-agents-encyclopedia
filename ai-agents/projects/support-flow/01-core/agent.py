"""SupportFlow Stage 1: Core ReAct Agent — реальная LLM, proper ReAct-цикл."""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


# ============================================================
# Configuration
# ============================================================


@dataclass
class ModelConfig:
    provider: str = "openai"  # openai | anthropic | deepseek
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2048


@dataclass
class AgentConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    max_iterations: int = 10
    system_prompt: str = ""
    verbose: bool = True


# ============================================================
# LLM Client
# ============================================================


class LLMClient:
    """Единый клиент для разных провайдеров."""

    PROVIDER_CONFIGS = {
        "openai": {
            "env_key": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
        },
        "anthropic": {
            "env_key": "ANTHROPIC_API_KEY",
            "base_url": "https://api.anthropic.com/v1",
        },
        "deepseek": {
            "env_key": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
        },
    }

    def __init__(self, config: ModelConfig):
        self.config = config
        provider_conf = self.PROVIDER_CONFIGS[config.provider]
        self.api_key = os.environ.get(provider_conf["env_key"])
        self.base_url = provider_conf["base_url"]
        self._client = None

    def chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        if self.config.provider == "openai":
            return self._openai_chat(messages, tools)
        elif self.config.provider == "anthropic":
            return self._anthropic_chat(messages, tools)
        elif self.config.provider == "deepseek":
            return self._deepseek_chat(messages, tools)
        raise ValueError(f"Unknown provider: {self.config.provider}")

    def _openai_chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = client.chat.completions.create(**kwargs)
        return self._to_unified(response)

    def _deepseek_chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs = {
            "model": self.config.model or "deepseek-chat",
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = client.chat.completions.create(**kwargs)
        return self._to_unified(response)

    def _anthropic_chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        system, anthropic_messages = self._convert_to_anthropic(messages)
        kwargs = {
            "model": self.config.model or "claude-sonnet-4-20250514",
            "messages": anthropic_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]
        response = client.messages.create(**kwargs)
        return self._from_anthropic(response)

    def _to_unified(self, response) -> dict:
        choice = response.choices[0]
        msg = choice.message
        result = {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [],
            "finish_reason": choice.finish_reason,
        }
        if msg.tool_calls:
            for tc in msg.tool_calls:
                result["tool_calls"].append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )
        return result

    def _convert_to_anthropic(
        self, messages: list[dict]
    ) -> tuple[str | None, list[dict]]:
        system = None
        converted = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
                continue
            if m["role"] == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id", ""),
                                "content": m["content"],
                            }
                        ],
                    }
                )
                continue
            converted.append({"role": m["role"], "content": m["content"]})
        return system, converted

    def _from_anthropic(self, response) -> dict:
        result = {
            "role": "assistant",
            "content": "",
            "tool_calls": [],
            "finish_reason": "stop",
        }
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_calls"].append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )
                result["finish_reason"] = "tool_calls"
        return result


# ============================================================
# Tools
# ============================================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the support knowledge base for answers. Use for common questions about billing, password reset, account issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language)",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (optional, e.g. 'Europe/Moscow')",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression like '2 + 2' or '150 * 0.2'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


TOOL_IMPLEMENTATIONS: dict[str, Callable] = {}


def tool(name: str):
    def decorator(fn):
        TOOL_IMPLEMENTATIONS[name] = fn
        return fn

    return decorator


@tool("search_knowledge_base")
def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for relevant articles."""
    knowledge_base = {
        "password reset": (
            "To reset your password:\n"
            "1. Go to the login page\n"
            "2. Click 'Forgot Password'\n"
            "3. Enter your email address\n"
            "4. Check your inbox for reset link\n"
            "5. Click the link and set a new password\n"
            "The link expires in 24 hours."
        ),
        "billing": (
            "Our billing cycle is monthly.\n"
            "Plans: Basic ($10/mo), Pro ($25/mo), Enterprise (custom).\n"
            "You can upgrade or downgrade at any time.\n"
            "Invoices are sent via email on the 1st of each month."
        ),
        "refund": (
            "Refund policy:\n"
            "• Full refund within 14 days of purchase\n"
            "• Pro-rated refund after 14 days\n"
            "• Enterprise: per contract terms\n"
            "Processing time: 5-10 business days."
        ),
        "account": (
            "Account management:\n"
            "• Change email: Settings → Profile\n"
            "• Delete account: Settings → Danger Zone\n"
            "• Export data: Settings → Export\n"
            "• Two-factor authentication available in Security settings."
        ),
    }

    query_lower = query.lower()
    for keyword, answer in knowledge_base.items():
        if keyword in query_lower:
            return answer
    return (
        f"I don't have specific information about '{query}' in my knowledge base. "
        "Would you like me to escalate this to a human agent?"
    )


@tool("get_current_time")
def get_current_time(timezone: str = "UTC") -> str:
    return datetime.now().strftime(f"%Y-%m-%d %H:%M:%S ({timezone})")


@tool("calculator")
def calculator(expression: str) -> str:
    import ast, operator

    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            return allowed_ops[type(node.op)](
                eval_node(node.left), eval_node(node.right)
            )
        elif isinstance(node, ast.UnaryOp):
            return allowed_ops[type(node.op)](eval_node(node.operand))
        raise ValueError(f"Unsupported: {type(node).__name__}")

    try:
        result = eval_node(ast.parse(expression, mode="eval").body)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"


def execute_tool(name: str, args: dict) -> str:
    fn = TOOL_IMPLEMENTATIONS.get(name)
    if not fn:
        return f"Error: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as e:
        return f"Error executing {name}: {e}"


# ============================================================
# ReAct Agent
# ============================================================

DEFAULT_SYSTEM_PROMPT = """You are SupportFlow, an intelligent support agent.

You have access to tools. Use them when you need information.
Follow these rules:
1. If the user asks about something in the knowledge base — search it.
2. If you need to calculate something — use calculator.
3. If you don't know the answer — be honest and offer escalation.
4. Always respond in the user's language.
5. Be concise and helpful.

Before calling a tool, explain what you're doing. After getting results, provide a complete answer."""


class ReActAgent:
    """ReAct-агент с реальным LLM и инструментами."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.llm = LLMClient(self.config.model)
        self.system_prompt = self.config.system_prompt or DEFAULT_SYSTEM_PROMPT
        self.start_time = time.time()

    def run(self, user_input: str) -> dict:
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for iteration in range(1, self.config.max_iterations + 1):
            if self.config.verbose:
                print(f"\n─── Iteration {iteration} ───")

            response = self.llm.chat_completion(messages, TOOL_SCHEMAS)

            if self.config.verbose:
                content = response["content"]
                if content:
                    print(f"[Assistant]: {content[:200]}...")

            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                messages.append({"role": "assistant", "content": response["content"]})
                return {
                    "response": response["content"],
                    "iterations": iteration,
                    "tool_calls_made": self._count_tool_calls(messages),
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": response["content"] or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                if self.config.verbose:
                    print(f"[Tool call]: {name}({json.dumps(args)})")
                result = execute_tool(name, args)
                if self.config.verbose:
                    print(f"[Tool result]: {result[:200]}...")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

        return {
            "response": "Max iterations reached. Please rephrase your question.",
            "iterations": self.config.max_iterations,
            "tool_calls_made": self._count_tool_calls(messages),
            "error": "max_iterations_exceeded",
        }

    def _count_tool_calls(self, messages: list[dict]) -> int:
        return sum(1 for m in messages if m.get("role") == "tool")

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time


# ============================================================
# CLI Entry Point
# ============================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow ReAct Agent")
    parser.add_argument(
        "--provider", default="openai", choices=["openai", "anthropic", "deepseek"]
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("query", nargs="*", help="Query (omit for interactive mode)")
    args = parser.parse_args()

    if not args.model:
        model_map = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "deepseek": "deepseek-chat",
        }
        args.model = model_map[args.provider]

    config = AgentConfig(
        model=ModelConfig(provider=args.provider, model=args.model),
        verbose=not args.quiet,
    )
    agent = ReActAgent(config)

    if args.query:
        query = " ".join(args.query)
        print(f"\nUser: {query}")
        result = agent.run(query)
        print(f"\n=== Response ===")
        print(result["response"])
        print(
            f"=== Iterations: {result['iterations']} | "
            f"Tool calls: {result['tool_calls_made']} ==="
        )
    else:
        print("\nSupportFlow ReAct Agent (interactive mode)")
        print(f"Provider: {args.provider} | Model: {args.model}")
        print("Type 'exit' to quit.\n")
        while True:
            try:
                query = input("You: ")
                if query.lower() in ("exit", "quit"):
                    break
                result = agent.run(query)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
