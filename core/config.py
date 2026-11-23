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

    # Copilot model
    copilot_model: str = Field(default="gpt-4o", alias="COPILOT_MODEL")

    # Data directory (relative to project root)
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
    def conversations_dir(self) -> Path:
        return Path(self.data_dir) / "conversations"

    def ensure_dirs(self) -> None:
        self.conversations_dir.mkdir(parents=True, exist_ok=True)


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
    if not s.github_token:
        s.github_token = s.resolved_github_token

    s.ensure_dirs()
    return s
