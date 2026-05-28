# DIFF: Stage 1 — Core ReAct Agent

> Относительно: пустоты (первая реализация)
> Модуль курса: [[../../../01-fundamentals/03-react-pattern]]

## Что изменилось

### Добавлено

| Компонент | Описание |
|-----------|----------|
| `config.py` | Конфигурация: ModelConfig (provider, model, temperature), AgentConfig (max_iterations, verbose) |
| `LLMClient` | Единый клиент для OpenAI / Anthropic / DeepSeek с автоматической конвертацией форматов |
| `TOOL_SCHEMAS` | 3 инструмента: search_knowledge_base, get_current_time, calculator |
| `TOOL_IMPLEMENTATIONS` | Реальные реализации инструментов (KB, time, safe eval) |
| `ReActAgent.run()` | Полный ReAct-цикл: вызов LLM → tool_calls → execution → context → repeat |
| CLI interface | `python agent.py --provider openai "как сбросить пароль?"` |
| Interactive mode | `python agent.py --provider anthropic` без аргументов |

### Улучшено (относительно старого `react_agent.py`)

| Аспект | Было | Стало |
|--------|------|-------|
| LLM | Mock (предопределённые ответы) | Реальный API (OpenAI/Anthropic/DeepSeek) |
| Tool calling | Ручной парсинг "ACTION:" | Стандартный function calling API |
| Инструменты | 1 (search_kb) | 3 (search_kb, time, calculator) |
| Error handling | Нет | Graceful error recovery per tool |
| Конфигурация | hardcoded | dataclasses + env vars |
| Языки | Hardcoded Python | Provider-agnostic |

### Удалено

- Старый `config.py` в `src/agent/` — не трогаем, он для production-версии
- Mock LLM — больше не нужен

## Как запустить

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
python agent.py --provider openai "как сбросить пароль?"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
python agent.py --provider anthropic "what is the refund policy?"

# DeepSeek
export DEEPSEEK_API_KEY="sk-..."
python agent.py --provider deepseek --model deepseek-chat "calculate 150 * 0.2"

# Interactive mode
python agent.py --provider openai --model gpt-4o-mini
```

## Архитектура

```
Режимы запуска:
  ┌──────────────────────┐
  │   CLI / Interactive  │
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │    ReActAgent.run()  │
  │                      │
  │  ┌────────────────┐  │
  │  │  LLMClient     │  │
  │  │  chat_completion│  │
  │  └───────┬────────┘  │
  │          │           │
  │  ┌───────▼────────┐  │
  │  │ Tool Execution │  │
  │  │ search KB      │  │
  │  │ calculator     │  │
  │  │ get_time       │  │
  │  └────────────────┘  │
  └──────────────────────┘
```

## Что дальше

Следующий этап: [[../../02-memory/DIFF|Stage 2 — добавление памяти и RAG]]
