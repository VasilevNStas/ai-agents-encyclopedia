#!/usr/bin/env python3
"""
RAG Pipeline — гибридный поиск по markdown-файлам курса.

Без внешних зависимостей: TF-IDF (keyword) + простой semantic (embedding опционально).

Использование:
  python3 rag_pipeline.py                          # демо
  python3 rag_pipeline.py "что такое ReAct?"        # поиск по вопросу

Зависимости (опционально):
  pip install numpy          # для cosine similarity
  pip install sentence-transformers  # для семантического поиска
"""

import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from glob import glob

# ─── Конфигурация ──────────────────────────────────────────────────

COURSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_K = 5         # сколько результатов вернуть
CHUNK_SIZE = 300  # токенов на чанк (приблизительно)

# ─── Chunking ──────────────────────────────────────────────────────

@dataclass
class Chunk:
    doc_id: str
    text: str
    metadata: dict

def chunk_markdown(filepath: str) -> list[Chunk]:
    """Разбивает markdown-файл на чанки по заголовкам."""

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath)
    rel_path = os.path.relpath(filepath, COURSE_DIR)

    # Извлекаем YAML frontmatter
    meta = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            text = parts[2]

    # Разбиваем по заголовкам второго уровня (##)
    sections = re.split(r"\n## ", text)
    chunks = []

    for i, section in enumerate(sections):
        # Первая секция — заголовок документа
        if i == 0:
            title = meta.get("tags", "unknown")
        else:
            title = section.split("\n")[0].strip()

        # Если секция слишком длинная — режем ещё
        if len(section) > CHUNK_SIZE * 4:
            sub_chunks = [section[j:j + CHUNK_SIZE * 4]
                          for j in range(0, len(section), CHUNK_SIZE * 4)]
            for j, sub in enumerate(sub_chunks):
                chunks.append(Chunk(
                    doc_id=f"{rel_path}#{title}#{j}",
                    text=sub.strip(),
                    metadata={
                        "file": rel_path,
                        "section": title,
                        "part": j + 1,
                        **meta
                    }
                ))
        else:
            chunks.append(Chunk(
                doc_id=f"{rel_path}#{title}",
                text=section.strip(),
                metadata={
                    "file": rel_path,
                    "section": title,
                    **meta
                }
            ))

    return chunks


def index_course() -> list[Chunk]:
    """Индексирует все .md файлы курса в чанки."""

    files = glob(os.path.join(COURSE_DIR, "**/*.md"), recursive=True)
    # Исключаем .obsidian/
    files = [f for f in files if ".obsidian" not in f]

    all_chunks = []
    for f in files:
        try:
            all_chunks.extend(chunk_markdown(f))
        except Exception as e:
            print(f"  ⚠ Ошибка индексации {f}: {e}")

    return all_chunks


# ─── TF-IDF (keyword search) ──────────────────────────────────────

class TFIDFIndex:
    """Простой TF-IDF без внешних зависимостей."""

    def __init__(self):
        self.doc_count = 0
        self.df = Counter()  # document frequency
        self.chunks = []

    def fit(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.doc_count = len(chunks)

        for chunk in chunks:
            terms = set(tokenize(chunk.text))
            for t in terms:
                self.df[t] += 1

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        query_terms = tokenize(query)
        scores = []

        for chunk in self.chunks:
            score = 0
            doc_terms = tokenize(chunk.text)
            doc_len = len(doc_terms)
            term_counts = Counter(doc_terms)

            for term in query_terms:
                tf = term_counts.get(term, 0) / max(doc_len, 1)
                idf = math.log((self.doc_count + 1) / (self.df.get(term, 0) + 1)) + 1
                score += tf * idf

            scores.append((chunk, score))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


def tokenize(text: str) -> list[str]:
    """Токенизация: нижний регистр, только слова."""
    text = text.lower()
    # Русские и английские слова
    tokens = re.findall(r"[а-яёa-z]+", text)
    # Фильтр коротких и стоп-слов
    stop_words = {"это", "что", "как", "для", "все", "если", "то", "по",
                  "на", "не", "он", "она", "они", "его", "ее", "их",
                  "the", "and", "for", "are", "but", "not", "you", "all",
                  "can", "had", "her", "was", "one", "our", "out"}
    return [t for t in tokens if len(t) > 2 and t not in stop_words]


# ─── Semantic Search (опционально) ────────────────────────────────

def semantic_search(query: str, chunks: list[Chunk], top_k: int = 5) -> list[tuple[Chunk, float]]:
    """Семантический поиск через sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")

        query_emb = model.encode(query)
        chunk_embs = model.encode([c.text[:500] for c in chunks])

        scores = np.dot(chunk_embs, query_emb) / (
            np.linalg.norm(chunk_embs, axis=1) * np.linalg.norm(query_emb) + 1e-8
        )

        ranked = sorted(zip(chunks, scores), key=lambda x: -x[1])
        return ranked[:top_k]

    except ImportError:
        print("  ⚠ sentence-transformers не установлен. Использую только TF-IDF.")
        return []


# ─── Reranking ─────────────────────────────────────────────────────

def rerank(query: str, results: list[tuple[Chunk, float]], top_k: int = 3) -> list[tuple[Chunk, float]]:
    """Reranking: термины запроса должны быть в chunk равномерно."""

    query_terms = set(tokenize(query))
    scored = []

    for chunk, tfidf_score in results:
        chunk_terms = set(tokenize(chunk.text))

        # Сколько терминов запроса есть в чанке
        overlap = len(query_terms & chunk_terms) / max(len(query_terms), 1)

        # Финальная оценка: TF-IDF + overlap
        final_score = tfidf_score * 0.7 + overlap * 0.3
        scored.append((chunk, final_score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


# ─── Query Rewriting ──────────────────────────────────────────────

def rewrite_query(query: str) -> str:
    """Переформулирует запрос для поиска (убирает шум)."""

    # Убираем вопросительные конструкции
    cleaned = re.sub(r"(расскажи|объясни|что такое|как работает|что значит)\s+",
                     "", query, flags=re.IGNORECASE)
    # Убираем знаки вопроса и лишние пробелы
    cleaned = cleaned.replace("?", "").replace("!", "").strip()
    return cleaned if cleaned else query


# ─── Contextual Enrichment ────────────────────────────────────────

def enrich(chunk: Chunk) -> str:
    """Добавляет метаданные к чанку."""
    meta = chunk.metadata
    source = meta.get("file", "unknown")
    section = meta.get("section", "")
    tags = meta.get("tags", "")

    header = f"[{source}"
    if section:
        header += f" → {section}"
    header += "]"

    return f"{header}\n{chunk.text}"


# ─── Полный пайплайн ──────────────────────────────────────────────

def rag_pipeline(query: str, chunks: list[Chunk]) -> str:
    """Полный RAG 2.0 пайплайн."""

    print(f"\n🔍 Запрос: {query}")
    print(f"📦 Всего чанков: {len(chunks)}")
    print()

    # 1. Query rewriting
    rewritten = rewrite_query(query)
    if rewritten != query:
        print(f"✏️ Переформулирован: {rewritten}")

    # 2. Hybrid search
    print("\n📊 Hybrid Search:")
    tfidf = TFIDFIndex()
    tfidf.fit(chunks)

    keyword_results = tfidf.search(rewritten, top_k=10)
    semantic_results = semantic_search(rewritten, chunks, top_k=5)

    # Fusion: объединяем результаты
    seen = set()
    combined = []
    for chunk, score in keyword_results + semantic_results:
        if chunk.doc_id not in seen:
            seen.add(chunk.doc_id)
            combined.append((chunk, score))
    combined.sort(key=lambda x: -x[1])

    print(f"   Найдено: {len(combined)} кандидатов")

    # 3. Reranking
    print("\n🎯 Reranking:")
    reranked = rerank(rewritten, combined, top_k=TOP_K)
    print(f"   Топ-{TOP_K} после reranking:")

    # 4. Contextual enrichment + generation
    context_parts = []
    for i, (chunk, score) in enumerate(reranked, 1):
        enriched_text = enrich(chunk)
        context_parts.append(enriched_text)
        print(f"   [{i}] {chunk.metadata.get('file', '?')} → {chunk.metadata.get('section', '?')} (score: {score:.3f})")

    # 5. Формируем контекст для LLM
    context = "\n\n".join(context_parts)

    prompt = f"""
Ты — ассистент, отвечающий на вопросы по курсу "Работа с AI-агентом".

Контекст из материалов курса:
{context}

Вопрос: {query}

Ответь на основе контекста. Если контекст не содержит ответа — скажи "в материалах курса нет информации об этом".
Цитируй источники в формате [файл → раздел].
"""

    return {
        "prompt": prompt,
        "sources": [(c.metadata.get("file", "?"), c.metadata.get("section", "?"))
                    for c, _ in reranked]
    }


# ─── CLI ───────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("RAG Pipeline v1.0 — гибридный поиск по курсу")
    print("=" * 60)

    # Индексируем курс
    print("\n📚 Индексация курса...")
    chunks = index_course()
    print(f"   Проиндексировано: {len(chunks)} чанков")

    # Запрос
    query = sys.argv[1] if len(sys.argv) > 1 else "что такое ReAct и как он работает?"
    result = rag_pipeline(query, chunks)

    print("\n" + "=" * 60)
    print("📝 Итоговый промпт для LLM:")
    print("=" * 60)
    print(result["prompt"][:500] + "...")
    print()
    print("📎 Источники:")
    for file, section in result["sources"]:
        print(f"   • {file} → {section}")


if __name__ == "__main__":
    main()
