"""
Page: 💬 Chat Assistant
-----------------------
Multi-turn conversational chat using the GitHub Copilot SDK.
Conversation history is persisted to disk so users can revisit it.

Architecture
------------
Each "conversation" has a stable `conv_id`. When the user switches
conversations or creates a new one the previous SDK session is left in
place (the SDK keeps context internally); we reconstruct the message
list from our local JSON store so the UI is always in sync.
"""
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

import asyncio
import streamlit as st

from core.agent import create_session, send_message, run_sync
from core.config import Settings
from core.conversation_store import ConversationStore
from tools.file_tools import inspect_workspace_file

# ── Retrieve shared state ──────────────────────────────────────────────
settings: Settings = st.session_state["settings"]
conv_store: ConversationStore = st.session_state["conv_store"]
copilot_client = st.session_state["copilot_client"]

# ── Page header ────────────────────────────────────────────────────────
st.title("💬 Chat Assistant")
st.caption("Continuous conversational AI powered by GitHub Copilot SDK")

if copilot_client is None:
    st.error("Copilot client is not available. Check your GITHUB_TOKEN in `.env`.")
    st.stop()

# ── Sidebar: conversation list ─────────────────────────────────────────
with st.sidebar:
    st.subheader("Conversations")
    if st.button("➕ New Conversation", use_container_width=True):
        new_id = conv_store.new_id()
        st.session_state["current_conv_id"] = new_id
        st.session_state["chat_messages"] = []
        # Drop old session so a fresh one is created
        st.session_state.pop("copilot_session_chat", None)
        st.rerun()

    st.divider()
    all_convs = conv_store.list_all()
    current_id = st.session_state.get("current_conv_id", "")

    for conv in all_convs:
        label = f"🗨️ {conv['title'][:30]}"
        is_current = conv["id"] == current_id
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(label, key=f"load_{conv['id']}", use_container_width=True,
                         type="primary" if is_current else "secondary"):
                st.session_state["current_conv_id"] = conv["id"]
                loaded = conv_store.load(conv["id"])
                st.session_state["chat_messages"] = loaded["messages"] if loaded else []
                st.session_state.pop("copilot_session_chat", None)
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{conv['id']}"):
                conv_store.delete(conv["id"])
                if conv["id"] == current_id:
                    st.session_state.pop("current_conv_id", None)
                    st.session_state["chat_messages"] = []
                st.rerun()

# ── Initialise conversation state ─────────────────────────────────────
if "current_conv_id" not in st.session_state:
    st.session_state["current_conv_id"] = conv_store.new_id()
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

conv_id = st.session_state["current_conv_id"]
messages: list[dict] = st.session_state["chat_messages"]

# ── Get or create Copilot session ─────────────────────────────────────
def _get_or_create_session():
    if "copilot_session_chat" not in st.session_state:
        system_msg = (
            "You are a helpful, concise AI assistant for the Agentic Workbench.\n"
            "You have access to a custom tool: `inspect_workspace_file`.\n"
            "When the user asks you to inspect, read, summarize, or check files in the repository "
            "(e.g. app.py, core/config.py), call `inspect_workspace_file` to fetch real content.\n"
            "Maintain context across the conversation. Format responses in Markdown."
        )
        session = run_sync(
            create_session(
                client=copilot_client,
                settings=settings,
                tools=[inspect_workspace_file],
                system_message=system_msg,
            )
        )
        st.session_state["copilot_session_chat"] = session
    return st.session_state["copilot_session_chat"]


# ── Render existing messages ───────────────────────────────────────────
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask me anything…"):
    # Show user message immediately
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get Copilot session and send message
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                session = _get_or_create_session()
                reply = run_sync(send_message(session, prompt, timeout=120.0))
            except Exception as e:
                # Reset cached session on error so retry uses fresh state
                st.session_state.pop("copilot_session_chat", None)
                reply = f"⚠️ Error communicating with Copilot: {e}"

        st.markdown(reply)

    messages.append({"role": "assistant", "content": reply})
    st.session_state["chat_messages"] = messages

    # Persist to disk
    conv_store.save(conv_id, messages)
    st.rerun()

