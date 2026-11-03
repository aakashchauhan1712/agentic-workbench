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
from core.agent import get_client


# ── Page configuration (must be FIRST Streamlit call) ─────────────────
st.set_page_config(
    page_title="Agentic Workbench",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Load settings & client bootstrap ──────────────────────────────────
settings = load_settings()
conv_store = ConversationStore(settings)

copilot_client = st.session_state.get("copilot_client")
client_error = None

if settings.resolved_github_token:
    force_reconnect = st.session_state.pop("_force_copilot_reconnect", False)
    if copilot_client is None or force_reconnect:
        try:
            copilot_client = get_client(settings, force_restart=force_reconnect)
        except Exception as e:
            copilot_client = None
            client_error = str(e)

st.session_state["settings"] = settings
st.session_state["conv_store"] = conv_store
st.session_state["copilot_client"] = copilot_client
st.session_state["client_error"] = client_error


# ── Sidebar status banner ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Agentic Workbench")
    st.caption("GitHub Copilot SDK Assistant")

    if settings.resolved_github_token:
        st.success("GitHub Copilot Connected", icon="🔑")
    else:
        st.warning("No GITHUB_TOKEN in .env", icon="⚠️")

    if client_error:
        st.error(f"Client warning:\n{client_error}")
        if st.button("🔄 Retry Connection", use_container_width=True):
            st.session_state["_force_copilot_reconnect"] = True
            st.rerun()

    st.divider()


# ── Navigation ─────────────────────────────────────────────────────────
chat_page   = st.Page("pages/chat.py",             title="Chat Assistant",       icon="💬", default=True)
gh_page     = st.Page("pages/github_assistant.py", title="GitHub Repo Assistant",icon="🐙")
review_page = st.Page("pages/file_reviewer.py",    title="File Reviewer",        icon="🔍")

pg = st.navigation([chat_page, gh_page, review_page])
pg.run()
