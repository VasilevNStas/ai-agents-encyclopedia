"""Tests for memory components."""

import pytest
import sys
from pathlib import Path

_memory_dir = Path(__file__).resolve().parent.parent / "02-memory"
if str(_memory_dir) not in sys.path:
    sys.path.insert(0, str(_memory_dir))

from src.agent.config import AgentConfig, RAGConfig


class TestShortTermMemorySlidingWindow:
    def test_adds_messages(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=3)
        m.add("user", "hello")
        m.add("assistant", "hi there")
        m.add("user", "help me")

        assert m.count == 3

    def test_sliding_window_trims_oldest(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=3)
        m.add("user", "msg1")
        m.add("user", "msg2")
        m.add("user", "msg3")
        m.add("user", "msg4")

        assert m.count == 3
        context = m.get_context()
        assert context[0]["content"] == "msg2"

    def test_get_context_returns_last_n(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=10)
        for i in range(5):
            m.add("user", f"msg{i}")

        context = m.get_context(limit=2)
        assert len(context) == 2
        assert context[0]["content"] == "msg3"
        assert context[-1]["content"] == "msg4"

    def test_clear_resets(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=10)
        m.add("user", "hello")
        m.clear()
        assert m.count == 0

    def test_timestamp_included(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=10)
        m.add("user", "test")
        msg = m.get_context()[0]
        assert "timestamp" in msg
        assert "role" in msg
        assert msg["role"] == "user"

    def test_multiple_roles(self):
        from memory import ShortTermMemory

        m = ShortTermMemory(max_messages=10)
        m.add("user", "hello")
        m.add("assistant", "world")
        m.add("tool", "result")
        m.add("user", "thanks")

        roles = [msg["role"] for msg in m.get_context()]
        assert roles == ["user", "assistant", "tool", "user"]


class TestWorkingMemoryCRUD:
    def test_set_and_get(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("user_name", "Alice")
        assert wm.get("user_name") == "Alice"

    def test_get_default(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        assert wm.get("missing_key") is None
        assert wm.get("missing_key", "default") == "default"

    def test_update_dict_merge(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("plan", {"step1": "search", "step2": "answer"})
        wm.update("plan", {"step3": "escalate"})
        assert wm.get("plan") == {
            "step1": "search",
            "step2": "answer",
            "step3": "escalate",
        }

    def test_update_list_extend(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("results", ["a", "b"])
        wm.update("results", ["c", "d"])
        assert wm.get("results") == ["a", "b", "c", "d"]

    def test_contains(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("key1", "val1")
        assert "key1" in wm
        assert "key2" not in wm

    def test_items_returns_copy(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("a", 1)
        wm.set("b", 2)
        data = wm.items()
        assert data == {"a": 1, "b": 2}
        data["c"] = 3
        assert "c" not in wm

    def test_clear(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("key", "value")
        wm.clear()
        assert wm.get("key") is None

    def test_update_overwrite_non_dict(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.set("count", 5)
        wm.update("count", 10)
        assert wm.get("count") == 10

    def test_update_creates_if_missing(self):
        from memory import WorkingMemory

        wm = WorkingMemory()
        wm.update("new_key", "new_value")
        assert wm.get("new_key") == "new_value"


class TestVectorStoreSearch:
    def test_empty_store_returns_empty(self):
        from vector_store import VectorStore

        vs = VectorStore()
        results = vs.search("anything")
        assert results == []

    def test_add_and_search(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents(["How to reset password", "Billing guide"])
        results = vs.search("password")
        assert len(results) > 0
        assert "password" in results[0]["text"].lower()

    def test_search_returns_top_k(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents([f"doc {i}" for i in range(20)])
        results = vs.search("doc", top_k=5)
        assert len(results) == 5

    def test_search_includes_scores(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents(["apple", "banana", "cherry"])
        results = vs.search("apple")
        assert all("score" in r for r in results)

    def test_add_with_metadata(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents(
            ["password reset guide"],
            metadata_list=[{"category": "technical", "source": "kb"}],
        )
        results = vs.search("password")
        assert results[0]["metadata"]["category"] == "technical"

    def test_delete_collection(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents(["some text"])
        vs.delete_collection()
        assert vs.document_count == 0

    def test_add_duplicate_documents(self):
        from vector_store import VectorStore

        vs = VectorStore()
        vs.add_documents(["text"])
        vs.add_documents(["text"])
        results = vs.search("text")
        assert len(results) >= 1

    def test_document_count(self):
        from vector_store import VectorStore

        vs = VectorStore()
        assert vs.document_count == 0
        vs.add_documents(["a", "b", "c"])
        assert vs.document_count == 3

    def test_mismatched_texts_and_metadata_raises(self):
        from vector_store import VectorStore

        vs = VectorStore()
        with pytest.raises(ValueError, match="must have the same length"):
            vs.add_documents(["text"], metadata_list=[{}, {}])
