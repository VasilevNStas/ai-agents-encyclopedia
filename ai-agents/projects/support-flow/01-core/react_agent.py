"""SupportFlow: минимальный ReAct-агент (Модуль 1)."""

import json
from typing import Any


# === Инструменты ===
def search_knowledge_base(query: str) -> str:
    """Поиск по базе знаний."""
    # Мок: в реальности — RAG запрос
    return f"Результаты поиска по запросу: {query}"


TOOLS = {
    "search_knowledge_base": search_knowledge_base,
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search knowledge base for answer",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    }
]


# === ReAct цикл ===
class ReActAgent:
    """Минимальный ReAct-агент."""

    def __init__(self, system_prompt: str, tools: dict, max_iterations: int = 5):
        self.system_prompt = system_prompt
        self.tools = tools
        self.max_iterations = max_iterations

    def invoke(self, user_input: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for step in range(self.max_iterations):
            # LLM call (mock — в реальности настоящий LLM)
            response = self._mock_llm(messages)

            if "FINAL_ANSWER" in response:
                return response.split("FINAL_ANSWER: ")[1]

            # Парсинг вызова инструмента
            if "ACTION:" in response:
                action_line = response.split("ACTION: ")[1].split("\n")[0]
                action_data = json.loads(action_line)
                tool_name = action_data["name"]
                tool_args = action_data["args"]

                result = self.tools[tool_name](**tool_args)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool", "content": result})

        return "Max iterations reached without final answer."

    def _mock_llm(self, messages) -> str:
        """Mock LLM — для демонстрации без API-ключа."""
        last = messages[-1]["content"].lower()
        if "пароль" in last or "password" in last:
            return (
                "THOUGHT: User is asking about password reset. "
                "I need to search the knowledge base.\n"
                'ACTION: {"name": "search_knowledge_base", '
                '"args": {"query": "password reset guide"}}'
            )
        return (
            "THOUGHT: I have enough information to answer.\n"
            "FINAL_ANSWER: Based on the knowledge base, here's the answer."
        )


# === Пример ===
if __name__ == "__main__":
    agent = ReActAgent(
        system_prompt="You are SupportFlow, a support agent.",
        tools=TOOLS,
    )
    result = agent.invoke("Как сбросить пароль?")
    print(f"Agent: {result}")
