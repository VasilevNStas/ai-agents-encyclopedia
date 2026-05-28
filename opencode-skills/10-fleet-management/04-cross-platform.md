---
created: 2026-05-28
tags: [course/skills, cross-platform, compatibility, opencode, claude-code]
---

# M10-L04: Кросс-агентная совместимость Skills

> [!quote] Ключевая идея
> Skill написанный для OpenCode, может работать в Claude Code, Cline, Gemini CLI и Copilot. Но не гарантированно. Разные агенты имеют разные возможности: инструменты, формат SKILL.md, правила загрузки. **Понимание различий — ключ к портабельности.**

---

## 1. Ландшафт AI-агентов (2026)

| Агент | Формат skills | Загрузка | Инструменты | Особенности |
|-------|--------------|----------|-------------|-------------|
| **OpenCode** | SKILL.md (agentskills.io v1) | Автотриггеринг (1%) | Read/Write/Edit/Bash/Grep/Glob | Открытая экосистема |
| **Claude Code** | SKILL.md + .claude/skills | Автотриггеринг | Read/Write/Edit/Bash/Task | Anthropic-native |
| **Cline** | SKILL.md | Автотриггеринг + ручной | Все MCP-инструменты | VS Code интеграция |
| **Gemini CLI** | SKILL.md (агентскриллс) | Автотриггеринг | Google-экосистема | Google models |
| **Copilot** | .github/skills (YAML-based) | Ручной вызов | GitHub API | Только для GitHub |

---

## 2. Что портабельно, а что нет

### Портабельно (работает везде)

```yaml
# SKILL.md — портабельный skill
name: code-review
description: Review code for security vulnerabilities and quality issues

# ↑ Эти поля работают во всех агентах

instructions: |
  ## Process
  1. Read the code
  2. Check for security issues
  3. Check for quality issues
  4. Format report

  ## Output Format
  Use markdown with severity labels.

# ↑ Markdown-инструкции работают везде
```

### Не портабельно (агент-специфично)

| Элемент | Где работает | Комментарий |
|---------|-------------|-------------|
| `allowed-tools` | OpenCode, Claude Code | Не поддерживается Cline |
| `depends_on` | OpenCode | Экспериментально |
| `allowed-tokens` | OpenCode | Экспериментально |
| `hard-gates` | Claude Code | Не поддерживается OpenCode |
| `max-execution-time` | Claude Code | Нет в spec |
| MCP-инструменты | OpenCode, Claude Code, Cline | Зависит от MCP-сервера |

---

## 3. Стратегия портабельности

### Уровень 1: Базовый (везде)

Пиши skills так, чтобы они работали во всех агентах:

```markdown
# SKILL.md — уровень 1: портабельный

name: security-scan
description: Scan code for common security vulnerabilities

instructions: |
  1. Read all Python files in the project
  2. Check for: SQL injection, XSS, hardcoded secrets, eval()
  3. Report findings in markdown table

  Используй только базовые инструменты: Read, Grep, Bash.
  Избегай агент-специфичных фич.
```

### Уровень 2: Адаптивный (агент-детект)

Skill определяет, в каком агенте работает, и адаптируется:

```markdown
name: deploy-check
description: Pre-deployment checklist

instructions: |
  ## Step 1: Detect environment
  Check if OPENCODE_HOME or CLAUDE_CODE_HOME env var exists.

  ## Step 2: Adapt workflow
  - Если OpenCode → используй `task` для параллельных проверок
  - Если Claude Code → используй `Tool` для последовательных
  - Если Cline → используй MCP-инструменты

  ## Step 3: Run checks
  В любом окружении выполни:
  1. Lint all changed files
  2. Run test suite
  3. Check for secrets in code
```

### Уровень 3: С раздельными файлами

```bash
deploy-check/
├── SKILL.md              # общие инструкции
├── SKILL.opencode.md     # OpenCode-специфичные
├── SKILL.claude.md       # Claude Code-специфичные
└── SKILL.cline.md        # Cline-специфичные
```

---

## 4. Tool Mapping между агентами

| Задача | OpenCode | Claude Code | Cline |
|--------|----------|-------------|-------|
| Чтение файла | `Read` | `Read` | `read_file` |
| Запись файла | `Write` | `Write` | `write_to_file` |
| Редактирование | `Edit` | `Edit` | `search_and_replace` |
| Поиск по паттерну | `Grep` | `Grep` | `grep_search` |
| Поиск файлов | `Glob` | `Glob` | `list_files` |
| Bash-команда | `Bash` | `Bash` | `execute_command` |
| Подзадача | `Task` | — | `ask_followup_question` |

```markdown
# Tool mapping в инструкциях

name: project-audit
description: Full project structure audit

instructions: |
  ## How to read this skill for different agents

  When you see "Read file X":
  - OpenCode → используй Read(X)
  - Claude Code → используй Read(X)
  - Cline → используй read_file(X)

  When you see "Search for pattern Y":
  - OpenCode → используй Grep(Y)
  - Claude Code → используй Grep(Y)
  - Cline → используй grep_search(Y)
```

---

## 5. Тестирование совместимости

```python
# test_cross_platform.py
import os
import subprocess


CROSS_PLATFORM_TESTS = [
    {
        "agent": "opencode",
        "command": "opencode --skill test-skill --eval 'test query'",
        "expected": "SKILL_ACTIVATED",
    },
    {
        "agent": "claude",
        "command": "claude --skill test-skill --prompt 'test query'",
        "expected": "SKILL_ACTIVATED",
    },
]


def test_skill_on_agent(skill_name: str, agent: str, command: str, expected: str) -> dict:
    """Тестирует skill на конкретном агенте."""
    try:
        result = subprocess.run(
            command.format(skill=skill_name),
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = expected in result.stdout
        return {
            "agent": agent,
            "skill": skill_name,
            "passed": passed,
            "stdout": result.stdout[:200],
            "stderr": result.stderr[:200],
        }
    except subprocess.TimeoutExpired:
        return {
            "agent": agent,
            "skill": skill_name,
            "passed": False,
            "error": "timeout",
        }
    except FileNotFoundError:
        return {
            "agent": agent,
            "skill": skill_name,
            "passed": False,
            "error": "agent not installed",
        }
```

---

## 6. Практика

1. Возьми свой любимый skill и проверь его на 2 разных агентах
2. Найди хотя бы одну конструкцию, которая работает в OpenCode, но не в Claude Code
3. Перепиши skill на уровень 2 (адаптивный)
4. Составь tool mapping для своего проекта

---

## Проверь себя

1. Какие AI-агенты поддерживают формат SKILL.md?
2. Назови три уровня портабельности skills.
3. Какие элементы SKILL.md не портабельны между агентами?
4. Какой подход используется для адаптивного skill (уровень 2)?
5. Почему tool mapping важен для кросс-агентных skills?

## Ключевые выводы

- Базовые SKILL.md портабельны между OpenCode, Claude Code, Cline
- Agent-специфичные фичи (allowed-tools, hard-gates) не портабельны
- Три уровня портабельности: базовый → адаптивный → раздельные файлы
- Tool mapping — обязательная документация для кросс-агентных skills
- Тестирование на каждом агенте — единственный способ убедиться

---

## Что дальше

→ [[../../09-performance/01-context-window-impact]] — производительность skills (повторение)
→ [[index|На главную курса Skills]]
