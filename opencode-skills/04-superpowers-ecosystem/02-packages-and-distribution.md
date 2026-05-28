# Публикация и дистрибуция пакетов skills

**Время чтения:** 8 мин

## Суть

Любой может опубликовать собственный пакет skills в npm registry. Пользователи устанавливают его через привычный `npm install`, а агент автоматически обнаруживает skills при старте. Версионирование через semver помогает управлять изменениями.

## Основной материал

### Публикация собственного пакета — пошагово

1. Создай структуру пакета:
```
my-skills/
├── package.json
├── skills/
│   ├── first-skill/
│   │   └── SKILL.md
│   └── second-skill/
│       └── SKILL.md
└── README.md
```

2. Заполни package.json:
```json
{
  "name": "@user/my-skills",
  "version": "1.0.0",
  "description": "Мои skills для AI-агента",
  "superpowers": {
    "skills": ["skills/*"]
  },
  "keywords": ["superpowers", "opencode"],
  "license": "MIT"
}
```

3. Опубликуй в npm:
```bash
npm login
npm publish
```

### Версионирование (semver)

Skills подчиняются семантическому версионированию:
- **Мажор (1.0.0 → 2.0.0)** — breaking change: skill меняет ожидаемый формат ввода/вывода
- **Минор (1.0.0 → 1.1.0)** — новый skill в пакете, новая опциональная секция
- **Патч (1.0.0 → 1.0.1)** — исправление ошибок в инструкциях, уточнение формулировок

### Changelog

Документировать изменения важно, потому что:
- Пользователь может не заметить, что skill изменился
- Breaking change может сломать автоматизацию

```markdown
# Changelog

## [2.0.0] - 2026-03-15
### Changed
- `code-review`: изменён формат вывода (теперь Markdown, а не JSON)
### Removed
- `legacy-checker`: удалён, функциональность перенесена в `code-review`
```

### Источники установки

```bash
# Из npm registry
npm install @user/my-skills

# Из git-репозитория
npm install github:user/my-skills

# С локального пути (разработка)
npm install ./my-skills
```

### Дистрибуция без npm

Не все пользователи работают с npm. Альтернативы:
- **Прямое копирование** — скачать архив и скопировать в `.opencode/skills/`
- **Git submodules** — подключить репозиторий и создать симлинк
- **Symlinks** — `ln -s /path/to/skills ~/.opencode/skills/`

```bash
# Пример с git submodule
git submodule add https://github.com/user/my-skills vendor/my-skills
ln -s vendor/my-skills/skills/* .opencode/skills/
```

### Где искать готовые skills

- [github.com/anthropics/skills](https://github.com/anthropics/skills) — официальные skills от Anthropic
- [github.com/obra/superpowers](https://github.com/obra/superpowers) — Superpowers
- [npm registry](https://www.npmjs.com/search?q=keywords:superpowers) — все пакеты с тегом superpowers
- [aitmpl.com/skills](https://aitmpl.com/skills) — агрегатор skills
- [skills.sh](https://skills.sh) — каталог skills

## Кейс / пример

Ты опубликовал пакет `@user/deploy-skills` с тремя skills. Через месяц один из skills содержит небезопасную инструкцию:

1. Исправляешь SKILL.md
2. Меняешь версию: `patch`
3. Обновляешь CHANGELOG.md
4. Публикуешь: `npm publish`
5. Пользователи узнают через `npm outdated` и `npm update`

## Упражнение

Создай минимальный пакет skills:
1. `mkdir -p my-test-skills/skills/hello-skill`
2. Создай `package.json` с флагом superpowers
3. Напиши SKILL.md
4. Установи локально через `npm link` или копированием в `.opencode/skills/`
5. Проверь, что агент видит новый skill

## Проверь себя

1. Какие шаги включает публикация собственного пакета skills?
2. Какое версионирование применяется к skills и что означают мажор, минор и патч?
3. Почему ведение CHANGELOG особенно важно для пакетов skills?
4. Назовите минимум два способа дистрибуции skills без npm.
5. Где искать готовые skills? Приведите два источника.

## Ключевые выводы

- Публикация пакета skills ничем не отличается от публикации обычного npm-пакета
- Semver: мажор = breaking change, минор = новый skill, патч = исправление
- Автообнаружение работает без настройки: достаточно флага `superpowers`
- npm — основной, но не единственный способ дистрибуции
- CHANGELOG обязателен — пользователи не видят уведомлений об обновлениях

## Что дальше

→ [Пишем первый Skill](../05-writing-skills/01-first-skill.md)
