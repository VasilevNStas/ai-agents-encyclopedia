---
created: 2026-05-28
tags: [readme, nav, meta]
---

# Learning / Обучение

Three courses in AI engineering: from the mental model of an LLM to production architectures.

> Course language is Russian. Technical terms, code, names and formats are in English.

---

## 📖 What is this?

An Obsidian vault containing three interconnected courses on AI engineering. Each course is a sequence of lessons with theory, examples, hands-on practice, and self-checks. Courses link to each other via `[[WikiLinks]]`: `[[ai-agents/...]]`, `[[opencode-skills/...]]`, `[[../../../ai-agents/...]]`.

Sequential order is recommended, but each course can be taken independently if you have the prerequisites.

### Getting started

1. Clone the repo: `git clone git@github.com:VasilevNStas/ai-agents-encyclopedia.git`
2. Open the folder in **Obsidian**: *Settings → Manage vaults → Open folder as vault*
3. Open `index.md` — this is the navigation entry point
4. Follow `[[WikiLinks]]` — they connect lessons, modules, and courses

That's it. No additional setup required.

---

## 📦 Courses overview

| # | Directory | Lessons | Lines | Status |
|---|-----------|:-------:|:-----:|:------:|
| 1 | [`ai-agents/`](./ai-agents/) | **48** | ~8000 | ✅ complete |
| 2 | [`opencode-skills/`](./opencode-skills/) | **27** | ~3500 | ✅ complete |
| 3 | [`prompt-engineering/`](./prompt-engineering/) | **15 modules** | ~5500 | ✅ complete |

Total: **~17,000+ lines, ~120+ files, 60+ cross-references**.

---

## 🧭 How they relate

Courses are structured from foundational to applied:

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  prompt-engineering ──────── foundational                           │
│  (how to communicate with LLMs)                                    │
│         │                                                          │
│         ▼                                                          │
│  ai-agents ──────────────────── core                               │
│  (how to build agents)                                             │
│         │                                                          │
│         ▼                                                          │
│  opencode-skills ────────────────── applied                        │
│  (how to package knowledge into Skills)                            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**prompt-engineering → ai-agents:** Prompt engineering modules (ReAct, MCP, RAG, guardrails) provide the foundation for ai-agents. When ai-agents dives deeper into tools and protocols, it references the corresponding prompt-engineering modules.

**ai-agents → opencode-skills:** Lessons 25-27 in ai-agents are a brief intro to Skills. The full 9-module course is in opencode-skills (27 lessons). Reference: `[[../../../opencode-skills/index|opencode-skills]]`.

---

## 🗺️ Full course map

### prompt-engineering · 15 modules (13 core + 2 advanced)

| Module | Topic | Lines |
|--------|-------|:-----:|
| M01 | Anatomy of LLMs — tokens, embeddings, attention, parameters | 223 |
| M02 | Anatomy of a Prompt — 8 elements, MVP→production, antipatterns | 340 |
| M03 | Chain-of-Thought — Zero-shot, Few-shot, Self-Consistency, ToT | 195 |
| M04 | ReAct & Agents — agent loop, function calling, error handling | 247 |
| M05 | RAG 2.0 — chunking, embedding, hybrid search, reranking | 241 |
| M06 | MCP — architecture, three primitives, transport, production | 253 |
| M07 | System Prompts — modular composition, Constitutional AI, guardrails | 211 |
| M07b | AI Safety & Alignment — reward hacking, deception, control | 230 |
| M08 | Evaluation & Security — metrics, LLM-as-Judge, injection | 242 |
| M08b | Fine-tuning Pipeline — LoRA, RLHF, DPO, approach selection | 220 |
| M09 | Architectural Patterns — multi-agent, reflection, event-driven | 229 |
| M10 | Role Prompting — Expert, Cascade, Multi-perspective, Adversarial | 231 |
| M11 | Text Processing — summarization, extraction, comparison, translation | 241 |
| M12 | Creative Prompting — brainstorming, storytelling, content plans | 209 |
| M13 | Analytics — SWOT, PEST, 5 Whys, Decision Matrix | 288 |
| M15 | Evals & Benchmarks — MMLU, SWE-bench, Arena, production eval | 250 |

Quiz: **78 questions** · Practice tasks: **15** · Example prompts: **6** · Reference solutions: **yes**

### ai-agents · 48 lessons, 13 modules

| Module | Description | Lessons |
|--------|-------------|:-------:|
| M01 — Fundamentals | LLMs, agents, ReAct | 3 |
| M02 — Agent Patterns | Plan-and-Solve, Reflexion, Tool Use | 3 |
| M03 — Memory & RAG | three memory layers, RAG 2.0, LLM Wiki, GRACE, Vector DB | 5 |
| M04 — Multi-Agent | Supervisor/Peer/Pipeline, protocols, antipatterns, A2A | 4 |
| M05 — Production | guardrails, observability, LDD, resilience, testing | 5 |
| M06 — Prompt Engineering | system prompt, CoT, structured output, caching | 4 |
| M07 — Skills (intro) | OpenCode Skills + MCP | 3 |
| M08 — Decision Architecture | fine-tuning vs RAG, model selection, cost, comparison, AI Gateway | 5 |
| M09 — Advanced RAG | agentic RAG, long-running, multi-modal, streaming | 4 |
| M10 — Data & Communication | data eng, protocols, HITL | 3 |
| M11 — Security & Safety | injection, privacy, secure architecture | 3 |
| M12 — Quality & Evolution | evals, A/B testing, continuous improvement | 3 |
| M13 — Ecosystem & Operations | frameworks, lifecycle, production ops | 3 |

Lesson format: `Key idea → Theory + code → Quiz → Summary → Links`

### opencode-skills · 27 lessons, 9 modules

| Module | Topics | Lessons |
|--------|--------|:-------:|
| M01 — Fundamentals | What is a Skill, vs prompt, vs AGENTS.md, ecosystem comparison | 3 |
| M02 — Anatomy | SKILL.md: YAML frontmatter, spec, validation, workshop | 3 |
| M03 — Mechanics | Skill Tool, 1% rule, lifecycle | 3 |
| M04 — Superpowers Ecosystem | Packages, distribution, npm, package workshop | 3 |
| M05 — Writing Skills | 6 steps, best practices, tool mapping | 3 |
| M06 — Advanced | Composition, chains, pitfalls | 3 |
| M07 — Debugging | Loading, instruction ignore, tools | 3 |
| M08 — Testing & Security | Testing, security, sandboxing, property-based testing | 4 |
| M09 — Performance | Context window, token cost, caching | 3 |

---

## 🚀 Usage scenarios

### Scenario A: Full immersion (recommended)

```
Step 1: prompt-engineering → M01 (Anatomy of LLMs)
        Goal: understand how the thing works under the hood.

Step 2: prompt-engineering → M02 (Anatomy of a Prompt)
        Goal: learn to write prompts deliberately.

Step 3: prompt-engineering → M03–M09
        Goal: master CoT, ReAct, RAG, MCP, system prompts, security.

Step 4: ai-agents → M01–M13
        Goal: from theory to production agents.

Step 5: opencode-skills → M01–M09
        Goal: package knowledge into reusable Skills.

Step 6: prompt-engineering → M10–M13
        Goal: applied scenarios (analytics, creative, text).
```

### Scenario B: Agents only

```
1. ai-agents M01–M02 (fundamentals)
2. ai-agents M03     (memory & RAG)
3. ai-agents M04–M06 (multi-agent, production, prompt eng)
4. ai-agents M08–M13 (model selection, security, quality, ecosystem)
```

### Scenario C: Skills only

```
opencode-skills M01 → M02 → M03 → ... → M09
Self-contained, no prerequisites from other courses.
```

### Scenario D: Production fast-track

```
1. ai-agents M05     — guardrails + observability + resilience + testing
2. ai-agents M11     — security (injection, privacy, audit)
3. ai-agents M12     — evaluation + A/B testing + continuous improvement
4. ai-agents M13     — frameworks + lifecycle + ops
5. prompt-engineering M08 — LLM-as-Judge, production checklist
```

---

## 🏗️ Directory structure

```
Обучение/
├── README.en.md                    ← this file
├── README.ru.md                    ← Russian version
├── index.md                        ← course navigation
│
├── ai-agents/                      ← agents course
│   ├── index.md                    ←   table of contents (48 lessons)
│   ├── AGENTS.md                   ←   assistant instructions
│   ├── log.md                      ←   change log
│   ├── 01-fundamentals/            ←   M01 lessons
│   ├── 02-agent-patterns/          ←   M02 lessons
│   ├── ...                         ←   M03–M12
│   ├── 13-ecosystem-operations/    ←   M13 (3 lessons)
│   ├── skills/                     ←   5 custom skill files
│   ├── wiki/                       ←   discussions (RAG, LDD, GRACE)
│   └── assets/                     ←   scripts, templates, exam
│
├── opencode-skills/                ← Skills course
│   ├── index.md
│   ├── AGENTS.md
│   ├── log.md
│   ├── 01-fundamentals/ ... 09-performance/  ← 9 modules
│   ├── meta/                       ←   roadmap, glossary, reference, course-index
│   ├── examples/                   ←   marp-slide (full skill example)
│   ├── skills/                     ←   study-helper
│   └── methodology.skill.md
│
├── prompt-engineering/             ← prompting course
│   ├── index.md
│   ├── AGENTS.md
│   ├── log.md
│   ├── 01-anatomy-of-llm/ ... 13-analytics-research/  ← 13 modules
│   ├── wiki/                       ←   2 extra topics
│   ├── prompts/                    ←   6 example prompts + reference solutions
│
├── примеры-проектов/               ← real-world projects
│   ├── загородный_дом_область/     ←   house 150m² with AI assistant
│   ├── multi-agent-code-review/    ←   5 specialized code review agents
│   └── research-rag-agent/         ←   multi-source deep research agent
│
├── opencode-setup.md               ← opencode configuration
└── environment-analysis.md         ← environment breakdown
```

---

## ✅ «AI Agent Architect» criteria checklist

| # | Skill | Where |
|---|-------|:-----:|
| 1 | Explain next-token prediction and attention | pe M01 |
| 2 | Design ReAct / Plan-and-Solve / Reflexion loop | aa M01–M02 |
| 3 | Organize three-layer memory + RAG | aa M03, pe M05 |
| 4 | Design a multi-agent system + A2A | aa M04, pe M09 |
| 5 | Choose fine-tuning vs RAG vs prompting, understand LoRA/RLHF | aa M08, pe M08b |
| 6 | Optimize cost (model routing, AI Gateway, caching) | aa M08 |
| 7 | Write a prompt (Role — Context — Task — Format) | pe M02, aa M06 |
| 8 | Protect against injection, reward hacking, spec gaming | aa M11, pe M07, pe M07b |
| 9 | Set up observability, evals, benchmarks | aa M05, aa M12, pe M15 |
| 10 | Use Skills (write, debug, property-based tests) | os M01–M09, aa M07-skl |
| 11 | Work with MCP and A2A protocols | pe M06, aa M07, aa M04 |
| 12 | Human-in-the-Loop for critical decisions | aa M10 |
| 13 | Production deploy: canary, rollback, ops, streaming | aa M13, aa M09 |
| 14 | Analyze via SWOT / PEST / frameworks | pe M13 |
| 15 | Write creative and role-based prompts | pe M10, pe M12 |
| 16 | Understand AI Safety (Constitutional AI, circuit breakers) | pe M07b |
| 17 | Evaluate models via benchmarks and custom evals | pe M15 |

*pe = prompt-engineering, aa = ai-agents, os = opencode-skills*

---

## 🛠️ Technical details

### File format

- **Markdown** (Obsidian-flavored: `[[WikiLinks]]`, callouts, YAML frontmatter)
- **Encoding**: UTF-8
- **Line endings**: LF
- **No emoji in code** (except README files).

### Callout blocks

| Type | Purpose |
|------|---------|
| `> [!note]` | Note |
| `> [!tip]` | Assignment |
| `> [!warning]` | Important |
| `> [!abstract]` | Lesson goal |
| `> [!quote]` | Key idea |
| `> [!success]` | Summary |

### AGENTS.md

Each course contains `AGENTS.md` — instructions for an AI assistant (opencode, Claude Code, etc.):
- Assistant role (professor, mentor)
- Course structure
- Response format
- Teaching methodology

To activate — open the vault in opencode. AGENTS.md is applied automatically.

---

## 📊 Statistics

| Metric | Value |
|--------|:-----:|
| Total courses | 3 |
| Total lessons | 48 + 27 + 15 modules |
| Total files | ~120 |
| Lines of content | ~17,000+ |
| Cross-references | 60+ |
| Quiz questions | 78 |
| Practice tasks | 48 + 27 |
| Example prompts | 6 |
| Skill examples | 2 (marp-slide, code-review-agent) |
| Example projects | 3 |
| AGENTS.md files | 3 |

### Directory sizes

```
ai-agents/          ~300 KB,  ~70 files
opencode-skills/    ~180 KB,  ~50 files
prompt-engineering/ ~200 KB,  ~30 files
```

---

## 📝 Context (May 2026)

- **Models**: GPT-4.5, Claude Sonnet 4.6, Claude Haiku 4.6, DeepSeek R1/V3
- **Protocols**: MCP, A2A, Function Calling
- **Frameworks**: LangGraph, CrewAI, Microsoft Agent Framework, Pydantic AI, LlamaIndex
- **Vector DBs**: Chroma, Qdrant, Pinecone
- **Skills format**: agentskills.io specification v1.0

---

## 📄 License

Educational materials. Free use for self-education.

---

*Last updated: 2026-05-28*
