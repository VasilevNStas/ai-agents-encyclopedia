> [!success] Status: Implemented
> Full ReAct agent with real LLM integration.

# SupportFlow — Этап 1: Core ReAct Agent

> После [[../../../01-fundamentals/03-react-pattern|Модуль 1 (Фундамент)]]

## Что реализовано

- **ReAct-цикл** с реальным LLM (OpenAI / Anthropic / DeepSeek)
- **3 инструмента**: search_knowledge_base, calculator, get_current_time
- **Единый LLM-клиент** для разных провайдеров с конвертацией форматов
- **CLI + interactive mode**

## Файлы

| Файл | Описание |
|------|----------|
| `agent.py` | ReActAgent, LLMClient, инструменты, CLI |
| `config.py` | (удалён — конфигурация встроена в agent.py) |
| `DIFF.md` | Что изменилось относительно предыдущего этапа |
| `requirements.txt` | Зависимости |

## Запуск

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
python agent.py --provider openai "как сбросить пароль?"

# Interactive
python agent.py --provider anthropic
```

## Пример

```
$ python agent.py "сколько стоит Pro план?"

─── Iteration 1 ───
[Tool call]: search_knowledge_base({"query": "Pro plan pricing"})
[Tool result]: Our billing cycle is monthly...
─── Iteration 2 ───

=== Response ===
Pro план стоит $25/месяц. Включает все базовые функции плюс приоритетную поддержку.

=== Iterations: 2 | Tool calls: 1 ===
```

## Ключевые концепты

- **ReAct**: Thought → Action → Observation → Answer
- **Tool calling через API**: LLM решает, когда и какой инструмент вызвать
- **Multi-provider**: один интерфейс, разные бэкенды
