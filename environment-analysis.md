# OpenCode Environment Analysis
Создан: 2026-05-26
Контекст: Анализ директорий, конфигурации и компонентов opencode

---

## 1. Конфигурация: `~/.config/opencode/`

### opencode.json — главный конфиг
**Модели:**
- Основная: `deepseek/deepseek-reasoner`
- Малая: `deepseek/deepseek-chat`
- Провайдеры: DeepSeek (основной), Zhipu/GLM (запасной: 5.1, 5 Turbo, 4.7, 4.7 Flash)

**Плагины (6):**
1. `opencode-notification` — уведомления (86 MB в кэше)
2. `opencode-vibeguard` — защита от шума (68 KB)
3. `opencode-wakatime` — трекинг времени (57 MB)
4. `opencode-scheduler` — расписание (57 MB)
5. `opencode-conductor-plugin` — треки/планы (6.9 MB)
6. `opencode-background-agents` — фоновые задачи (57 MB)

Удалены: `superpowers`, `opencode-skills-collection`, `opencode-crawl4ai`, `opencode-supermemory`

**Permissions:** edit/write/bash — всё `ask`

**Фичи:**
- auto compaction + prune (reserved: 15K)
- snapshot включён
- LSP включён
- formatter включён
- autoupdate отключён
- watcher с ignore-списком (node_modules, .git, .next и т.д.)

**MCP-серверы:** отключены все (`"mcp": {}`)
Ранее были: weather, context7, playwright, filesystem — убраны за ненадобностью

**Кастомные команды:**
- `review-ru` — код-ревью на русском (DeepSeek Reasoner)
- `explain-ru` — объяснение кода на русском
- `save-dialog` — сохранить диалог в markdown (DeepSeek Chat)

**Агенты:**
- `russian-assistant` — сабагент с русским промптом (DeepSeek Reasoner)
- `conductor` — для треков (DeepSeek Chat)
- `default_agent: "build"`

### `~/.config/opencode/skills/` — активные скилы
**Статус:** пусто (0 файлов)
Раньше было 81 pointer-скил, затем 22 активных + 59 в архиве. После чистки всё удалено.

### `~/.config/opencode/skills-archive/`
**Статус:** не существует (был создан, потом удалён)

### `~/.config/opencode/skill-libraries/`
**Размер:** 0 (пусто)
Ранее содержал 75 категорий скилов (~1460 individual skills)

### `~/.config/opencode/node_modules/`
**Размер:** 57 MB
**Назначение:** серверные зависимости opencode
**Влияние на токены:** 0 токенов (не загружается в LLM)
**Ключевые пакеты:**
- `effect` — 43 MB (функциональный TS-фреймворк)
- `zod` — 5.6 MB
- `@opencode-ai/plugin` — прямая зависимость (v1.15.5)
- Остальное: yaml, uuid, toml, fast-check, kubernetes-types и т.д.
**Как работать:** не трогать, npm/bun сам управляет

### `~/.config/opencode/package.json`
```json
{ "dependencies": { "@opencode-ai/plugin": "1.15.5" } }
```

---

## 2. Кэш: `~/.cache/opencode/`

**Общий размер:** 395 MB

### `packages/` (337 MB) — кэш плагинов
- `opencode-notification@latest` — 86 MB
- `opencode-wakatime@latest` — 57 MB
- `opencode-scheduler@latest` — 57 MB
- `opencode-background-agents@latest` — 57 MB
- `pyright` — 33 MB (LSP Python)
- `yaml-language-server` — 23 MB (LSP YAML)
- `bash-language-server` — 17 MB (LSP bash)
- `opencode-conductor-plugin@latest` — 6.9 MB
- `opencode-vibeguard@latest` — 68 KB

### `bin/` (55 MB) — LSP-серверы + форматтер
- vscode-json-languageservice
- prettier
- pyright
- и зависимости

### `models.json` (2 MB)
Кэш всех моделей провайдеров (Duo, Nebius, HPC-AI, Xiaomi, GitHub Copilot, Together AI, StepFun, Inference, Poolside). Содержит model_name, контекст, цены, возможности.

### Прочее
- `version` — "21"
- `package.json` — суперпауэрс как git-зависимость
- `node_modules/` — пусто

**Влияние на токены:** 0 токенов
**Нужно ли:** да, кэш работы opencode. Без него плагины будут перекачиваться при каждом запуске.

---

## 3. Данные: `~/.local/`

**Общий размер:** 1.3 GB

### `bin/` (52 KB) — кастомные скрипты
- `aider` — Aider AI coding assistant (pipx)
- `export-dialog` — скрипт сохранения диалогов
- `opencode-db` — тулза для opencode SQLite базы
- `opencode-update-superpowers` — обновление superpowers
- `poetry` — Python package manager
- `skill-get` — загрузчик скилов
- `update-opencode-plugins` — обновление плагинов

### `pipx/` (944 MB) — Python-окружения pipx
- **932 MB** — `aider-chat` (Aider AI с torch и зависимостями)
- 12 MB — shared библиотеки

### `share/opencode/` (253 MB) — данные opencode
- `log/` — **128 MB логов** (периодически чистить)
- `tool-output/` — 22 MB выводов тулов
- `snapshot/` — 1.6 MB снимков диалогов
- `storage/` — 1.2 MB
- `opencode.db` — SQLite база (история сессий, настройки)
- `auth.json` — токены авторизации
- `delegations/` — результаты фоновых задач

### `share/skills-library/` (109 MB) — библиотека скилов
Ранее содержал 75 категорий скилов для `opencode-skills-collection`.

### `share/opencode-db/` (388 KB) — кастомная тулза
Утилита для работы с opencode SQLite базой.

### `share/opentui/` (2.7 MB) — терминальный UI

### `state/` (36 KB) — сессионные данные
- `opencode/` — состояние opencode
- `gem/` — данные gem

---

## 4. Сводка по влиянию на токены

| Компонент | Токены | Тип |
|-----------|--------|-----|
| Системный промпт | ~8-10K | В контексте LLM |
| AGENTS.md | ~2K | В контексте LLM |
| available_skills (сейчас 0) | 0 | В контексте LLM |
| Tool definitions | ~2K | В контексте LLM |
| node_modules (57 MB) | 0 | Серверный код |
| cache/ (395 MB) | 0 | Серверный кэш |
| .local/ (1.3 GB) | 0 | Данные на диске |

**Итог:** контекст LLM ~12-15K токенов для нового диалога.

---

## 5. Что можно оптимизировать

### Без потери функциональности
1. `rm -rf ~/.local/share/opencode/log/*` — очистит 128 MB логов
2. `rm -f ~/.cache/opencode/models.json` — сэкономит 2 MB (пересоздастся)

### С потерей функциональности
3. `pipx uninstall aider-chat` — уберёт 932 MB если Aider не нужен
4. `rm -rf ~/.local/share/skills-library` — уберёт 109 MB если скилы не нужны
5. Отключение плагинов в `opencode.json` уменьшит кэш packages/

---

## 6. Список установленных инструментов

### AI/LLM
- OpenCode (DeepSeek Reasoner + DeepSeek Chat)
- Aider Chat (через pipx, 932 MB)

### Python
- Poetry (package manager)
- pipx (изолированные окружения)
- Python LSP (pyright, 33 MB)

### Прочее
- YAML Language Server (23 MB)
- Bash Language Server (17 MB)
- OpenTUI

---

## 7. История изменений конфигурации

### Было (до оптимизации):
- 9 плагинов (включая superpowers, skills-collection, crawl4ai, supermemory)
- 4 MCP-сервера (weather, context7, playwright, filesystem)
- 81 активный pointer-скил
- 75 категорий скилов в библиотеке

### Стало (текущее состояние):
- 6 плагинов
- 0 MCP-серверов
- 0 активных скилов
- 0 скилов в библиотеке
