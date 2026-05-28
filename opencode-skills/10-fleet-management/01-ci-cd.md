---
created: 2026-05-28
tags: [course/skills, ci-cd, testing, automation, fleet]
---

# M10-L01: CI/CD для Skills

> [!quote] Ключевая идея
> Skill — это код. Как и код, он должен проходить валидацию, тестироваться и развёртываться через CI/CD. Без пайплайна ты узнаешь, что skill сломался, когда агент перестанет его загружать. **Skill CI/CD = валидация структуры + тест триггеринга + проверка инструкций.**

---

## Проблема: skill — это хрупкий артефакт

Skill ломается не так, как код:
- **Не синтаксически, а семантически:** SKILL.md валиден, но description не совпадает с реальной задачей
- **Не с ошибкой, а молчанием:** агент просто не загружает skill
- **Не в рантайме, а в discovery:** проблема проявляется только когда агент решает, нужен ли skill

Поэтому CI/CD для skills должен проверять **три слоя**:

```yaml
# .github/workflows/skill-ci.yml
name: Skill CI
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Validate SKILL.md structure
        run: python scripts/skill-validator.py skills/

      - name: Test skill triggering
        run: python scripts/test-triggering.py skills/
```

---

## Слой 1: Валидация структуры

Проверяет, что SKILL.md корректен и все поля заполнены:

```python
# scripts/skill-validator.py
import yaml
import os
import sys
import re


def validate_skill(path: str) -> list[str]:
    errors = []

    if not os.path.exists(os.path.join(path, "SKILL.md")):
        errors.append(f"{path}: missing SKILL.md")
        return errors

    with open(os.path.join(path, "SKILL.md")) as f:
        content = f.read()

    # Парсинг YAML frontmatter
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        errors.append(f"{path}: invalid YAML frontmatter")
        return errors

    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        errors.append(f"{path}: YAML parse error: {e}")
        return errors

    # Обязательные поля
    required_fields = ["name", "description"]
    for field in required_fields:
        if field not in meta:
            errors.append(f"{path}: missing required field '{field}'")

    # Ограничения
    if meta.get("description") and len(meta["description"]) > 1024:
        errors.append(f"{path}: description exceeds 1024 chars")

    return errors


def main():
    skills_dir = sys.argv[1]
    all_errors = []

    for root, dirs, files in os.walk(skills_dir):
        if "SKILL.md" in files:
            errors = validate_skill(root)
            all_errors.extend(errors)

    if all_errors:
        for e in all_errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    print(f"OK: {skills_dir} validated")


if __name__ == "__main__":
    main()
```

---

## Слой 2: Тест триггеринга

Проверяет, что skill загружается по ожидаемому запросу:

```python
# scripts/test-triggering.py
import yaml
import json
import re
import sys
from pathlib import Path


TRIGGER_TESTS = {
    "code-review": [
        "проверь код на безопасность",
        "сделай code review этого PR",
        "найди уязвимости в коде",
    ],
    "debugging": [
        "почему падает тест",
        "помоги найти баг",
        "ошибка в production",
    ],
    "documentation": [
        "напиши документацию к модулю",
        "создай README",
        "опиши API",
    ],
}


def test_triggering(skill_name: str, description: str, test_queries: list[str]) -> dict:
    """Симулирует discovery: проверяет совпадение description с запросом."""
    results = []
    desc_lower = description.lower()

    for query in test_queries:
        q_lower = query.lower()

        # Простейшая эвристика: пересечение ключевых слов
        query_words = set(q_lower.split())
        desc_words = set(desc_lower.split())
        overlap = len(query_words & desc_words) / max(len(query_words), 1)

        should_trigger = overlap > 0.1  # имитация порога 1%

        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "overlap": round(overlap, 3),
        })

    return {"skill": skill_name, "results": results}


def main():
    skills_dir = Path(sys.argv[1])
    all_results = []

    for sk_dir in skills_dir.iterdir():
        sk_file = sk_dir / "SKILL.md"
        if not sk_file.exists():
            continue

        with open(sk_file) as f:
            content = f.read()

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            continue

        meta = yaml.safe_load(match.group(1))
        name = meta.get("name", sk_dir.name)
        description = meta.get("description", "")

        tests = TRIGGER_TESTS.get(name, [
            "проанализируй это",
            "сделай это",
            "помоги с этим",
        ])

        result = test_triggering(name, description, tests)
        all_results.append(result)

    print(json.dumps(all_results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

---

## Слой 3: Интеграционный тест

Проверяет, что агент реально загружает skill:

```python
# scripts/test-skill-execution.sh
#!/bin/bash
# Тестирует, что skill загружается в OpenCode

SKILL_NAME=$1
TEST_PROMPT=$2

echo "Testing skill: $SKILL_NAME"
echo "Prompt: $TEST_PROMPT"

# Запуск OpenCode с принудительной загрузкой skill
# и проверкой, что инструкции из skill были применены
opencode --eval "
  skill(\"$SKILL_NAME\")
  /instruction: выполни задачу и напиши 'SKILL_ACTIVATED' в начале ответа
  $TEST_PROMPT
" 2>&1 | grep -q "SKILL_ACTIVATED"

if [ $? -eq 0 ]; then
  echo "PASS: $SKILL_NAME activated successfully"
  exit 0
else
  echo "FAIL: $SKILL_NAME did not activate"
  exit 1
fi
```

---

## Пайплайн целиком

```yaml
# .github/workflows/skills.yml
name: Skills Pipeline

on:
  push:
    paths:
      - 'skills/**/*.md'
      - 'skills/**/*.py'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate structure
        run: python scripts/skill-validator.py skills/

  test-triggering:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test triggering
        run: python scripts/test-triggering.py skills/

  integration:
    needs: test-triggering
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test skill execution
        run: |
          for sk in skills/*/; do
            name=$(basename $sk)
            bash scripts/test-skill-execution.sh $name "test query for $name"
          done
```

---

## Практика

1. Добавь `skill-validator.py` в свой проект
2. Создай GitHub Action, который запускает его на каждый PR
3. Добавь тест триггеринга для одного своего skill
4. Убедись, что пайплайн падает при битом description

---

## Проверь себя

1. Какие три слоя проверяет CI/CD для skills?
2. Какие обязательные поля должны быть в frontmatter SKILL.md?
3. Что проверяет тест триггеринга?
4. Какое максимальное количество символов допускается в description?
5. На какие события должен срабатывать CI/CD пайплайн?

## Ключевые выводы

- Skill CI/CD проверяет 3 слоя: структуру, триггеринг, исполнение
- Валидатор ловит битый YAML, отсутствие полей, превышение лимитов
- Тест триггеринга проверяет semantic match description → задача
- CI/CD должен запускаться на каждый PR, меняющий skills/

---

## Что дальше

→ [[02-monitoring]] — следующий урок: мониторинг и observability skills
