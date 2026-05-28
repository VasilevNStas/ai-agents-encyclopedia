---
name: wiki-maintainer
description: Универсальный ассистент для ведения LLM Wiki по любой теме
author: ai-agents
version: 2.0.0
tags: [skill, wiki, maintenance, second-brain, knowledge-management]
depends_on: []
config:
  domain: auto                    # auto | tech | business | science | life
  compression: smart
  auto_connect: true              # автоматически связывать страницы
  progressive_summarization: true # углублять страницы при повторных визитах
---

# Skill: Wiki Maintainer v2.0 — «Второй мозг»

> [!quote] Назначение
> Веди структурированную базу знаний по любой теме — от программирования до бизнеса и наук. Каждый диалог с ассистентом компилируется в wiki-страницу, которая со временем богатеет и связывается с другими страницами.

---

## 1. Поддерживаемые домены

Skill автоматически определяет домен по контексту диалога:

| Домен | Папка | Примеры тем |
|-------|-------|-------------|
| `tech` | `wiki/tech/` | Архитектура агентов, RAG, Python |
| `business` | `wiki/business/` | Стратегия, финансы, маркетинг |
| `science` | `wiki/science/` | Физика, математика, биология |
| `life` | `wiki/life/` | Цели, привычки, рефлексия |

Структура на диске:

```
wiki/
├── tech/
│   ├── agent-architecture.md
│   └── rag-patterns.md
├── business/
│   ├── business-model.md
│   └── negotiation.md
├── science/
│   ├── quantum-mechanics.md
│   └── calculus.md
├── life/
│   ├── goals-2026.md
│   └── habits.md
├── index.md        ← навигация по всем доменам
└── log.md          ← единая хронология
```

---

## 2. Типы страниц

Каждая страница имеет тип, который определяет её шаблон:

### 📄 Concept (Концепция)
Базовое понятие, идея, теория.

```markdown
---
created: 2026-05-09
type: concept
domain: tech
tags: [concept, architecture]
status: seedling   # seedling → growing → evergreen
---

# ReAct Pattern

## Определение
Паттерн, в котором LLM чередует рассуждение и действие.

## Ключевые тезисы
- ...

## Связи
- [[Chain-of-Thought]] — основа рассуждения
```

**Статусы (progressive summarization):**
- `seedling` — только что создана, сырой синтез
- `growing` — дополнена, есть примеры и связи
- `evergreen` — отполирована, можно использовать как reference

### 🔗 Entity (Сущность)
Конкретный объект: человек, компания, продукт, книга.

```markdown
---
created: 2026-05-09
type: entity
domain: business
tags: [entity, company, ai]
---

# DeepSeek

## Описание
Китайская AI-компания, создатель DeepSeek-R1 и DeepSeek-V2.

## Ключевые факты
- Основана: 2023
- Продукты: R1, V2
- ...
```

### 💡 Decision (Решение)
Зафиксированное решение с контекстом и обоснованием.

```markdown
---
created: 2026-05-09
type: decision
domain: tech
tags: [decision, architecture]
---

# Выбор: DeepSeek vs Claude для агента

## Контекст
Нужно было выбрать модель для ядра агента.

## Рассмотренные варианты
1. DeepSeek-R1 — дешевле, хорош для рассуждений
2. Claude 3.5 — лучше в следовании инструкциям, но дороже

## Решение
DeepSeek-R1 — для экономии и качества reasoning.

## Последствия
...

## Связи
- [[agent-architecture]]
```

### 📝 Source (Источник)
Ссылка на внешний материал.

### 🔭 Reflection (Рефлексия)
Личная заметка, вывод, инсайт.

---

## 3. Процесс Ingest

После каждого диалога:

### Шаг 1: Определи домен и тип
```python
# Автоматически по контексту диалога
domain = detect_domain(dialog_text)    # tech | business | science | life
page_type = detect_page_type(dialog_text)  # concept | entity | decision | ...
```

### Шаг 2: Создай или обнови страницу
```python
# Если страница уже существует — обнови (growing)
# Если новая — создай (seedling)
if page_exists(topic):
    update_page(topic, new_insights)
    advance_status(topic)  # seedling → growing → evergreen
else:
    create_page(topic, dialog_summary, domain, page_type)
```

### Шаг 3: Свяжи с существующими страницами
```python
# Auto-connect: найди пересечения с другими страницами
related_pages = find_related(domain, tags, content)
for page in related_pages:
    add_wikilink(new_page, page)
    add_wikilink(page, new_page)  # обратная связь
```

### Шаг 4: Обнови index.md и log.md
```markdown
# В index.md
## Business
- [[business/negotiation.md]] — техники переговоров
- [[tech/rag-patterns.md]] ★ — кросс-доменная связь

# В log.md
## [2026-05-09] ingest | Техники переговоров
  Domain: business
  Type: concept
  Status: seedling
  Links: [[tech/prompt-engineering]]
```

---

## 4. Cross-domain linking (кросс-доменные связи)

Самая мощная фича — **связи между разными доменами**.

```markdown
# wiki/business/negotiation.md
## Связи
- [[tech/prompt-engineering]] — промпты как переговоры с LLM ★
- [[life/habits]] — подготовка к переговорам как привычка

# wiki/tech/prompt-engineering.md
## Связи
- [[business/negotiation]] — формулировка запроса = аргументация ★
```

**Звёздочка ★ — неожиданная связь.** Это сигнал: «посмотри, тут есть пересечение, о котором ты мог не подумать».

### Алгоритм auto-connect:
```python
def auto_connect(new_page, existing_pages):
    for page in existing_pages:
        # 1. Прямые совпадения (одинаковые термины)
        if shared_terms(new_page, page) > 3:
            link_pages(new_page, page)

        # 2. Смысловые пересечения (похожие теги)
        if shared_tags(new_page, page):
            link_pages(new_page, page)

        # 3. Неожиданные связи (разные домены, но одно ядро)
        if page.domain != new_page.domain:
            if shared_core_concept(new_page, page):
                link_pages(new_page, page, is_surprising=True)  # ★
```

---

## 5. Progressive summarization

При каждом повторном визите к странице — **углубляй её**:

```
Pass 1 (ingest):      Создать страницу (seedling) — сырой синтез
Pass 2 (revisit):     Выделить bold — ключевые фразы
Pass 3 (deepen):      Выделить highlight — самые важные мысли
Pass 4 (synthesize):  Написать executive summary — 2-3 предложения
Pass 5 (connect):     Найти кросс-доменные связи ★
```

```markdown
# wiki/tech/react-pattern.md (after pass 4)

## Executive Summary
ReAct — это цикл Thought → Action → Observation.
Критичен для агентов, но без плана — зацикливается.

## Ключевые тезисы
**Thought** — рассуждение вслух. **Action** — вызов инструмента.
**Observation** — результат. ==Связка Thought→Action→Observation==
заменяет "магическое угадывание" ответа пошаговым reasoning.

## Связи
- [[tech/plan-and-solve]] — решение проблемы зацикливания
- [[life/problem-solving]] — ★ тот же цикл в решении жизненных проблем
```

---

## 6. Периодический Lint

Раз в месяц (или по запросу «проверь вики»):

- [ ] **Seedling → Growing:** какие страницы пора углубить?
- [ ] **Evergreen review:** какие страницы подтверждены опытом?
- [ ] **Orphans:** страницы без обратных ссылок
- [ ] **Stale:** страницы старше 3 месяцев без обновлений
- [ ] **Cross-domain:** какие темы пересекаются между доменами?
- [ ] **Index check:** все ли страницы в index.md?

```python
def lint_report(wiki):
    return f"""
📊 Wiki Health Report
══════════════════════
Total pages:     {wiki.total_pages}
  seedling:      {wiki.count_status('seedling')} — нуждаются в углублении
  growing:       {wiki.count_status('growing')}
  evergreen:     {wiki.count_status('evergreen')}

Domains:         {len(wiki.domains)}
  tech:          {wiki.count_domain('tech')}
  business:      {wiki.count_domain('business')}
  science:       {wiki.count_domain('science')}
  life:          {wiki.count_domain('life')}

Orphans:         {wiki.count_orphans()} — без обратных связей
Cross-domain:    {wiki.count_cross_links()} ★ неожиданных связей
Stale (>3mo):    {wiki.count_stale()}
"""
```

---

## 7. Конфигурация времени выполнения

```python
# Быстрый ингест — только создать страницу
skill("wiki-maintainer", {
    "domain": "tech",
    "progressive_summarization": False,
    "auto_connect": False
})

# Полный цикл — создать + связать + продвинуть статус
skill("wiki-maintainer", {
    "domain": "auto",
    "compression": "smart",
    "auto_connect": True,
    "progressive_summarization": True
})

# Линт — проверить здоровье Wiki
skill("wiki-maintainer", {
    "domain": "auto",
    "lint_report": True
})

# Cross-domain review — найти неожиданные связи
skill("wiki-maintainer", {
    "domain": "auto",
    "cross_domain_review": True
})
```

---

## Что тебе это даёт (Life)

```
Через месяц:
  30+ страниц seedling — сырые заметки

Через полгода:
  200+ страниц, из них 50 growing, 10 evergreen
  Кросс-доменные связи: "переговоры в бизнесе"
  → "промпты для LLM"

Через год:
  Твой «второй мозг» с сотнями связанных страниц
  по всем сферам жизни — знания не теряются,
  а накапливаются и связываются.
```
