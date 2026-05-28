# opencode — конфигурация и окружение

## Основной конфиг
- **Файл:** `~/.config/opencode/opencode.json`
- **Схема:** https://opencode.ai/config.json

## Провайдеры (модели AI)
| Провайдер | API-ключ в env | Модели |
|---|---|---|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-reasoner` (основная), `deepseek-chat` (малая) |
| **OpenAI** | `OPENAI_API_KEY` | стандартные модели |
| **Qwen (DashScope)** | `QWENCLOUD_API_KEY` | `qwen-coder-plus`, `qwen-plus`, `qwen-max`, `qwq-plus`, `qwen-turbo`, `qwen3.7-max` |
| **Zhipu (GLM)** | `ZHIPU_API_KEY` | `glm-5.1`, `glm-5-turbo`, `glm-4.7`, `glm-4.7-flash` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `openrouter/free`, `qwen/qwen3-coder:free`, `qwen/qwen3-30b-a3b` |

## Плагины
- `opencode-notification` — уведомления
- `opencode-vibeguard` — защита
- **`opencode-wakatime`** — трекинг времени (WakaTime, папка `~/.wakatime`)
- `opencode-scheduler` — планировщик задач
- `opencode-conductor-plugin` — conductor-агент
- `opencode-background-agents` — фоновые агенты

## Агенты
- **`russian-assistant`** — отвечает на русском, модель `deepseek-reasoner`
- **`conductor`** — модель `deepseek-chat`
- **`default_agent`: `build`**

## Пользовательские команды
| Команда | Описание |
|---|---|
| `review-ru` | Код-ревью на русском |
| `explain-ru` | Объяснение кода на русском |
| `save-dialog` | Сохранить диалог в markdown (использует `~/.local/bin/export-dialog`) |

## Скрипты в `~/.local/bin/`
| Скрипт | Назначение |
|---|---|
| `export-dialog` | Экспорт диалогов opencode |
| `opencode-db` | Утилита работы с БД opencode |
| `opencode-update-superpowers` | Обновление конфигурации opencode |
| `update-opencode-plugins` | Обновление плагинов |
| `skill-get` | Загрузка навыков opencode |
| `poetry` | Python-пакетный менеджер (symlink, не opencode) |

## Другие конфиги
- `~/.config/opencode/AGENTS.md` — инструкции для агента по умолчанию
- `~/.config/opencode/tui.json` — настройки интерфейса
- `~/.config/opencode/agents/` — дополнительные агенты
- `~/.config/opencode/rules/` — правила
- `~/.config/opencode/skills/` — навыки

## Ключевые настройки
- **`autoupdate: false`** — автообновление отключено
- **`permissions`** — `edit/write/bash` все `ask` (спрашивать)
- **`snapshot: true`** — снапшоты контекста включены
- **`lsp: true`** — LSP поддержка включена
- **`formatter: true`** — форматирование включено

## Окружение (Language Runtimes)
- **Python:** pyenv — версии 3.12.13, 3.13.13, 3.14.5 (активная: 3.13.13)
- **Ruby:** RVM — версии 3.4.7, 4.0.5 (активная: 4.0.5, Rails 8.1.3)
- **Node:** через brew
