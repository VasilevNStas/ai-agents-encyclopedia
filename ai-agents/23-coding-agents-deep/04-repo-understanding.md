---
created: 2026-05-28
tags: [course/coding-agents-deep, repo-understanding, ast, code-graph, navigation]
status: active
---

# Урок 23.4: Code Repository Understanding

> [!quote] Ключевая идея
> Репозиторий — не набор файлов, а граф: функции вызывают функции, классы наследуют классы, импорты связывают модули. Coding agent должен _понимать_ этот граф, чтобы генерировать код, который впишется в архитектуру.

---

## 1. Code Graph Construction

```python
class CodeGraph:
    """Граф зависимостей кодовой базы."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.nodes = {}     # {id: Node}
        self.edges = []     # [(source, target, type)]
        self._build()

    def _build(self):
        """Строит граф из AST всех файлов."""
        import ast

        for file_path in Path(self.repo_path).rglob("*.py"):
            with open(file_path) as f:
                try:
                    tree = ast.parse(f.read())
                    self._process_file(file_path, tree)
                except SyntaxError:
                    continue

    def _process_file(self, file_path: Path, tree: ast.AST):
        """Обрабатывает файл: извлекает функции, классы, импорты."""

        file_id = str(file_path.relative_to(self.repo_path))
        self.nodes[file_id] = {"type": "file", "path": file_id}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_id = f"{file_id}::{node.name}"
                self.nodes[func_id] = {
                    "type": "function",
                    "name": node.name,
                    "file": file_id,
                    "lineno": node.lineno,
                }
                self.edges.append((file_id, func_id, "contains"))

            elif isinstance(node, ast.ClassDef):
                class_id = f"{file_id}::{node.name}"
                self.nodes[class_id] = {
                    "type": "class",
                    "name": node.name,
                    "file": file_id,
                    "lineno": node.lineno,
                }
                self.edges.append((file_id, class_id, "contains"))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.edges.append((file_id, alias.name, "imports"))

            elif isinstance(node, ast.Call):
                if hasattr(node.func, 'id'):
                    self.edges.append((file_id, node.func.id, "calls"))

    def find_related(self, entity: str, max_depth: int = 2) -> list[str]:
        """Находит всё, что связано с entity (функцией/файлом)."""
        from collections import deque

        visited = set()
        queue = deque([(entity, 0)])
        related = []

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            related.append(current)

            for src, tgt, _ in self.edges:
                if src == current and tgt not in visited:
                    queue.append((tgt, depth + 1))
                if tgt == current and src not in visited:
                    queue.append((src, depth + 1))

        return related
```

---

## 2. AST-level Understanding

```python
class ASTAnalyzer:
    """Понимание кода через AST."""

    def get_function_context(self, code: str, function_name: str) -> dict:
        """Извлекает полный контекст функции."""
        import ast

        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return {
                    "name": node.name,
                    "params": self._get_params(node),
                    "returns": self._get_return_type(node),
                    "calls": self._get_calls(node),
                    "decorators": self._get_decorators(node),
                    "complexity": self._calculate_complexity(node),
                    "docstring": ast.get_docstring(node),
                }
        return {}

    def _get_calls(self, node: ast.FunctionDef) -> list[str]:
        """Какие функции вызывает эта функция."""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and hasattr(child.func, 'id'):
                calls.append(child.func.id)
        return calls

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Цикломатическая сложность."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
        return complexity

    def get_class_hierarchy(self, code: str) -> dict:
        """Иерархия наследования классов."""
        import ast
        tree = ast.parse(code)
        hierarchy = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [
                    self._get_base_name(base) for base in node.bases
                ]
                hierarchy[node.name] = {
                    "bases": bases,
                    "methods": [
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                    "decorators": self._get_decorators(node),
                }

        return hierarchy
```

---

## 3. Change Impact Analysis

```python
class ChangeImpactAnalyzer:
    """Анализ влияния изменений на код."""

    def analyze_impact(self, changed_file: str, changed_function: str) -> dict:
        """Определяет, какие ещё части кода затронуты."""

        graph = self.code_graph

        # Find all callers
        callers = []
        for src, tgt, etype in graph.edges:
            if tgt == f"{changed_file}::{changed_function}" and etype == "calls":
                callers.append(src)

        # Find all callees (functions called by changed function)
        callees = [
            tgt for src, tgt, etype in graph.edges
            if src == f"{changed_file}::{changed_function}" and etype == "calls"
        ]

        # Tests that cover this function
        tests = self._find_tests(changed_function)

        return {
            "direct_callers": callers,
            "direct_callees": callees,
            "affected_files": len(set(c.rsplit("::", 1)[0] for c in callers if "::" in c)),
            "affected_tests": tests,
            "risk_level": "high" if len(callers) > 5 else "medium" if callers else "low",
        }

    def _find_tests(self, function_name: str) -> list[str]:
        """Находит тесты, которые тестируют функцию."""
        test_files = Path(self.repo_path).rglob("test_*.py")
        covering_tests = []

        for test_file in test_files:
            with open(test_file) as f:
                content = f.read()
                if function_name in content:
                    covering_tests.append(str(test_file.relative_to(self.repo_path)))

        return covering_tests
```

---

## 4. Navigation Tools

```python
class CodeNavigation:
    """Инструменты навигации по кодовой базе для агента."""

    async def go_to_definition(self, symbol: str, file_path: str) -> dict:
        """Находит определение символа (функции/класса)."""
        import ast

        with open(file_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == symbol:
                lines = self._extract_lines(file_path, node.lineno, node.end_lineno)
                return {
                    "file": file_path,
                    "line": node.lineno,
                    "code": "\n".join(lines),
                }

        return {"error": f"Symbol {symbol} not found in {file_path}"}

    async def find_references(self, symbol: str, repo_path: str) -> list[dict]:
        """Находит все использования символа."""
        references = []
        for file_path in Path(repo_path).rglob("*.py"):
            with open(file_path) as f:
                for i, line in enumerate(f, 1):
                    if symbol in line and f"{file_path}::{symbol}" not in line:
                        references.append({
                            "file": str(file_path.relative_to(repo_path)),
                            "line": i,
                            "snippet": line.strip(),
                        })
        return references[:20]  # Limit
```

---

## Резюме

```
Code Understanding Stack:

AST Level:     синтаксис, типы, вызовы
Graph Level:   зависимости, иерархия, потоки
Semantic Level: назначение, поведение, контекст

Инструменты:
  Code Graph: граф вызовов и наследования
  AST Analyzer: извлечение сигнатур, сложности
  Impact Analysis: кто сломается от изменений
  Navigation: go-to-def, find references

Anti-patterns:
  ❌ Игнорировать AST, работать с текстом
  ❌ Не проверять impact изменений
  ❌ Не знать иерархию наследования
```

---

## Практическое задание

1. Построй CodeGraph для репозитория (AST → граф).

2. Реализуй ChangeImpactAnalyzer: кто вызывает функцию.

3. Добавь CodeNavigation: go-to-definition + find-references.

---

## Проверь себя

1. Как строится граф зависимостей кода?

2. Какая информация извлекается из AST для понимания кода?

3. Как работает change impact analysis?

4. Какие инструменты навигации нужны агенту?

---

## Ссылки

- [[03-self-debugging]] — self-debugging
- [[05-multi-file-editing]] — следующий урок: multi-file editing
