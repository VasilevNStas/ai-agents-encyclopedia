---
created: 2026-05-28
tags: [course/coding-agents-deep, swe-agent, code-generation, landscape]
status: active
---

# Урок 23.1: Coding Agents Landscape

> [!quote] Ключевая идея
> Coding agents 2026 — не «пишут код по промпту». Это целый класс систем: SWE-agent решает issue-ы, Codex пишет функции, Cursor редактирует файлы, Devin/Pythagora автономно ведут проекты. Каждый — свой архитектурный паттерн.

---

## 1. Классификация Coding Agents

```python
class CodingAgentTaxonomy:
    """Таксономия coding agents."""

    CATEGORIES = {
        "code_gen": {
            "description": "Генерация кода по описанию",
            "examples": ["GitHub Copilot", "Codex", "CodeGemma"],
            "architecture": "Single LLM call + context",
            "complexity": "★☆☆",
        },
        "code_edit": {
            "description": "Редактирование существующего кода",
            "examples": ["Cursor Tab", "Copilot Edit", "Amazon Q"],
            "architecture": "Diff generation + lint",
            "complexity": "★★☆",
        },
        "issue_resolver": {
            "description": "Решение GitHub issues",
            "examples": ["SWE-agent", "Devin", "OpenHands"],
            "architecture": "Plan → Code → Test → Fix loop",
            "complexity": "★★★",
        },
        "repo_agent": {
            "description": "Автономная работа с репозиторием",
            "examples": ["Devin", "Pythagora", "Cody"],
            "architecture": "Multi-tool: bash, editor, search, git",
            "complexity": "★★★",
        },
        "code_review": {
            "description": "Автоматическое ревью кода",
            "examples": ["CodeRabbit", "Code Review agent (ours)"],
            "architecture": "Diff analysis + rules",
            "complexity": "★★☆",
        },
    }

    @staticmethod
    def which_agent(task: str) -> str:
        if task in ["new_feature", "generate_component"]:
            return "code_gen"
        elif task in ["fix_bug", "refactor"]:
            return "code_edit"
        elif task in ["fix_issue", "resolve_pr_comment"]:
            return "issue_resolver"
        elif task == "full_project":
            return "repo_agent"
        return "code_gen"
```

---

## 2. Сравнение подходов

| Характеристика | Prompt-based | Tool-using | SWE-agent | Devin-like |
|---------------|-------------|------------|-----------|------------|
| Генерация | Один промпт | Multi-turn | Plan→Code→Test | Full project |
| Контекст | Текущий файл | +LSP/semantic | +Repo + issues | +Requirements |
| Инструменты | Нет | LSP, linter | bash, vim, git | Docker, browser |
| Итерации | Нет | 2-3 попытки | До 50 | Неограничено |
| Accuracy | 60-70% | 70-80% | 80-90% (SWE-bench) | 70-85% |
| Cost/call | $0.01 | $0.05 | $0.10-1.00 | $0.50-5.00 |

---

## 3. SWE-agent Architecture (Reference)

```python
class SWEAgent:
    """SWE-agent: issue → patch."""

    def __init__(self, model, repo_path: str):
        self.model = model
        self.repo = RepoContext(repo_path)
        self.tools = {
            "search_file": self.search_file,
            "edit_file": self.edit_file,
            "view_file": self.view_file,
            "run_tests": self.run_tests,
            "git_diff": self.git_diff,
        }

    async def solve_issue(self, issue_text: str) -> str:
        """Решает issue: генерирует patch."""

        context = await self.repo.get_relevant_context(issue_text)
        max_iterations = 30

        for i in range(max_iterations):
            prompt = self._build_prompt(issue_text, context, i)
            response = await self.model.generate(prompt)

            action = self._parse_action(response)
            if action["type"] == "submit":
                patch = await self.git_diff()
                tests_passed = await self._run_all_tests()
                return {"patch": patch, "tests_passed": tests_passed}

            elif action["type"] == "tool":
                result = await self.tools[action["tool"]](**action["args"])
                context += f"\n[{action['tool']} result]: {result[:500]}"

        return {"error": "Max iterations reached"}

    def _parse_action(self, response: str) -> dict:
        """Парсит действие из ответа модели."""
        if "<submit>" in response:
            return {"type": "submit"}
        match = re.search(r'<tool=(\w+)>(.*?)</tool>', response, re.DOTALL)
        if match:
            return {"type": "tool", "tool": match.group(1), "args": json.loads(match.group(2))}
        return {"type": "tool", "tool": "search_file", "args": {"query": response}}
```

---

## 4. Code Context Building

```python
class RepoContext:
    """Сбор контекста из репозитория."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.file_index = self._build_index()

    async def get_relevant_context(self, query: str, max_tokens: int = 8000) -> str:
        """Собирает релевантный контекст под запрос."""

        # 1. Semantic search по коду
        relevant_files = self._semantic_search(query, top_k=5)

        # 2. Сбор сигнатур
        context_parts = []
        tokens_used = 0

        for file_path in relevant_files:
            skeleton = self._extract_skeleton(file_path)
            tokens = len(skeleton) // 4

            if tokens_used + tokens > max_tokens:
                break

            context_parts.append(f"### {file_path}\n{skeleton}")
            tokens_used += tokens

        # 3. Relevant snippets (full code для критичных мест)
        snippets = self._extract_relevant_snippets(query)
        for snippet in snippets:
            if tokens_used + len(snippet) // 4 > max_tokens:
                break
            context_parts.append(snippet)
            tokens_used += len(snippet) // 4

        return "\n\n".join(context_parts)

    def _build_index(self) -> dict:
        """Индекс всех файлов репозитория."""
        import ast
        index = {}
        for path in Path(self.repo_path).rglob("*.py"):
            with open(path) as f:
                try:
                    tree = ast.parse(f.read())
                    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    index[str(path)] = {"functions": functions, "classes": classes}
                except SyntaxError:
                    pass
        return index
```

---

## Резюме

```
Coding Agents 2026 — спектр:

Простой редактор (Copilot) ← → Полноценный инженер (Devin)

Аспекты сравнения:
  — Контекст: строка → файл → репозиторий → проект
  — Инструменты: none → LSP → bash → Docker
  — Итерации: 0 → 3 → 30 → ∞
  - Cost: $0.01 → $5.00 за задачу

Лидеры:
  SWE-agent: лучший на SWE-bench (open-source reference)
  Devin: самый автономный (но closed-source)
  Cursor: лучший UX для ежедневной разработки
```

---

## Практическое задание

1. Классифицируй 5 coding agents по таксономии выше.

2. Реализуй RepoContext с semantic поиском.

3. Напиши SWE-agent: issue → patch pipeline.

---

## Проверь себя

1. Какие 5 категорий coding agents существуют?

2. Чем SWE-agent отличается от простого codegen?

3. Как собирается контекст из репозитория?

---

## Ссылки

- [[02-code-generation]] — следующий урок: code generation architecture
- [[../../../04-multi-agent/01-orchestration]] — multi-agent orchestration
- [[../../../08-decision-architecture/02-model-selection]] — выбор модели для кода
