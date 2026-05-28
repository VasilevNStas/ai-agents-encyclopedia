---
created: 2026-05-28
tags: [course/coding-agents-deep, code-generation, architecture, context]
status: active
---

# Урок 23.2: Code Generation Architecture

> [!quote] Ключевая идея
> Генерация кода — это не «LLM пишет код». Это pipeline: intent → context → plan → generate → verify → fix. Каждый этап — свой промпт, своя модель, свои метрики.

---

## 1. Code Generation Pipeline

```python
class CodeGenPipeline:
    """Полный пайплайн генерации кода."""

    def __init__(self, models: dict):
        self.planner = models["planner"]       # Plan модель (медленная, точная)
        self.coder = models["coder"]            # Code модель (быстрая)
        self.verifier = models["verifier"]      # Проверка

    async def generate(self, intent: str, context: str) -> dict:
        # 1. Plan: разбиваем intent на шаги
        plan = await self._plan(intent, context)

        # 2. Code: генерация по шагам
        code = await self._code(plan, context)

        # 3. Verify: проверка
        issues = await self._verify(code, context)

        # 4. Fix: если есть проблемы
        if issues:
            code = await self._fix(code, issues)

        return {"code": code, "plan": plan, "fixes": issues}
```

---

## 2. Plan → Code Pattern

```python
class PlanThenCode:
    """Plan-then-Code: разделение анализа и генерации."""

    async def plan(self, intent: str, context: str) -> list[dict]:
        """Генерирует план реализации."""

        prompt = f"""Task: {intent}
Context:
{context[:2000]}

Create a step-by-step implementation plan:
1. List files to modify
2. For each file: what changes
3. Dependencies and order
4. Edge cases to handle

Return as JSON list of steps."""

        response = await self.planner.generate(prompt)
        plan = json.loads(self._extract_json(response))

        # Validate plan
        if not self._validate_plan(plan):
            plan = await self._refine_plan(plan, intent)
        return plan

    async def execute_plan(self, plan: list[dict], context: str) -> str:
        """Выполняет план: генерирует код для каждого шага."""
        generated_code = []

        for step in plan:
            code = await self.coder.generate(
                f"Implement step: {step['description']}\n"
                f"File: {step.get('file', 'unknown')}\n"
                f"Context:\n{context[:1000]}"
            )
            generated_code.append({
                "file": step.get("file", "unknown"),
                "code": code,
                "step": step["description"],
            })

        return self._combine_code(generated_code)
```

---

## 3. Retrieval-Augmented Generation for Code

```python
class CodeRAG:
    """RAG для генерации кода: поиск похожих паттернов."""

    def __init__(self, codebase_path: str):
        self.index = self._build_code_index(codebase_path)
        self.encoder = SentenceTransformer("codebert-base")

    async def retrieve_patterns(self, query: str, k: int = 3) -> list[str]:
        """Ищет похожие реализации в codebase."""

        query_emb = self.encoder.encode(query)
        results = self.index.search(query_emb, k=k)

        patterns = []
        for result in results:
            with open(result["path"]) as f:
                code = f.read()
            patterns.append(f"# Pattern from {result['path']}\n```\n{code[:500]}\n```")

        return patterns

    async def generate_with_patterns(self, query: str) -> str:
        """Генерация кода с поиском паттернов."""

        patterns = await self.retrieve_patterns(query)
        context = "\n\n".join(patterns)

        prompt = f"Similar patterns from codebase:\n{context}\n\n"
        prompt += f"Generate code for: {query}\n"
        prompt += "Follow the patterns above. Return ONLY the code."

        return await self.coder.generate(prompt)

    def _build_code_index(self, path: str) -> "FaissIndex":
        """Строит векторный индекс кода."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("codebert-base")

        files = list(Path(path).rglob("*.py"))
        texts = []
        paths = []
        for f in files:
            with open(f) as fh:
                texts.append(fh.read())
                paths.append(str(f))

        embeddings = model.encode(texts)
        index = FaissIndex(dim=embeddings.shape[1])
        index.add(embeddings, paths)
        return index
```

---

## 4. Incremental Generation

```python
class IncrementalCodeGen:
    """Инкрементальная генерация: добавляем код к существующему."""

    async def generate_function(self, file_content: str, function_spec: dict) -> str:
        """Генерирует новую функцию в существующий файл."""

        # 1. Анализируем существующие импорты и сигнатуры
        imports, existing_funcs = self._parse_file(file_content)

        # 2. Определяем место вставки
        insert_point = self._find_insert_point(file_content, function_spec)

        # 3. Генерируем только новую функцию
        function_code = await self.coder.generate(
            f"Generate ONLY the function body for:\n"
            f"Name: {function_spec['name']}\n"
            f"Params: {function_spec.get('params', [])}\n"
            f"Returns: {function_spec.get('returns', 'None')}\n"
            f"Existing imports: {imports}\n"
            f"Existing functions: {list(existing_funcs.keys())}\n"
            f"IMPORTANT: Return ONLY the function code."
        )

        # 4. Добавляем импорт если нужно
        needed_imports = self._check_needed_imports(function_code, imports)
        if needed_imports:
            file_content = self._add_imports(file_content, needed_imports)

        return file_content + "\n\n" + function_code
```

---

## 5. Code Quality Verification

```python
class CodeVerifier:
    """Верификация сгенерированного кода."""

    async def verify(self, code: str, language: str = "python") -> list[str]:
        """Проверка кода: синтаксис, типы, тесты."""
        issues = []

        # 1. Syntax check
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")

        # 2. Lint
        lint_issues = await self._lint(code)
        issues.extend(lint_issues)

        # 3. Type check (optional)
        if language == "python":
            type_issues = await self._type_check(code)
            issues.extend(type_issues)

        # 4. Security check
        security_issues = await self._security_check(code)
        issues.extend(security_issues)

        return issues

    async def _lint(self, code: str) -> list[str]:
        """Запуск linter."""
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w") as f:
            f.write(code)
            f.flush()
            result = subprocess.run(["ruff", f.name], capture_output=True, text=True)
            return [line for line in result.stdout.split("\n") if line]

    async def _security_check(self, code: str) -> list[str]:
        """Проверка безопасности."""
        issues = []
        dangerous = ["eval(", "exec(", "__import__", "pickle.loads"]
        for func in dangerous:
            if func in code:
                issues.append(f"Security: {func} used in code")
        return issues
```

---

## Резюме

```
Code Generation Pipeline:

Intent → Plan → Retrieve → Generate → Verify → Fix
  │         │       │          │         │       │
  prompt   steps  patterns    code      lint   refactor

Ключевые паттерны:
  Plan-then-Code: разделение анализа и генерации
  Code RAG: поиск похожих реализаций
  Incremental: генерация с учётом existing кода
  Verify-then-fix: автоисправление ошибок

Anti-patterns:
  ❌ Генерация всего файла (а не diff)
  ❌ Нет верификации синтаксиса
  ❌ Нет контекста проекта
```

---

## Практическое задание

1. Реализуй PlanThenCode: intent → план → генерация.

2. Добавь CodeRAG с поиском похожих реализаций.

3. Настрой CodeVerifier: syntax + lint + security.

---

## Проверь себя

1. Какие 5 этапов в пайплайне генерации кода?

2. Чем Plan-then-Code лучше прямой генерации?

3. Как работает RAG для кода?

4. Почему incremental generation важна?

---

## Ссылки

- [[01-landscape]] — coding agents landscape
- [[03-self-debugging]] — следующий урок: self-debugging
