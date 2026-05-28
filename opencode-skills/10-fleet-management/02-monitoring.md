---
created: 2026-05-28
tags: [course/skills, monitoring, observability, metrics, fleet]
---

# M10-L02: Мониторинг и Observability Skills

> [!quote] Ключевая идея
> Ты не знаешь, какие skills реально работают, пока не начнёшь их измерять. Многие skills годами висят в проекте, но агент их никогда не загружает — description не совпадает с реальными задачами. **Мониторинг usage — единственный способ понять, какие skills приносят пользу, а какие — мертвый груз.**

---

## 1. Что измерять

### Core метрики

| Метрика | Что показывает | Как собирать |
|---------|---------------|-------------|
| **Load count** | Сколько раз skill был загружен | Лог загрузки агента |
| **Trigger rate** | % сессий, где skill сработал | load_count / total_sessions |
| **Token cost** | Сколько токенов съел skill | размер SKILL.md × load_count |
| **Completion rate** | Доходит ли агент до конца инструкций | финальный чекпоинт в SKILL.md |
| **User satisfaction** | Понравился ли результат | feedback после выполнения |

### Логи загрузки

```python
# skill_metrics.py — сбор метрик использования skills
import json
import os
from datetime import datetime
from collections import defaultdict


class SkillMetrics:
    """Сбор и анализ метрик использования skills."""

    def __init__(self, log_path: str = "~/.opencode/logs/skills.jsonl"):
        self.log_path = os.path.expanduser(log_path)
        self.ensure_log_dir()

    def ensure_log_dir(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_load(self, skill_name: str, session_id: str, load_time_ms: int):
        """Логирует загрузку skill."""
        record = {
            "event": "skill_load",
            "skill": skill_name,
            "session": session_id,
            "timestamp": datetime.now().isoformat(),
            "load_time_ms": load_time_ms,
        }
        self._append(record)

    def log_execution(self, skill_name: str, session_id: str,
                      tokens_used: int, completed: bool):
        """Логирует выполнение skill."""
        record = {
            "event": "skill_execution",
            "skill": skill_name,
            "session": session_id,
            "tokens": tokens_used,
            "completed": completed,
            "timestamp": datetime.now().isoformat(),
        }
        self._append(record)

    def _append(self, record: dict):
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

---

## 2. Дашборд использования

```python
class SkillDashboard:
    """Генерирует отчёт по использованию skills."""

    def __init__(self, log_path: str):
        self.log_path = log_path

    def generate_report(self) -> dict:
        records = self._load_records()

        loads = [r for r in records if r["event"] == "skill_load"]
        executions = [r for r in records if r["event"] == "skill_execution"]

        # Статистика по каждому skill
        by_skill = defaultdict(lambda: {"loads": 0, "executions": 0,
                                         "tokens": 0, "completions": 0})

        for r in loads:
            by_skill[r["skill"]]["loads"] += 1

        for r in executions:
            skill = r["skill"]
            by_skill[skill]["executions"] += 1
            by_skill[skill]["tokens"] += r.get("tokens", 0)
            if r.get("completed"):
                by_skill[skill]["completions"] += 1

        report = {
            "total_sessions": len(set(r["session"] for r in records)),
            "total_skills_loaded": len(by_skill),
            "skills": [],
        }

        for name, stats in sorted(by_skill.items()):
            completion_rate = (stats["completions"] / max(stats["executions"], 1)) * 100
            report["skills"].append({
                "name": name,
                "loads": stats["loads"],
                "executions": stats["executions"],
                "total_tokens": stats["tokens"],
                "avg_tokens_per_exec": stats["tokens"] // max(stats["executions"], 1),
                "completion_rate": round(completion_rate, 1),
            })

        return report

    def _load_records(self) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path) as f:
            return [json.loads(line) for line in f if line.strip()]
```

### Пример отчёта

```json
{
  "total_sessions": 150,
  "total_skills_loaded": 8,
  "skills": [
    {"name": "code-review", "loads": 45, "executions": 40, "total_tokens": 120000, "completion_rate": 92.5},
    {"name": "debugging", "loads": 38, "executions": 35, "total_tokens": 95000, "completion_rate": 88.6},
    {"name": "documentation", "loads": 12, "executions": 10, "total_tokens": 45000, "completion_rate": 70.0},
    {"name": "legacy-formatter", "loads": 2, "executions": 1, "total_tokens": 8000, "completion_rate": 100.0},
  ]
}
```

**Вывод:** `legacy-formatter` загрузился 2 раза за 150 сессий — возможно, он никому не нужен.

---

## 3. Аудит парка skills

Регулярный аудит должен отвечать на вопросы:

```python
class SkillAudit:
    """Аудит парка skills: что работает, что нет, что устарело."""

    def __init__(self, skills_dir: str, metrics: SkillMetrics):
        self.skills_dir = skills_dir
        self.metrics = metrics

    def run_audit(self) -> list[dict]:
        """Полный аудит всех skills в директории."""
        findings = []

        for root, dirs, files in os.walk(self.skills_dir):
            if "SKILL.md" not in files:
                continue

            skill_path = root
            skill_name = os.path.basename(root)
            skill_file = os.path.join(root, "SKILL.md")
            last_modified = os.path.getmtime(skill_file)

            findings.append({
                "skill": skill_name,
                "path": skill_path,
                "last_modified": datetime.fromtimestamp(last_modified).isoformat(),
                "age_days": (datetime.now() - datetime.fromtimestamp(last_modified)).days,
                "size_kb": round(os.path.getsize(skill_file) / 1024, 1),
                "needs_review": self._needs_review(skill_name, last_modified),
            })

        return findings

    def _needs_review(self, skill_name: str, last_modified: float) -> str:
        """Определяет, нужен ли review skill-а."""
        days_old = (datetime.now() - datetime.fromtimestamp(last_modified)).days

        if days_old > 180:  # 6 месяцев без изменений
            return "stale — review needed"
        if days_old > 90:
            return "aging — consider review"

        return "recent"
```

### Правила retirement

```python
RETIREMENT_RULES = [
    {"condition": "loads < 5 за 30 дней", "action": "warning — low usage"},
    {"condition": "completion_rate < 50%", "action": "fix or remove"},
    {"condition": "age > 6 месяцев без изменений", "action": "review"},
    {"condition": "дублирует другой skill", "action": "merge or remove"},
    {"condition": "ссылается на удалённые инструменты", "action": "remove"},
]
```

---

## 4. Skill Budgeting

Как и бюджет на LLM-вызовы, skills потребляют контекстное окно:

```python
class SkillBudget:
    """Бюджет на skills: сколько токенов они могут занимать."""

    MAX_SKILL_TOKENS = 50000  # 50K токенов на все skills

    def __init__(self):
        self.loaded_skills: dict[str, int] = {}

    def can_load(self, skill_name: str, skill_tokens: int) -> bool:
        current = sum(self.loaded_skills.values())
        if current + skill_tokens > self.MAX_SKILL_TOKENS:
            return False
        return True

    def load(self, skill_name: str, skill_tokens: int):
        self.loaded_skills[skill_name] = skill_tokens

    def unload(self, skill_name: str):
        self.loaded_skills.pop(skill_name, None)

    def report(self) -> dict:
        return {
            "total_tokens": sum(self.loaded_skills.values()),
            "budget": self.MAX_SKILL_TOKENS,
            "remaining": self.MAX_SKILL_TOKENS - sum(self.loaded_skills.values()),
            "skills": self.loaded_skills,
        }
```

---

## 5. Практика

1. Добавь `SkillMetrics()` в свой проект
2. Собери статистику за неделю работы — какие skills реально грузятся
3. Найди skill, который грузится < 3 раз в день — подумай, нужен ли он
4. Построй дашборд (хотя бы в JSON) по utilisation skills

---

## Проверь себя

1. Назови три основные метрики мониторинга skills.
2. Какой вывод можно сделать, если skill загрузился 2 раза за 150 сессий?
3. Какие правила retirement описаны в уроке?
4. Что такое skill budgeting и зачем он нужен?
5. Какие вопросы должен отвечать регулярный аудит парка skills?

## Ключевые выводы

- Метрики usage — единственный способ понять реальную ценность skill
- Skill без нагрузки — мёртвый груз в контекстном окне
- Retirement policy должна быть автоматической
- Skill budgeting защищает контекстное окно от переполнения

---

## Что дальше

→ [[03-fleet-management]] — управление парком skills в компании
→ [[04-cross-platform]] — кросс-агентная совместимость
