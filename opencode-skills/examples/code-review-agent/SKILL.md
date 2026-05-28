---
name: code-review-agent
description: Use when the user asks to review code, find bugs,
  check code quality, or perform a security audit on source code.
  Covers Python, TypeScript, JavaScript, Go, Rust, and Ruby.
---

# Code Review Agent

Perform systematic code review: security, correctness, performance, style, and maintainability.

## When to Use

Use this skill when:
- Reviewing a PR or commit diff
- Checking code for bugs or security issues
- Asked to "review this code" or "find problems in this code"
- Auditing code quality before deployment

DO NOT use for:
- Writing new code from scratch (use a writing skill instead)
- Explaining what code does (just answer directly)
- Refactoring without review (review first, refactor as a separate step)

## Process

### Step 1: Read the code

Use `read` or `grep` tool to understand the full context. Read at minimum:
- The file(s) under review
- Related imports and dependencies
- Tests for the code (if they exist)

### Step 2: Run security scan

Check for:
- Hardcoded secrets (API keys, passwords, tokens)
- SQL injection (string concatenation in queries)
- Command injection (shell=True, os.system, eval)
- Path traversal (user input in file paths)
- Unsafe deserialization (pickle, yaml.load)
- Known vulnerable dependency patterns

Security issues are **blocking** — flag them immediately.

### Step 3: Check correctness

Verify:
- Edge cases handled? (empty input, None, boundary values)
- Error handling? (try/except, error returns, graceful degradation)
- Type consistency? (mypy, TypeScript strict mode)
- Logic errors? (off-by-one, wrong operator, inverted condition)
- Race conditions? (shared state without locks)

### Step 4: Evaluate performance

Look for:
- Unnecessary allocations in hot paths
- N+1 queries in database code
- Missing caching for expensive operations
- O(n^2) algorithms where O(n log n) is possible
- Synchronous blocking I/O in async code

### Step 5: Assess maintainability

Check:
- Naming clarity (does the name reflect intent?)
- Function size (one function = one responsibility)
- Comment quality (why, not what)
- Test coverage (are there tests? do they test the right things?)
- Dead code (unused imports, unreachable branches)

### Step 6: Write review

Format:

```markdown
## Code Review: {file}

### Critical (must fix)
- {issue} — {file:line}

### Warning (should fix)
- {issue} — {file:line}

### Suggestion (consider)
- {suggestion}

### Positive
- {what was done well}
```

Each issue includes:
1. Severity label (Critical / Warning / Suggestion)
2. File and line number
3. Explanation of the problem
4. Suggested fix (concrete code)
5. Why it matters (impact if not fixed)

## Common Mistakes

- **Reviewing style before security** — always security first
- **False positives on naming** — focus on bugs, not preferences
- **Missing context** — review without reading imports = incomplete review
- **Too many suggestions** — 3-5 real issues > 20 nitpicks
- **No positive feedback** — good code deserves acknowledgment
