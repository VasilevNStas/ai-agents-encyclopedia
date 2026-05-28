---
created: 2026-05-28
tags: [course/coding-agents-deep, production, ci-cd, code-review, quality]
status: active
---

# Урок 23.6: CI/CD для Generated Code

> [!quote] Ключевая идея
> Код, сгенерированный агентом, должен проходить те же quality gates, что и человеческий. Но agent-generated code требует дополнительных проверок: security audit, hallucination check, consistency с codebase, отсутствие dead code.

---

## 1. Quality Gates for Generated Code

```python
class GeneratedCodeQualityGates:
    """Quality gates для agent-generated кода."""

    GATES = [
        "syntax_check",
        "type_check",
        "lint",
        "test_suite",
        "security_scan",
        "consistency_check",
        "coverage_check",
        "hallucination_check",
    ]

    async def check(self, code: str, context: dict) -> dict:
        results = {}
        for gate in self.GATES:
            results[gate] = await getattr(self, f"_check_{gate}")(code, context)

        passed = all(r["passed"] for r in results.values())
        return {"passed": passed, "gates": results}

    async def _check_consistency(self, code: str, context: dict) -> dict:
        """Проверяет, что код консистентен с codebase."""
        issues = []
        # Check function signatures exist
        for func in self._extract_calls(code):
            if not self._function_exists(func, context["repo_path"]):
                issues.append(f"Function {func} not found in codebase")
        return {"passed": len(issues) == 0, "issues": issues}

    async def _check_hallucination(self, code: str, context: dict) -> dict:
        """Проверяет, что код не ссылается на несуществующие API."""
        issues = []
        # Check imported modules exist
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._module_exists(alias.name):
                        issues.append(f"Module {alias.name} does not exist")
        return {"passed": len(issues) == 0, "issues": issues}

    def _extract_calls(self, code: str) -> list[str]:
        tree = ast.parse(code)
        return [
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and hasattr(node.func, 'id')
        ]
```

---

## 2. CI/CD Pipeline

```yaml
# .github/workflows/agent-code-review.yml
name: Agent Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  agent-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Syntax & Lint
        run: |
          ruff check --select=E,F,W .
          mypy src/

      - name: Test Suite
        run: pytest --cov=src --cov-fail-under=80

      - name: Agent Code Quality
        id: agent-quality
        run: |
          python ci/check_agent_code.py \
            --diff-to-main \
            --check-consistency \
            --check-hallucination

      - name: Security Scan
        run: |
          bandit -r src/ -ll
          safety check

      - name: Post Review Comments
        if: failure()
        uses: code-review/agent-commenter@v1
        with:
          result-file: agent-quality-report.json
```

---

## 3. Agent PR Review Pipeline

```python
class AgentPRReviewer:
    """Автоматическое ревью PR, созданного агентом."""

    async def review_pr(self, pr_number: int, repo: str) -> dict:
        """Полное ревью PR от агента."""

        # 1. Get diff
        diff = await self._get_diff(pr_number, repo)

        # 2. Review each file
        reviews = []
        for file_path, changes in diff.items():
            review = await self._review_file(file_path, changes)
            reviews.append(review)

        # 3. Cross-file analysis
        cross_issues = await self._cross_file_analysis(reviews, diff)

        # 4. Generate summary
        summary = self._generate_summary(reviews, cross_issues)

        # 5. Post comment
        await self._post_comment(pr_number, repo, summary)

        return {"reviews": reviews, "cross_issues": cross_issues, "summary": summary}

    async def _review_file(self, file_path: str, changes: dict) -> dict:
        prompt = f"""Review this code change:
File: {file_path}
Diff: {changes.get('diff', '')[:2000]}

Check:
1. Correctness: does the logic make sense?
2. Style: follows project conventions?
3. Safety: any security issues?
4. Performance: any obvious inefficiencies?
5. Edge cases: missing error handling?

Return issues as JSON list."""
        response = await self.llm.generate(prompt)
        return {"file": file_path, "issues": self._parse_issues(response)}

    async def _cross_file_analysis(self, reviews: list[dict], diff: dict) -> list[str]:
        """Анализ cross-file issues."""
        issues = []
        added_imports = self._collect_imports(reviews, diff)
        for imp in added_imports:
            if not self._used_import(imp, diff):
                issues.append(f"Unused import: {imp}")
        return issues
```

---

## 4. Coverage and Mutation Testing

```python
class AgentCodeCoverage:
    """Проверка покрытия для сгенерированного кода."""

    async def check_coverage(self, test_results: dict) -> dict:
        """Проверяет, что тесты покрывают ключевые пути."""

        coverage = {
            "line_coverage": test_results.get("line_rate", 0),
            "branch_coverage": test_results.get("branch_rate", 0),
            "function_coverage": test_results.get("function_rate", 0),
        }

        thresholds = {"min_line": 0.8, "min_branch": 0.7, "min_function": 0.9}

        issues = []
        for metric, value in coverage.items():
            threshold = thresholds.get(f"min_{metric.split('_')[0]}", 0.8)
            if value < threshold:
                issues.append(f"{metric}: {value:.0%} < {threshold:.0%}")

        return {
            "coverage": coverage,
            "passed": len(issues) == 0,
            "issues": issues,
            "suggestions": await self._suggest_tests(issues) if issues else [],
        }

    async def mutation_test(self, code: str) -> dict:
        """Mutation testing: проверяет, что тесты находят ошибки."""
        mutants = self._generate_mutants(code)
        killed = 0
        for mutant in mutants:
            test_passed = await self._run_tests(mutant)
            if not test_passed:
                killed += 1
        return {
            "mutants": len(mutants),
            "killed": killed,
            "mutation_score": killed / max(len(mutants), 1),
        }
```

---

## Резюме

```
CI/CD for Generated Code:

Quality Gates:
  ☐ Syntax check (обязательно)
  ☐ Type check
  ☐ Lint (ruff/mypy)
  ☐ Existing tests pass
  ☐ Consistency: нет ссылок на несуществующие API
  ☐ Hallucination: нет вымышленных библиотек
  ☐ Coverage: >80%
  ☐ Security: bandit + safety

PR Review Pipeline:
  Diff → Review each file → Cross-file issues → Summary → Post comment

Anti-patterns:
  ❌ Доверять сгенерированному коду без проверки
  ❌ Не проверять consistency
  ❌ Не запускать mutation tests
```

---

## Практическое задание

1. Реализуй GeneratedCodeQualityGates с 3 ключевыми проверками.

2. Настрой CI/CD pipeline для agent-generated PR.

3. Добавь AgentPRReviewer с cross-file анализом.

4. Реализуй mutation test для проверки тестов.

---

## Проверь себя

1. Какие quality gates нужны для сгенерированного кода?

2. Как работает consistency check?

3. Что такое hallucination check для кода?

4. Как mutation testing проверяет качество тестов?

---

## Ссылки

- [[05-multi-file-editing]] — multi-file editing
- [[../../../05-production/04-resilience]] — resilience patterns
- [[../../20-eval-tools-deep/05-production-eval]] — production eval
