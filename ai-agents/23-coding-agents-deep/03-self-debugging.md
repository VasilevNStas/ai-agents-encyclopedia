---
created: 2026-05-28
tags: [course/coding-agents-deep, self-debugging, self-healing, error-fix]
status: active
---

# Урок 23.3: Self-Debugging & Self-Healing

> [!quote] Ключевая идея
> Код никогда не работает с первой попытки. Разница между «агент написал код» и «агент сделал задачу» — в циклах отладки. Self-debugging превращает ошибки в обучающие сигналы, а не в тупики.

---

## 1. Debug Cycle

```python
class SelfDebugger:
    """Цикл самодиагностики и исправления кода."""

    def __init__(self, max_attempts: int = 5, models: dict = None):
        self.max_attempts = max_attempts
        self.debugger_llm = models.get("debugger") if models else None
        self.history = []

    async def debug(self, code: str, test_command: str, error: str = None) -> dict:
        """Цикл отладки: run → parse → fix → retry."""

        for attempt in range(self.max_attempts):
            if attempt > 0:
                # Fix based on error
                code = await self._fix_code(code, error)
                self.history.append({"attempt": attempt, "fix": error[:100]})

            # Run
            success, output = await self._run_code(code, test_command)

            if success:
                return {"code": code, "attempts": attempt + 1, "success": True}

            error = self._parse_error(output)
            log(f"Attempt {attempt + 1}: {error[:100]}")

        return {"code": code, "attempts": self.max_attempts, "success": False, "last_error": error}

    async def _fix_code(self, code: str, error: str) -> str:
        prompt = f"""The following code has an error:
```python
{code}
```
Error:
```
{error}
```
Fix the bug. Return ONLY the corrected code."""

        return await self.debugger_llm.generate(prompt)

    def _parse_error(self, output: str) -> str:
        """Извлекает сообщение об ошибке из вывода."""
        lines = output.split("\n")
        error_lines = [l for l in lines if "Error" in l or "Traceback" in l or "Exception" in l]
        return "\n".join(error_lines[-5:]) if error_lines else output[-200:]
```

---

## 2. Error Classification

```python
class ErrorClassifier:
    """Классификация ошибок для выбора стратегии исправления."""

    CATEGORIES = {
        "syntax": {
            "patterns": ["SyntaxError", "unexpected EOF", "invalid syntax"],
            "strategy": "fix_syntax",
        },
        "import": {
            "patterns": ["ImportError", "ModuleNotFoundError", "No module named"],
            "strategy": "add_import",
        },
        "type": {
            "patterns": ["TypeError", "not subscriptable", "argument of type"],
            "strategy": "fix_types",
        },
        "attribute": {
            "patterns": ["AttributeError", "has no attribute"],
            "strategy": "fix_attribute",
        },
        "value": {
            "patterns": ["ValueError", "index out of range", "KeyError"],
            "strategy": "fix_value",
        },
        "logical": {
            "patterns": ["AssertionError", "expected", "got"],
            "strategy": "fix_logic",
        },
    }

    def classify(self, error: str) -> str:
        for category, config in self.CATEGORIES.items():
            if any(p in error for p in config["patterns"]):
                return category
        return "unknown"

    async def apply_fix(self, code: str, error: str, category: str) -> str:
        strategies = {
            "syntax": self._fix_syntax,
            "import": self._add_import,
            "type": self._fix_types,
            "logical": self._fix_logic,
        }
        fixer = strategies.get(category, self._generic_fix)
        return await fixer(code, error)

    async def _fix_syntax(self, code: str, error: str) -> str:
        prompt = f"Fix syntax error:\n```\n{code[:500]}\n```\nError: {error}"
        return await self.llm.generate(prompt)
```

---

## 3. Test Generation for Validation

```python
class TestGenerator:
    """Генерация тестов для валидации исправлений."""

    async def generate_test(self, code: str, function_name: str) -> str:
        """Генерирует тест для функции."""

        prompt = f"""Generate a pytest test for this function:
```python
{code}
```
Function to test: {function_name}
Return ONLY the test code with pytest."""

        test = await self.llm.generate(prompt)

        # Verify test runs
        success, output = await self._run_test(test)
        if not success:
            test = await self._fix_test(test, output)

        return test

    async def regression_check(self, original_tests: list[str], new_code: str) -> list[str]:
        """Проверяет, что старые тесты проходят с новым кодом."""
        failures = []
        for test in original_tests:
            combined = f"{new_code}\n\n{test}"
            success, _ = await self._run_test(combined)
            if not success:
                failures.append(test)
        return failures
```

---

## 4. Self-Healing in Production

```python
class ProductionSelfHealer:
    """Self-healing для production кода."""

    def __init__(self):
        self.error_patterns = {}
        self.fix_history = []

    async def heal(self, error: str, context: dict) -> dict:
        """Healing с учётом истории."""

        # 1. Check if seen this error before
        error_hash = hashlib.md5(error.encode()).hexdigest()
        if error_hash in self.error_patterns:
            known_fix = self.error_patterns[error_hash]
            log(f"Known error, applying cached fix: {known_fix['fix_type']}")
            return {"fix": known_fix["code"], "from_cache": True}

        # 2. Classify
        category = ErrorClassifier().classify(error)

        # 3. Generate fix
        fix = await self._generate_fix(error, context, category)

        # 4. Cache fix
        self.error_patterns[error_hash] = {
            "fix_type": category,
            "code": fix,
            "count": 1,
        }

        return {"fix": fix, "from_cache": False}

    async def _generate_fix(self, error: str, context: dict, category: str) -> str:
        prompt = f"Production error:\n{error}\n\nContext:\n{json.dumps(context, indent=2)[:500]}\n\nGenerate fix:"
        return await self.llm.generate(prompt)
```

---

## Резюме

```
Self-Debugging Pipeline:

Run → Error → Classify → Fix → Verify → (retry)
 │      │        │         │       │
code  stderr   syntax    LLM     test
              import    gener-  suite
              type      ation
              logical

Strategy:
  Syntax → Исправить синтаксис (быстрая LLM)
  Import → Добавить import (RAG по зависимостям)
  Type → Исправить типы (медленная LLM)
  Logic → Переписать логику (с тестами)

Anti-patterns:
  ❌ Исправлять не понимая ошибку
  ❌ Бесконечные retry (нужен лимит)
  ❌ Не проверять что старые тесты проходят
```

---

## Практическое задание

1. Реализуй SelfDebugger с 5 попытками исправления.

2. Добавь ErrorClassifier с 6 категориями.

3. Настрой TestGenerator: тест → validate → fix test.

4. Реализуй ProductionSelfHealer с кэшем ошибок.

---

## Проверь себя

1. Как работает цикл self-debugging?

2. Какие 6 категорий ошибок существуют?

3. Зачем нужен TestGenerator?

4. Как self-healing работает в production?

---

## Ссылки

- [[02-code-generation]] — генерация кода
- [[04-repo-understanding]] — следующий урок: понимание репозитория
