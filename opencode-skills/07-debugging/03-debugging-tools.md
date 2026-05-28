# Инструменты отладки

**Время чтения:** 8 мин

## Суть

Чтобы понять, почему skill работает не так, нужны инструменты: проверка файловой структуры, просмотр логов, eval-запросы и принудительная загрузка. Комбинируй методы для полной диагностики.

## Основной материал

### 1. Проверка файловой структуры

Первым делом убедись, что skill физически существует и корректен:

```bash
# Проверить наличие файла
ls skills/<skill-name>/SKILL.md

# Проверить структуру директории
ls -la skills/<skill-name>/

# Валидация frontmatter (если установлен skills-ref)
skills-ref validate skills/<skill-name>
```

**Что проверять:**
- Директория называется как `name` в frontmatter?
- Файл называется `SKILL.md` (не `skill.md`, не `*.skill.md`)?
- YAML frontmatter валиден? Есть пустая строка после `---`?
- description не превышает 1024 символов?

### 2. Логи загрузки

В зависимости от CLI:

**OpenCode:** флаг `--verbose` или переменная окружения
```bash
OP_HIDE_SKILL_OUTPUT=false opencode
```

**Claude Code:** `~/.claude/logs/` — содержит информацию о загруженных skills

**Gemini CLI:** используй `/skills list` для просмотра зарегистрированных skills

Логи показывают: какие skills были найдены, какие загружены, какие сматчились.

### 3. Eval-запросы (систематическое тестирование)

Создай набор тестовых запросов для проверки триггеринга:

```bash
# Структура eval-набора
evals/
  evals.json    # запросы + ожидания
  files/        # входные данные (если нужны)
```

Пример `evals.json`:
```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "напиши тесты для модуля calculateTax",
      "should_trigger": true
    },
    {
      "id": 2,
      "prompt": "как переименовать переменную",
      "should_trigger": false
    }
  ]
}
```

Порядок тестирования:
1. Запусти каждый запрос 3 раза (модель недетерминирована)
2. Вычисли trigger rate = количество загрузок / количество запусков
3. Цель: should_trigger = true → trigger rate > 0.5
4. Цель: should_trigger = false → trigger rate < 0.5

### 4. Принудительная загрузка

Явный вызов skill независимо от match'а:

```bash
skill("skill-name")   # OpenCode
Skill("skill-name")   # Claude Code
activate_skill("skill-name")  # Gemini CLI
```

Если при принудительной загрузке skill работает, а при естественном запросе — нет, проблема в триггеринге (description). Если не работает и при принудительной — проблема в самом SKILL.md.

### 5. Скрипт автоматизированной диагностики

```bash
#!/bin/bash
SKILL_NAME=$1
SKILL_PATH=".opencode/skills/$SKILL_NAME"

echo "=== Диагностика skill: $SKILL_NAME ==="

# Шаг 1: проверка файла
if [ -f "$SKILL_PATH/SKILL.md" ]; then
    echo "[OK] SKILL.md существует"
else
    echo "[FAIL] SKILL.md не найден по пути $SKILL_PATH"
fi

# Шаг 2: проверка frontmatter
head -10 "$SKILL_PATH/SKILL.md" | grep -q "^---" && \
    echo "[OK] YAML frontmatter найден" || \
    echo "[FAIL] YAML frontmatter отсутствует"

# Шаг 3: проверка description
DESC=$(grep -A1 "^description:" "$SKILL_PATH/SKILL.md" | tail -1)
DESC_LEN=${#DESC}
if [ $DESC_LEN -le 1024 ]; then
    echo "[OK] description: $DESC_LEN символов"
else
    echo "[FAIL] description превышает 1024 символа: $DESC_LEN"
fi

# Шаг 4: проверка name
NAME=$(grep "^name:" "$SKILL_PATH/SKILL.md" | sed 's/name: *//')
echo "[INFO] name в frontmatter: $NAME"
echo "[INFO] имя директории: $SKILL_NAME"
```

### 6. Сравнение поведения с и без skill

Для проверки ценности skill сравни вывод агента на один и тот же запрос:
- С загруженным skill
- Без skill (удали/переименуй временно)

Оценка по метрикам:
- Качество результата (pass rate по assertions)
- Количество потраченных токенов
- Время выполнения

## Кейс / пример

Skill не загружается. Диагностика:

1. `ls .opencode/skills/my-skill/SKILL.md` — файл есть
2. `skills-ref validate .opencode/skills/my-skill` — ошибка: description 1150 символов (лимит 1024)
3. Укорачиваем description до 900 символов
4. `skills-ref validate .opencode/skills/my-skill` — OK
5. Пробуем запрос — skill загружается

## Упражнение

Загрузи принудительно любой установленный skill через `skill("name")`. Проверь, сработал ли он. Затем создай запрос, который должен его триггернуть автоматически. Сравни результаты.

## Проверь себя

1. Перечисли четыре основных инструмента отладки skills, описанных в уроке.
2. Как принудительно загрузить skill для проверки?
3. Что такое eval-запросы и как они помогают в отладке?
4. Какая команда используется для валидации frontmatter skill?
5. Что нужно проверить в файловой структуре skill в первую очередь?

## Ключевые выводы

- Начинай с проверки файловой структуры и валидации frontmatter
- Логи показывают, какие skills были найдены и загружены
- Eval-запросы систематически проверяют триггеринг
- Принудительная загрузка изолирует проблему: триггеринг vs содержание skill
- Скрипт диагностики автоматизирует рутинные проверки

## Что дальше

→ [Тестирование Skills](../08-testing-security/01-testing-skills.md)
