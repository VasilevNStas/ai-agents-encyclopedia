"""Configuration for SupportFlow agent."""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class ModelConfig:
    """LLM model configuration."""

    provider: str = "anthropic"
    model_id: str = "claude-sonnet-4.6"
    cheap_model: str = "claude-haiku-4.6"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class BudgetConfig:
    """Budget control configuration."""

    max_cost_per_session: float = 0.50  # $
    max_llm_calls_per_session: int = 20
    max_tool_calls_per_session: int = 50
    alert_threshold: float = 0.40  # warn at 80%


@dataclass
class RAGConfig:
    """RAG configuration."""

    vector_db: str = "chroma"
    collection_name: str = "support-knowledge-base"
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    rerank_top_k: int = 3
    embedding_model: str = "text-embedding-3-small"


@dataclass
class SecurityConfig:
    """Security configuration."""

    pseudonymize_pii: bool = True
    audit_all_actions: bool = True
    require_hitl_for: tuple = ("delete", "send_email", "admin")
    max_sql_rows: int = 100


@dataclass
class AgentConfig:
    """Master configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Environment
    env: str = field(default_factory=lambda: os.getenv("ENV", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "info"))
    langfuse_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY")
    )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls()

    def is_production(self) -> bool:
        return self.env == "production"
