---
created: 2026-05-28
tags: [course/case-studies, context-window, quality, architect]
status: active
---

# Case Study 5: Context Window Poisoning — когда агент «забывает» инструкции

> [!quote] Ключевая идея
> LLM имеет ограниченное контекстное окно. Чем длиннее история диалога, тем ниже «плотность внимания» к старым токенам. После 50K+ токенов модель начинает «забывать» начало диалога, включая системный промпт. Это не баг — это **физика attention**.

---

## Инцидент

**Компания:** Legal-tech стартап (2025)
**Сценарий:** Агент для анализа контрактов. Работает с большими документами (50-100 страниц). Системный промпт содержит юридические требования: конфиденциальность, формат ответа, обязательные поля.
**Проблема:** После ~40 страниц анализа агент начал игнорировать требования конфиденциальности и выдавал полный текст контракта в ответе.
**Результат:** Юрист получил ответ с конфиденциальными данными. Нарушение NDA.

## Механика poisoning

```
Контекст агента после 40 страниц:

[system] "Ты — юридический ассистент. Соблюдай конфиденциальность..."
  ↑ Attention к system prompt: ~0.02 (из-за расстояния)

[user] "Проанализируй контракт"
[tool] read_file → страницы 1-10 контракта
[tool] read_file → страницы 11-20 контракта
...
[tool] read_file → страницы 131-140 контракта
[tool] search_clause → результаты поиска
  ↑ Attention к последним токенам: ~0.85

[user] "Покажи полный текст раздела 5"
  ↑ Модель видит кучу данных контракта, слабо помнит system prompt
  → Отвечает: "Раздел 5: Конфиденциальность..." (ВЕСЬ ТЕКСТ РАЗДЕЛА)
```

### Почему это происходит

```python
import math


def attention_decay(position: int, context_length: int) -> float:
    """
    Упрощённая модель: внимание к токену падает
    с расстоянием от текущей позиции.
    """
    distance = context_length - position
    # Soft attention decay (реальная кривая сложнее)
    return 1.0 / (1.0 + math.log(distance + 1))


# System prompt на позиции 0, текущая позиция на 50000:
print(attention_decay(0, 50000))  # ≈ 0.09 — 9% от исходного внимания
# Последние токены на позиции 49990:
print(attention_decay(49990, 50000))  # ≈ 0.99 — 99% внимания
```

**Результат:** внимание к system prompt падает на порядок. Модель «помнит», что она юрист, но «забывает» конкретные ограничения.

## Решение

### Решение 1: Dynamic system prompt refresh

```python
class ContextManager:
    """Управляет контекстным окном: не даёт инструкциям «забыться»."""

    def __init__(self, system_prompt: str, refresh_interval: int = 10000):
        self.system_prompt = system_prompt
        self.refresh_interval = refresh_interval  # токенов
        self.token_count = 0

    def add_content(self, content: str) -> list[dict]:
        """Добавляет контент с периодическим refresh system prompt."""
        messages = []
        content_tokens = estimate_tokens(content)
        self.token_count += content_tokens

        # Каждые N токенов — напоминаем system prompt
        if self.token_count > self.refresh_interval:
            messages.append({"role": "system", "content": self.system_prompt})
            self.token_count = 0  # сброс счётчика

        messages.append({"role": "user", "content": content})
        return messages


# Использование
manager = ContextManager(SYSTEM_PROMPT, refresh_interval=8000)
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for chunk in document_chunks:
    messages.extend(manager.add_content(chunk))
    response = agent.invoke(messages)
    messages.append({"role": "assistant", "content": response})
```

### Решение 2: Structured context (context window budgeting)

```python
class ContextBudget:
    """Распределяет контекстное окно между компонентами."""

    MAX_TOKENS = 128_000

    # Бюджет на каждый компонент
    BUDGET = {
        "system_prompt": 2000,       # 2K — инструкции агента
        "working_memory": 10000,     # 10K — текущие результаты
        "conversation": 8000,        # 8K — история диалога
        "rag_results": 100000,       # 100K — данные из RAG
        "tool_outputs": 8000,        # 8K — результаты тулов
    }

    def allocate(self, component: str, tokens: int) -> bool:
        """Проверяет, есть ли бюджет для компонента."""
        if component not in self.BUDGET:
            return False

        budget = self.BUDGET[component]
        used = self.usage.get(component, 0)

        if used + tokens > budget:
            # Компрессия: суммаризируем старые данные
            self.compress(component)
            used = self.usage.get(component, 0)

        self.usage[component] = used + tokens
        return True

    def compress(self, component: str):
        """Суммаризация компонента для освобождения места."""
        if component == "rag_results":
            # Оставляем только top-3 результата
            self.usage[component] = min(self.usage[component], 3000)
        elif component == "conversation":
            # Суммаризируем историю
            self.usage[component] = min(self.usage[component], 2000)
```

### Решение 3: Semantic compression

```python
class SemanticCompressor:
    """Сжимает контекст, сохраняя смысл."""

    def compress_messages(self, messages: list[dict]) -> list[dict]:
        """Суммаризирует старые сообщения."""
        if estimate_tokens(messages) < 20000:
            return messages  # ещё рано

        # Разделяем: первые сообщения (старые) → в суммаризацию
        system = [m for m in messages if m["role"] == "system"]
        recent = messages[-6:]  # последние 6 сообщений
        old = messages[len(system):-6]

        if not old:
            return messages

        # Суммаризация старых
        summary = self.summarize(old)

        return system + [
            {"role": "system", "content": f"Session summary: {summary}"}
        ] + recent

    def summarize(self, messages: list[dict]) -> str:
        """LLM-суммаризация диалога."""
        text = "\n".join(m["content"] for m in messages)
        prompt = f"Summarize this conversation concisely (preserve facts, decisions, user preferences):\n\n{text}"
        return llm.invoke(prompt).content
```

### Решение 4: Cross-context consistency check

```python
def verify_consistency(state: AgentState) -> bool:
    """Проверяет, что агент всё ещё следует инструкциям."""

    check_prompt = f"""
    System prompt: {SYSTEM_PROMPT}
    Agent's last response: {state['messages'][-1]['content']}

    Does the response violate any system prompt rules?
    Answer ONLY: YES or NO
    """

    result = judge_llm.invoke(check_prompt)
    if "YES" in result.content:
        # Агент отклонился от инструкций
        # Очищаем контекст и перезапускаем
        alert("Agent deviated from instructions — context reset")
        return False
    return True
```

### Решение 5: Context window budget as guardrail

```python
@tool
def read_document_section(
    path: str,
    section: str,
    current_context_tokens: int,
) -> str:
    """Read a document section with context budget awareness."""
    section_content = extract_section(path, section)
    section_tokens = estimate_tokens(section_content)

    BUDGET_PER_OPERATION = 5000

    if section_tokens > BUDGET_PER_OPERATION:
        # Слишком большой раздел — суммаризируем
        return summarize_text(section_content, max_tokens=BUDGET_PER_OPERATION)

    if current_context_tokens + section_tokens > 100000:
        # Контекст почти полон — только суммаризация
        return summarize_text(section_content, max_tokens=1000)

    return section_content
```

## Чеклист: контекстная гигиена

- [ ] Dynamic system prompt refresh каждые N токенов
- [ ] Semantic compression старых сообщений
- [ ] Context window budget (явное распределение)
- [ ] Consistency check после каждого RAG-запроса
- [ ] Budget guardrail на tool output (max токенов на инструмент)
- [ ] Предупреждение при заполнении >80% контекста
- [ ] Отдельный счётчик для data vs instructions

## Ключевые выводы

| Проблема | Решение | Сложность |
|----------|---------|-----------|
| Attention decay к system prompt | Refresh каждые 8-10K токенов | Low |
| RAG-данные вытесняют инструкции | Context budget | Medium |
| Модель «забывает» ограничения | Consistency check | High |
| Потеря контекста диалога | Semantic compression | Medium |
| Инструменты переполняют окно | Budget guardrail | Low |

> [!warning] Контекстное окно — это «оперативная память» агента
> Как и в компьютере, если оперативной памяти мало — система начинает тормозить и делать ошибки. Разница: агент не «выдаст ошибку», а тихо начнёт игнорировать инструкции и галлюцинировать. **Мониторинг заполнения контекста — обязательный элемент observability.**

---

## Проверь себя

1. Почему внимание к system prompt падает с длиной контекста?
2. Как semantic compression отличается от простого обрезания истории?
3. Напиши budget guardrail, который блокирует чтение файла, если контекст >100K токенов.
4. Как часто нужно делать consistency check?
5. Спроектируй систему, которая автоматически переключает модель на более длинный контекст (200K), если короткий (32K) переполнен.

---

## Ссылки

- [[04-canary-failure]] — предыдущий case study
- [[../../../05-production/02-observability]] — observability (урок 17)
- [[../../../03-memory-and-rag/01-memory-types]] — три слоя памяти (урок 7)
- [[../../../09-advanced-rag-agents/02-long-running-agents]] — long-running агенты (урок 34)
