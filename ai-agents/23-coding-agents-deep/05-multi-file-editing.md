---
created: 2026-05-28
tags: [course/coding-agents-deep, multi-file, refactoring, diff, git]
status: active
---

# Урок 23.5: Multi-file Editing & Refactoring

> [!quote] Ключевая идея
> Реальный coding agent не пишет одну функцию. Он добавляет импорт, создаёт новый файл, обновляет тесты, рефакторит связанные модули, запускает CI. Multi-file editing — ключевое отличие toy agent от production.

---

## 1. Diff-based Editing

```python
class DiffEditor:
    """Редактирование через унифицированный diff."""

    async def apply_edit(self, file_path: str, instruction: str) -> dict:
        """Применяет изменение к файлу через diff."""

        with open(file_path) as f:
            original = f.read()

        # Генерируем diff
        diff = await self._generate_diff(original, instruction)

        # Применяем diff
        new_content = self._apply_diff(original, diff)

        # Валидация
        issues = await self._validate(new_content)
        if issues:
            diff = await self._fix_diff(diff, issues)
            new_content = self._apply_diff(original, diff)

        # Сохраняем
        with open(file_path, "w") as f:
            f.write(new_content)

        return {
            "file": file_path,
            "diff": diff,
            "changes": self._count_changes(diff),
        }

    async def _generate_diff(self, original: str, instruction: str) -> str:
        prompt = f"""Generate a unified diff for:
File: {file_path}
Instruction: {instruction}

Original:
```python
{original[:1000]}
```

Return ONLY the diff (unified format):"""
        return await self.llm.generate(prompt)
```

---

## 2. Cross-file Refactoring

```python
class CrossFileRefactorer:
    """Рефакторинг, затрагивающий несколько файлов."""

    async def refactor(self, plan: list[dict]) -> list[dict]:
        """Выполняет multi-file рефакторинг по плану."""

        results = []
        for step in plan:
            if step["action"] == "edit":
                result = await self._edit_file(step["file"], step["changes"])
            elif step["action"] == "create":
                result = await self._create_file(step["file"], step["content"])
            elif step["action"] == "delete":
                result = await self._delete_file(step["file"])
            elif step["action"] == "rename":
                result = await self._rename_file(step["from"], step["to"])

            results.append(result)

            # Update references in other files
            if step["action"] in ["rename", "delete"]:
                await self._update_references(step)

        return results

    async def _update_references(self, change: dict):
        """Обновляет все ссылки на изменённый файл/символ."""

        symbol = change.get("symbol", change.get("from"))
        new_name = change.get("to") or change.get("new_symbol")

        for file_path in Path(self.repo_path).rglob("*.py"):
            with open(file_path) as f:
                content = f.read()

            if symbol in content:
                log(f"Updating references in {file_path}")
                content = content.replace(symbol, new_name)
                with open(file_path, "w") as f:
                    f.write(content)

    async def rename_function(self, old_name: str, new_name: str, scope: str = "repo"):
        """Переименование функции с обновлением всех вызовов."""

        # 1. Find definition
        def_file = await self._find_definition(old_name)

        # 2. Rename in definition
        await self._edit_file(def_file, f"Rename {old_name} to {new_name}")

        # 3. Find all references
        references = await self._find_references(old_name)

        # 4. Update all references
        for ref in references:
            await self._edit_file(ref["file"],
                f"In {ref['file']}:{ref['line']}, rename {old_name} to {new_name}")
```

---

## 3. Import Management

```python
class ImportManager:
    """Управление импортами при генерации кода."""

    def get_imports(self, file_path: str) -> list[str]:
        """Извлекает все импорты из файла."""
        import ast
        with open(file_path) as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}" for alias in node.names)
        return imports

    async def add_import(self, file_path: str, needed_import: str) -> bool:
        """Добавляет import если его нет."""
        imports = self.get_imports(file_path)
        if needed_import in imports:
            return False

        # Определяем тип импорта
        if "." in needed_import:
            module, name = needed_import.rsplit(".", 1)
            import_stmt = f"from {module} import {name}"
        else:
            import_stmt = f"import {needed_import}"

        # Добавляем после последнего существующего импорта
        with open(file_path) as f:
            lines = f.readlines()

        last_import = -1
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")):
                last_import = i

        lines.insert(last_import + 1, import_stmt + "\n")
        with open(file_path, "w") as f:
            f.writelines(lines)

        return True
```

---

## 4. Safe Rollback

```python
class SafeFileEditor:
    """Безопасное редактирование с возможностью отката."""

    def __init__(self):
        self.backups = {}  # {file_path: backup_content}

    async def edit(self, file_path: str, new_content: str) -> bool:
        """Редактирует с backup."""

        # Backup
        with open(file_path) as f:
            self.backups[file_path] = f.read()

        # Write
        with open(file_path, "w") as f:
            f.write(new_content)

        # Verify (syntax check)
        try:
            ast.parse(new_content)
            return True
        except SyntaxError:
            await self.rollback(file_path)
            return False

    async def rollback(self, file_path: str = None):
        """Откат изменений."""
        if file_path:
            if file_path in self.backups:
                with open(file_path, "w") as f:
                    f.write(self.backups[file_path])
                del self.backups[file_path]
        else:
            for path, content in self.backups.items():
                with open(path, "w") as f:
                    f.write(content)
            self.backups.clear()
```

---

## Резюме

```
Multi-file Editing Pipeline:

Plan → Edit File 1 → Update References → Edit File 2 → ... → Verify

Ключевые паттерны:
  Diff-based: минимальные изменения, понятный review
  Cross-file: обновление всех ссылок
  Import management: автоматическое добавление
  Safe rollback: backup перед каждым изменением

Инструменты:
  DiffEditor: unified diff generation
  CrossFileRefactorer: rename + update references
  ImportManager: add/remove/organize imports
  SafeFileEditor: backup + rollback
```

---

## Практическое задание

1. Реализуй DiffEditor с генерацией унифицированного diff.

2. Настрой CrossFileRefactorer для rename функции.

3. Добавь ImportManager с автоматическим добавлением.

4. Реализуй SafeFileEditor с rollback.

---

## Проверь себя

1. Почему diff-based editing лучше, чем перезапись файла?

2. Как работает cross-file рефакторинг?

3. Как управлять импортами при генерации?

4. Зачем нужен safe rollback?

---

## Ссылки

- [[04-repo-understanding]] — понимание репозитория
- [[06-production-ci]] — следующий урок: CI/CD для кода
