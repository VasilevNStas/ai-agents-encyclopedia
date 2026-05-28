---
created: 2026-05-28
tags: [course/skills, fleet-management, versioning, enterprise, lifecycle]
---

# M10-L03: Управление парком Skills

> [!quote] Ключевая идея
> Один skill — это просто. 50 skills в команде из 10 разработчиков — это **управление парком**: версионирование, миграция, retirement, code review для .md-файлов. Без системы skills превращаются в свалку: половина не работает, четверть устарела, остальные дублируют друг друга.

---

## 1. Инвентаризация: знай свой парк

```bash
# Быстрая инвентаризация всех skills в проекте
find .opencode/skills -name "SKILL.md" | while read f; do
  name=$(head -5 "$f" | grep "^name:" | cut -d: -f2 | xargs)
  desc=$(head -10 "$f" | grep "^description:" | cut -d: -f2- | xargs)
  echo "$name | $desc | $f"
done
```

### Манифест парка

```yaml
# skills-manifest.yaml — описание всех skills проекта
version: 1
updated: 2026-05-28

skills:
  - name: code-review
    version: 2.1.0
    path: skills/code-review/
    owner: team-core
    status: active
    trigger_rate: 0.30  # 30% сессий
    avg_tokens: 4500

  - name: legacy-migration
    version: 0.9.0
    path: skills/legacy-migration/
    owner: team-platform
    status: beta  # ещё тестируется
    trigger_rate: 0.05

  - name: old-formatter
    version: 1.0.0
    path: skills/old-formatter/
    owner: unknown
    status: deprecated  # заменён на code-formatter
    deprecation_date: 2026-04-01
    replacement: code-formatter
```

---

## 2. Версионирование skills

### Когда менять версию

| Изменение | Тип | Пример |
|-----------|-----|--------|
| Новые инструкции | Minor | Добавлен шаг в процесс |
| Новые требования к среде | Minor | Новый обязательный инструмент |
| Удаление инструкций | Major | Удалён критический шаг |
| Изменение триггера | Major | Новое description |
| Исправление опечаток | Patch | Грамматика, форматирование |

### Changelog

```markdown
# Changelog

## [2.1.0] - 2026-05-28
### Added
- Шаг валидации перед отправкой отчёта
- Поддержка JSON output format

### Fixed
- Опечатка в description (теперь триггерится на "security audit")

## [2.0.0] - 2026-04-15
### Changed
- Полное обновление процесса ревью: теперь 4 этапа вместо 3
- Новый формат отчёта

### Removed
- Шаг автоматического исправления (перенесён в отдельный skill)
```

---

## 3. Code Review для SKILL.md

SKILL.md — это код. Его нужно ревьюить как код:

```markdown
## Code Review Checklist for Skills

### Структура
- [ ] Есть YAML frontmatter с name и description
- [ ] description ≤ 1024 символов
- [ ] description отражает реальную задачу (проверить тест-запросами)
- [ ] Нет дублирования с другими skills (проверить grep по описаниям)

### Инструкции
- [ ] Шаги выполнимы агентом (нет требований к GUI)
- [ ] Нет противоречий с AGENTS.md проекта
- [ ] Примеры валидны (не содержат устаревшего синтаксиса)
- [ ] Проверена обратная совместимость

### Безопасность
- [ ] Нет опасных паттернов (rm -rf, curl | bash)
- [ ] Нет запроса чувствительных данных
- [ ] Инструменты имеют минимально необходимые права

### Производительность
- [ ] Размер SKILL.md < 5000 токенов
- [ ] Нет избыточных примеров
- [ ] references не дублируют content
```

---

## 4. Миграция при breaking changes

```python
# migrate_skills.py — автоматическая миграция skills
import os
import re
import shutil
from datetime import datetime


class SkillMigration:
    """Управление миграцией skills при обновлениях."""

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.backup_dir = os.path.join(skills_dir, ".backups")

    def backup(self, skill_name: str):
        """Создаёт backup перед миграцией."""
        src = os.path.join(self.skills_dir, skill_name)
        if not os.path.exists(src):
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(self.backup_dir, f"{skill_name}_{ts}")
        os.makedirs(self.backup_dir, exist_ok=True)
        shutil.copytree(src, dst)
        print(f"Backup: {src} → {dst}")

    def update_description(self, skill_name: str, new_description: str):
        """Обновляет description с backup."""

        self.backup(skill_name)

        sk_file = os.path.join(self.skills_dir, skill_name, "SKILL.md")
        with open(sk_file) as f:
            content = f.read()

        # Замена description в YAML frontmatter
        pattern = r"(^description:).*$"
        replacement = f"\\1 {new_description}"
        content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)

        with open(sk_file, "w") as f:
            f.write(content)

        print(f"Updated: {skill_name} description")

    def deprecate(self, skill_name: str, replacement: str = ""):
        """Помечает skill как deprecated."""

        self.backup(skill_name)

        sk_file = os.path.join(self.skills_dir, skill_name, "SKILL.md")
        with open(sk_file) as f:
            content = f.read()

        # Добавляем deprecation notice
        deprecation_note = (
            "\n> [!warning] DEPRECATED\n"
            f"> Этот skill больше не поддерживается."
        )
        if replacement:
            deprecation_note += f" Используйте `{replacement}` вместо него.\n"

        content += deprecation_note

        # Добавляем статус в frontmatter
        content = content.replace(
            "status: active",
            "status: deprecated"
        )

        with open(sk_file, "w") as f:
            f.write(content)

        print(f"Deprecated: {skill_name}")


# Использование
migration = SkillMigration(".opencode/skills")
migration.deprecate("old-formatter", replacement="code-formatter")
migration.update_description("code-review", "Review code for security, quality and style")
```

---

## 5. Политика управления парком

```yaml
# skills-policy.yaml — политика управления skills

inventory:
  auto_discovery: true  # сканировать директории skills
  manifest_required: true  # каждый skill в манифесте
  orphan_detection: true  # найти skills вне манифеста

versioning:
  semver: true
  changelog_required: true
  backup_before_migration: true

retirement:
  auto_retire_after_days: 180  # 6 месяцев без изменений
  low_usage_threshold: 0.02  # < 2% сессий
  notify_before_removal: 14  # дней предупреждения

code_review:
  required_for: [new, major_update, description_change]
  checklist: skills-policy.yaml
  min_approvers: 1

monitoring:
  track_loads: true
  track_completion: true
  weekly_report: true
  alert_on_degradation: true  # completion_rate < 50%
```

---

## 6. Практика

1. Составь манифест всех skills в твоём проекте
2. Найди хотя бы один skill, который не обновлялся > 3 месяцев
3. Проверь, нет ли дублирующихся description у разных skills
4. Проведи code review одного чужого SKILL.md по чеклисту

---

## Проверь себя

1. Какие поля должен содержать манифест парка skills?
2. Когда изменение SKILL.md считается major-версией?
3. Какие разделы должен включать code review checklist для skills?
4. Что должно происходить при breaking changes в skill?
5. Какие правила retirement рекомендованы для skills без нагрузки?

## Ключевые выводы

- Парк skills требует управления: инвентаризация, версионирование, retirement
- SKILL.md — код, его нужно ревьюить как код
- Breaking changes требуют миграции с backup
- Skills без нагрузки должны удаляться

---

## Что дальше

→ [[04-cross-platform]] — кросс-агентная совместимость
