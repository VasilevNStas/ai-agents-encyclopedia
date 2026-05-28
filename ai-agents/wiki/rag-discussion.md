---
created: 2026-05-08
tags: [wiki/discussion, rag]
source: "opencode-2026-05-08_19.36.35.md"
status: active
---

# RAG — обсуждение по итогам урока 8

> [!summary] Что обсуждали
> Разбор отличий Naive RAG от RAG 2.0, выбор ключевых этапов пайплайна.

## Ключевые тезисы

1. **Naive RAG** — chunks → embed → search → LLM. Работает только в демках
2. **RAG 2.0** — 5 этапов: rewrite → hybrid search → rerank → enrich → generate
3. **Reranking** — выбран как самый важный этап (исправляет semantic gap)
4. **Query Rewriting и Contextual Enrichment** — опциональны, можно выкинуть без потери качества
5. **Retrieval** — если ничего не нашёл, остальные этапы бесполезны

## Вывод студента

> «Самое важное — Reranking. Выкинул бы Query Rewriting и Contextual Enrichment»

## Архитектурное замечание профессора

Reranking критичен, но Retrieval — фундамент. Без него нечего ранжировать.

## Связи

- [[03-memory-and-rag/02-rag-advanced]] — урок
- [[03-memory-and-rag/03-llm-wiki]] — альтернатива RAG
- [[03-memory-and-rag/03-llm-wiki]] — LLM Wiki подробнее
