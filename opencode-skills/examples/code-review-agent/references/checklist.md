# Code Review Checklist

## Security (Critical)
- [ ] Hardcoded secrets (API keys, passwords, tokens, private keys)
- [ ] SQL injection (string interpolation in queries)
- [ ] Command injection (shell=True, os.popen, subprocess with shell)
- [ ] Path traversal (user input in open(), File IO without validation)
- [ ] Unsafe deserialization (pickle, yaml.load without Loader)
- [ ] XSS (untrusted input rendered without escaping)
- [ ] CSRF missing tokens
- [ ] Insecure direct object references (IDOR)
- [ ] Authentication bypass
- [ ] Known vulnerable dependency

## Correctness (High)
- [ ] Edge cases: empty input, None/null, zero, negative values
- [ ] Error handling: exceptions caught, errors returned, not swallowed
- [ ] Type safety: mypy strict, TypeScript strict, runtime assertions
- [ ] Off-by-one errors, wrong comparison operators
- [ ] Race conditions: shared mutable state, async without locks
- [ ] Pagination: offset/limit, cursors, total count
- [ ] Transaction handling: commit/rollback on error
- [ ] Encoding: unicode, utf-8, binary safety

## Performance (Medium)
- [ ] N+1 queries in ORM code
- [ ] Unnecessary allocations in loops
- [ ] Missing caching (Redis, memoization, CDN)
- [ ] Synchronous blocking I/O in async code
- [ ] Large objects in memory unnecessarily
- [ ] Inefficient algorithms (O(n^2) where O(n log n) possible)
- [ ] Missing indexes on database queries

## Maintainability (Medium)
- [ ] Function does one thing (single responsibility)
- [ ] Naming reflects intent (not implementation)
- [ ] Comments explain WHY not WHAT
- [ ] No dead code (unused imports, dead branches)
- [ ] Tests exist and test the right things
- [ ] Dependencies are explicit (requirements.txt, package.json)
- [ ] Configuration is external, not hardcoded

## Style (Low)
- [ ] Consistent formatting (follows linter config)
- [ ] Meaningful variable names (no single-letter except loops)
- [ ] No commented-out code
- [ ] No debug artifacts (console.log, print, breakpoints)
- [ ] Import order (stdlib, third-party, local)
