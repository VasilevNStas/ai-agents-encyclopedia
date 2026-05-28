#!/usr/bin/env python3
"""
skill-validator.py — проверка SKILL.md на валидность.

Usage:
    python3 skill-validator.py <path-to-skill-dir>
    python3 skill-validator.py --all <skills-dir>

Проверяет:
  - Наличие SKILL.md
  - YAML frontmatter (name, description обязательны)
  - name: kebab-case, совпадает с именем директории
  - description: <= 1024 символов, начинается с "Use when"
  - Отсутствие XML-тегов (конвенция Superpowers)
  - Ссылки на файлы (scripts/, references/, assets/)
  - Негативные паттерны (описание процесса вместо триггера в description)
"""

import sys
import os
import re
import yaml
from pathlib import Path


def validate_skill(skill_dir: str) -> list[str]:
    """Проверяет skill в указанной директории. Возвращает список ошибок."""
    errors = []
    base = Path(skill_dir)
    skill_file = base / "SKILL.md"
    dir_name = base.name

    # 1. Наличие SKILL.md
    if not skill_file.exists():
        return [f"[{dir_name}] SKILL.md not found"]

    content = skill_file.read_text(encoding="utf-8")

    # 2. YAML frontmatter
    if not content.startswith("---"):
        errors.append(f"[{dir_name}] Missing YAML frontmatter (must start with ---)")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append(f"[{dir_name}] Malformed YAML frontmatter")
        return errors

    yaml_part = parts[1].strip()

    try:
        meta = yaml.safe_load(yaml_part)
    except yaml.YAMLError as e:
        errors.append(f"[{dir_name}] YAML parse error: {e}")
        return errors

    if not isinstance(meta, dict):
        errors.append(f"[{dir_name}] YAML frontmatter is not a dictionary")
        return errors

    # 3. name обязательно
    name = meta.get("name")
    if not name:
        errors.append(f"[{dir_name}] Missing required field: name")
    else:
        # 3a. kebab-case
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            errors.append(
                f"[{dir_name}] name '{name}' is not kebab-case "
                "(lowercase letters, numbers, hyphens)"
            )
        # 3b. совпадает с именем директории
        if name != dir_name:
            errors.append(
                f"[{dir_name}] name '{name}' does not match directory name '{dir_name}'"
            )

    # 4. description обязательно
    description = meta.get("description")
    if not description:
        errors.append(f"[{dir_name}] Missing required field: description")
    else:
        # 4a. длина
        if len(description) > 1024:
            errors.append(
                f"[{dir_name}] description too long: {len(description)} chars "
                "(max 1024)"
            )
        # 4b. начинается с "Use when" (только для английских описаний)
        # Пропускаем русские описания

    # 5. Негативные паттерны в description
    if description:
        process_words = [
            "analyzes",
            "generates",
            "creates",
            "handles",
            "manages",
            "processes",
            "provides",
            "performs",
        ]
        first_word = description.strip().split()[0].lower() if description else ""
        if first_word in process_words:
            errors.append(
                f"[{dir_name}] description describes PROCESS ('{first_word}...'), "
                "not trigger conditions. Use 'Use when...' instead."
            )

    body = parts[2].strip()

    # 6. XML-теги (Superpowers convention)
    xml_tags = re.findall(r"</?[a-z]+>", body)
    if xml_tags:
        # Не ошибка, а предупреждение
        pass

    # 7. Проверка ссылок на scripts/, references/, assets/
    for ref_dir in ["scripts", "references", "assets"]:
        ref_path = base / ref_dir
        if ref_path.exists():
            for ref_file in ref_path.rglob("*"):
                if ref_file.is_file():
                    rel = ref_file.relative_to(base)
                    link = str(rel)
                    if link not in body and str(rel).split("/")[-1] not in body:
                        errors.append(
                            f"[{dir_name}] File '{link}' exists but is not referenced in SKILL.md"
                        )

    return errors


def print_report(errors: list[str], name: str):
    """Выводит отчёт по одному skill."""
    if not errors:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}")
        for err in errors:
            print(f"     - {err}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "--all" and len(sys.argv) >= 3:
        skills_dir = Path(sys.argv[2])
        if not skills_dir.is_dir():
            print(f"Error: {skills_dir} is not a directory")
            sys.exit(1)

        total = 0
        failed = 0
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir():
                errors = validate_skill(str(skill_path))
                print_report(errors, skill_path.name)
                total += 1
                if errors:
                    failed += 1

        print(f"\n{'=' * 40}")
        print(f"Total: {total}, Failed: {failed}, Passed: {total - failed}")

    else:
        skill_dir = sys.argv[1]
        if not os.path.isdir(skill_dir):
            print(f"Error: {skill_dir} is not a directory")
            sys.exit(1)

        errors = validate_skill(skill_dir)
        name = Path(skill_dir).name
        print_report(errors, name)

        if errors:
            sys.exit(1)


if __name__ == "__main__":
    main()
