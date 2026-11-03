"""
Agentic Workbench – Main entry point.

Run with:
    python -m streamlit run app.py

Features:
- 💬 Chat Assistant: Multi-turn conversational chat powered by GitHub Copilot SDK.
- 🐙 GitHub Repo Assistant: Read-only repository inspection using GitHub MCP server.
- 🔍 File Reviewer: Skill-based file & code reviewer with diff display and human approval.
"""
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

import streamlit as st

# ── Project imports ────────────────────────────────────────────────────
from core.config import load_settings
from core.conversation_store import ConversationStore


# ── Page configuration (must be FIRST Streamlit call) ─────────────────
st.set_page_config(
    page_title="Agentic Workbench",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Load settings once and share with all pages ────────────────────────
# Settings reads GITHUB_TOKEN and COPILOT_MODEL from your .env file
# (or from Streamlit Cloud secrets when deployed).
settings = load_settings()
conv_store = ConversationStore(settings)

st.session_state["settings"] = settings
st.session_state["conv_store"] = conv_store


# ── Sidebar status banner ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Agentic Workbench")
    st.caption("GitHub Copilot SDK – Week 2 Demo")

    if settings.resolved_github_token:
        st.success("GitHub Copilot Connected", icon="🔑")
    else:
        st.warning("No GITHUB_TOKEN found in .env", icon="⚠️")

    st.divider()


# ── Navigation ─────────────────────────────────────────────────────────
chat_page   = st.Page("pages/chat.py",             title="Chat Assistant",       icon="💬", default=True)
gh_page     = st.Page("pages/github_assistant.py", title="GitHub Repo Assistant",icon="🐙")
review_page = st.Page("pages/file_reviewer.py",    title="File Reviewer",        icon="🔍")

pg = st.navigation([chat_page, gh_page, review_page])
pg.run()
