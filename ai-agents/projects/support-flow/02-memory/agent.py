"""SupportFlow Stage 2: Agent с трёхслойной памятью и RAG-пайплайном."""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from memory import AgentMemory, MemoryConfig
from rag import RAGPipeline, RAGConfig


# ============================================================
# Configuration
# ============================================================


@dataclass
class ModelConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2048


@dataclass
class AgentConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    max_iterations: int = 10
    verbose: bool = True
    use_rag: bool = True
    memory_dir: str = ".memory"


# ============================================================
# LLM Client (упрощённая копия из Stage 1)
# ============================================================


class LLMClient:
    PROVIDER_CONFIGS = {
        "openai": {"env_key": "OPENAI_API_KEY"},
        "anthropic": {"env_key": "ANTHROPIC_API_KEY"},
        "deepseek": {"env_key": "DEEPSEEK_API_KEY"},
    }

    def __init__(self, config: ModelConfig):
        self.config = config
        self.api_key = os.environ.get(self.PROVIDER_CONFIGS[config.provider]["env_key"])

    def chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> dict:
        if self.config.provider in ("openai", "deepseek"):
            return self._openai_like(messages, tools)
        elif self.config.provider == "anthropic":
            return self._anthropic_chat(messages, tools)
        raise ValueError(f"Unknown provider: {self.config.provider}")

    def _openai_like(self, messages: list[dict], tools: list[dict] | None) -> dict:
        from openai import OpenAI

        base_urls = {"deepseek": "https://api.deepseek.com/v1"}
        client = OpenAI(
            api_key=self.api_key,
            base_url=base_urls.get(self.config.provider, None),
        )
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = client.chat.completions.create(**kwargs)
        return self._unify(resp)

    def _anthropic_chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
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

        kwargs = {
            "model": self.config.model or "claude-sonnet-4-20250514",
            "messages": converted,
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

        resp = client.messages.create(**kwargs)
        result = {
            "role": "assistant",
            "content": "",
            "tool_calls": [],
            "finish_reason": "stop",
        }
        for block in resp.content:
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

    def _unify(self, resp) -> dict:
        choice = resp.choices[0]
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
            "name": "save_to_memory",
            "description": "Save important information to long-term memory for future reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Identifier for the information",
                    },
                    "content": {"type": "string", "description": "Content to remember"},
                },
                "required": ["key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_from_memory",
            "description": "Read previously saved information from long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Identifier to retrieve"},
                },
                "required": ["key"],
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
                        "description": "Timezone (optional)",
                    },
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
                        "description": "Mathematical expression",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


TOOL_IMPL: dict[str, Any] = {}


def tool(name: str):
    def dec(fn):
        TOOL_IMPL[name] = fn
        return fn

    return dec


def execute_tool(name: str, args: dict, memory: AgentMemory | None = None) -> str:
    fn = TOOL_IMPL.get(name)
    if not fn:
        return f"Error: unknown tool '{name}'"
    try:
        return fn(**args, memory=memory)
    except TypeError:
        # Some tools don't accept memory parameter
        import inspect

        sig = inspect.signature(fn)
        filtered = {k: v for k, v in args.items() if k in sig.parameters}
        return fn(**filtered)
    except Exception as e:
        return f"Error executing {name}: {e}"


@tool("search_knowledge_base")
def search_knowledge_base(query: str, rag: RAGPipeline | None = None, **kwargs) -> str:
    if rag:
        result = rag.retrieve(query)
        if result.chunks:
            return "\n\n".join(
                f"[{i}] {c['text']}" for i, c in enumerate(result.chunks, 1)
            )
    # Fallback
    kb = {
        "password": "To reset your password, go to login → Forgot Password → check email.",
        "billing": "Plans: Basic $10/mo, Pro $25/mo, Enterprise custom.",
        "refund": "Full refund within 14 days, pro-rated after.",
        "account": "Account settings available in profile. Export data first.",
    }
    for keyword, answer in kb.items():
        if keyword in query.lower():
            return answer
    return f"Could not find specific information about '{query}'."


@tool("save_to_memory")
def save_to_memory(
    key: str, content: str, memory: AgentMemory | None = None, **kwargs
) -> str:
    if memory:
        path = memory.save_knowledge(
            key,
            content,
            {"saved_at": __import__("datetime").datetime.now().isoformat()},
        )
        return f"Saved to memory: {path}"
    return f"Memory system not available. Content: {content[:100]}..."


@tool("read_from_memory")
def read_from_memory(key: str, memory: AgentMemory | None = None, **kwargs) -> str:
    if memory:
        content = memory.load_knowledge(key)
        if content:
            return content
        # List available keys
        keys = memory.list_knowledge_keys()
        if keys:
            return f"Key '{key}' not found. Available keys: {', '.join(keys)}"
        return f"Key '{key}' not found. Memory is empty."
    return f"Memory system not available."


@tool("get_current_time")
def get_current_time(timezone: str = "UTC", **kwargs) -> str:
    from datetime import datetime

    return datetime.now().strftime(f"%Y-%m-%d %H:%M:%S ({timezone})")


@tool("calculator")
def calculator(expression: str, **kwargs) -> str:
    import ast, operator

    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def eval_n(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return ops[type(node.op)](eval_n(node.left), eval_n(node.right))
        if isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](eval_n(node.operand))
        raise ValueError(f"Unsupported: {type(node).__name__}")

    try:
        r = eval_n(ast.parse(expression, mode="eval").body)
        return f"{expression} = {r}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# Agent with Memory & RAG
# ============================================================

SYSTEM_PROMPT = """You are SupportFlow, an intelligent support agent with memory and knowledge base.

You can:
1. Search the knowledge base for answers (always search first)
2. Save important information to memory (for reuse across conversations)
3. Read from memory when the user references past conversations
4. Use calculator for math and time for date/time queries

Rules:
- Search the knowledge base before answering support questions.
- If the user mentions a previous issue, read from memory to recall context.
- Save important user preferences or unresolved issues to memory.
- Always respond in the user's language.
- Be concise, helpful, and honest when you don't know something."""


class MemoryAgent:
    """Агент с трёхслойной памятью и RAG."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.llm = LLMClient(self.config.model)
        self.memory = AgentMemory(MemoryConfig(storage_dir=self.config.memory_dir))
        self.rag = RAGPipeline() if self.config.use_rag else None
        self.system_prompt = SYSTEM_PROMPT

    def run(self, user_input: str, session_id: str = "default") -> dict:
        # 1. Добавляем пользовательский ввод в short-term memory
        self.memory.add_message("user", user_input)

        # 2. Строим контекст с RAG (если включён)
        rag_context = ""
        if self.rag:
            rag_result = self.rag.retrieve(user_input)
            rag_context = self.rag.format_context(rag_result)

        # 3. Строим system prompt с контекстом
        system = self.system_prompt
        if rag_context:
            system = f"{system}\n\nCurrent context:\n{rag_context}"

        # 4. Собираем messages: system + short-term history + текущий запрос
        messages: list[dict] = [{"role": "system", "content": system}]
        history = self.memory.get_conversation_context(limit=10)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 5. ReAct-цикл
        for iteration in range(1, self.config.max_iterations + 1):
            if self.config.verbose:
                print(f"\n─── Iteration {iteration} ───")

            response = self.llm.chat_completion(messages, TOOL_SCHEMAS)
            content = response["content"] or ""
            tool_calls = response.get("tool_calls", [])

            if self.config.verbose and content:
                print(f"[Assistant]: {content[:200]}...")

            if not tool_calls:
                self.memory.add_message("assistant", content)
                return {
                    "response": content,
                    "iterations": iteration,
                    "tool_calls": self._count_tool_calls(messages),
                    "memory_size": self.memory.short_term.count,
                    "rag_used": bool(rag_context),
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": content or "",
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
                    print(f"[Tool]: {name}({json.dumps(args)})")

                result = execute_tool(name, args, memory=self.memory)
                if self.config.verbose:
                    print(f"[Result]: {result[:200]}...")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

        msg = "Max iterations reached. Please rephrase your question."
        self.memory.add_message("assistant", msg)
        return {"response": msg, "error": "max_iterations_exceeded"}

    def _count_tool_calls(self, messages: list[dict]) -> int:
        return sum(1 for m in messages if m.get("role") == "tool")


# ============================================================
# CLI
# ============================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SupportFlow with Memory & RAG")
    parser.add_argument(
        "--provider", default="openai", choices=["openai", "anthropic", "deepseek"]
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("query", nargs="*")
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
        use_rag=not args.no_rag,
    )
    agent = MemoryAgent(config)

    query = " ".join(args.query)
    if query:
        print(f"\nUser: {query}")
        result = agent.run(query)
        print(f"\n=== Response ===")
        print(result["response"])
        print(
            f"=== Iterations: {result['iterations']} | "
            f"Tool calls: {result['tool_calls']} | "
            f"RAG: {result['rag_used']} ==="
        )
    else:
        print(f"\nSupportFlow with Memory & RAG (interactive)")
        print(f"Provider: {args.provider} | Model: {args.model}")
        print("Type 'exit' to quit.\n")
        while True:
            try:
                q = input("You: ")
                if q.lower() in ("exit", "quit"):
                    break
                result = agent.run(q)
                print(f"\nAgent: {result['response']}\n")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
