"""Mock LLM responses for testing."""

from typing import Optional

# Common mock responses for agent tests
MOCK_RESPONSES = {
    "greeting": {
        "choices": [
            {
                "message": {
                    "content": "Hello! I am an AI assistant. How can I help you today?",
                    "role": "assistant",
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
    },
    "tool_call": {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "function": {
                                "name": "read",
                                "arguments": '{"file_path": "/tmp/test.txt"}',
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50},
    },
    "financial_advice": {
        "choices": [
            {
                "message": {
                    "content": "I cannot provide financial advice. Please consult a certified financial advisor.",
                    "role": "assistant",
                }
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 18, "total_tokens": 33},
    },
    "code_generation": {
        "choices": [
            {
                "message": {
                    "content": "```python\ndef hello():\n    print('Hello, World!')\n```",
                    "role": "assistant",
                }
            }
        ],
        "usage": {"prompt_tokens": 25, "completion_tokens": 20, "total_tokens": 45},
    },
}


def get_mock_response(key: str) -> Optional[dict]:
    """Get a mock response by key."""
    return MOCK_RESPONSES.get(key)


def stream_mock_response(key: str, chunk_size: int = 10):
    """Simulate streaming response."""
    response = get_mock_response(key)
    if not response:
        return

    content = response["choices"][0]["message"]["content"] or ""
    for i in range(0, len(content), chunk_size):
        yield {
            "choices": [
                {
                    "delta": {"content": content[i : i + chunk_size]},
                    "finish_reason": None if i + chunk_size < len(content) else "stop",
                }
            ]
        }
