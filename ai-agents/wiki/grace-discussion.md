---
created: 2026-05-09
tags: [wiki/grace, graph-rag, code-engineering]
status: active
---

# GRACE — обсуждаемые идеи

> GRACE (Graph-RAG Anchored Code Engineering) — реализация GraphRAG от Владимира Иванова (@turboplanner), заточенная под анализ кода.

## Источники

- [GRACE Marketplace](https://github.com/osovv/grace-marketplace)
- [GRACE Docx (bootstrap)](https://github.com/xronocode/grace-docx/blob/main/grace-docx-bootstrap.md)
- Канал: https://t.me/turboproject

## Ключевые мысли

- Обычный RAG теряет связи между кусками — GRACE строит их в граф
- Anchored = запрос привязывается к узлу графа, потом идёт по связям
- Для кода важнее архитектура (кто кого вызывает), а не просто текст
- GRACE + ReAct: агент может делать `#graph`-запросы прямо в цикле

## Вопросы

- Как GRACE масштабируется на большие проекты (1000+ файлов)?
- Можно ли комбинировать GRACE с RAG (RAG для доки, GRACE для кода)?

## Связанные уроки

- [[03-memory-and-rag/04-grace]] — урок 10
- [[03-memory-and-rag/02-rag-advanced]] — RAG 2.0
