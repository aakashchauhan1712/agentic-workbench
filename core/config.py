"""
Agentic Workbench – Configuration
Loads settings from .env, environment variables, or Streamlit Cloud Secrets (st.secrets).
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GitHub token (required for Copilot SDK)
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_mcp_token: str = Field(default="", alias="GITHUB_MCP_TOKEN")

    # Google Gemini API key (for LangChain RAG & Gemini 2.5)
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    # Embedding model
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )

    # Copilot model
    copilot_model: str = Field(default="gpt-4o", alias="COPILOT_MODEL")

    # Data directory (relative to the project root)
    data_dir: str = Field(default="data", alias="DATA_DIR")
    app_title: str = Field(default="Agentic Workbench", alias="APP_TITLE")

    @property
    def resolved_github_token(self) -> str:
        token = (self.github_token or "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
        if not token:
            try:
                import streamlit as st
                token = st.secrets.get("GITHUB_TOKEN", "")
            except Exception:
                pass
        return token.strip()

    @property
    def resolved_google_api_key(self) -> str:
        key = (
            (self.google_api_key or "").strip()
            or (self.gemini_api_key or "").strip()
            or os.getenv("GOOGLE_API_KEY", "").strip()
            or os.getenv("GEMINI_API_KEY", "").strip()
        )
        if not key:
            try:
                import streamlit as st
                key = st.secrets.get("GOOGLE_API_KEY", "") or st.secrets.get("GEMINI_API_KEY", "")
            except Exception:
                pass
        return key.strip()

    @property
    def conversations_dir(self) -> Path:
        return Path(self.data_dir) / "conversations"

    @property
    def uploads_dir(self) -> Path:
        return Path(self.data_dir) / "uploads"

    @property
    def vector_stores_dir(self) -> Path:
        return Path(self.data_dir) / "vector_stores"

    def ensure_dirs(self) -> None:
        for d in [self.conversations_dir, self.uploads_dir, self.vector_stores_dir]:
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Load and return settings. Seamlessly pulls from .env and Streamlit secrets."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for k, v in st.secrets.items():
                if isinstance(v, str) and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

    s = Settings()
    # Apply resolved fallbacks if fields are empty
    if not s.github_token:
        s.github_token = s.resolved_github_token
    if not s.google_api_key:
        s.google_api_key = s.resolved_google_api_key

    s.ensure_dirs()
    return s
