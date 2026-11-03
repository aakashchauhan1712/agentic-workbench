"""
Page: 💬 Chat Assistant
-----------------------
Multi-turn conversational chat using the GitHub Copilot SDK.
Conversation history is saved to disk so you can switch between
conversations and reload them later.

How a session works
-------------------
The first time the user sends a message, we call create_session_and_client()
which starts a CopilotClient and opens a Copilot session.  Both are stored in
st.session_state so they survive between Streamlit reruns.

On every subsequent message we call chat_with_session() which reuses the
same session — giving the agent memory of the whole conversation.
"""
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

import streamlit as st

from core.agent import create_session_and_client, chat_with_session
from core.config import Settings
from core.conversation_store import ConversationStore
from tools.file_tools import inspect_workspace_file

# ── Retrieve shared state ──────────────────────────────────────────────
settings: Settings = st.session_state["settings"]
conv_store: ConversationStore = st.session_state["conv_store"]

# ── Page header ────────────────────────────────────────────────────────
st.title("💬 Chat Assistant")
st.caption("Continuous conversational AI powered by GitHub Copilot SDK")

if not settings.resolved_github_token:
    st.error("No GITHUB_TOKEN found. Add it to your `.env` file and restart.")
    st.stop()

# ── Sidebar: conversation list ─────────────────────────────────────────
with st.sidebar:
    st.subheader("Conversations")
    if st.button("➕ New Conversation", use_container_width=True):
        new_id = conv_store.new_id()
        st.session_state["current_conv_id"] = new_id
        st.session_state["chat_messages"] = []
        # Clear the session so a fresh one is created next message
        st.session_state.pop("chat_client", None)
        st.session_state.pop("chat_session", None)
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
                st.session_state.pop("chat_client", None)
                st.session_state.pop("chat_session", None)
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

# ── Get or create Copilot client + session ────────────────────────────
def _get_or_create_session():
    """
    Return the existing Copilot session, or create a new one.
    The session is stored in st.session_state so it persists across reruns.
    """
    if "chat_session" not in st.session_state:
        system_msg = (
            "You are a helpful, concise AI assistant for the Agentic Workbench.\n"
            "You have access to a custom tool: `inspect_workspace_file`.\n"
            "When the user asks you to inspect, read, summarise, or check files in "
            "the repository (e.g. app.py, core/config.py), call `inspect_workspace_file` "
            "to fetch the real content.\n"
            "Maintain context across the conversation. Format responses in Markdown."
        )
        # create_session_and_client starts the SDK client AND opens a session
        # together inside a single asyncio.run() call — simple and correct.
        client, session = create_session_and_client(
            settings=settings,
            tools=[inspect_workspace_file],
            system_message=system_msg,
        )
        st.session_state["chat_client"] = client
        st.session_state["chat_session"] = session

    return st.session_state["chat_session"]


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

    # Send message to Copilot and show the reply
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                session = _get_or_create_session()
                reply = chat_with_session(settings, session, prompt, timeout=120.0)
            except Exception as e:
                # If the session broke, clear it so next message starts fresh
                st.session_state.pop("chat_client", None)
                st.session_state.pop("chat_session", None)
                reply = f"⚠️ Error communicating with Copilot: {e}"

        st.markdown(reply)

    messages.append({"role": "assistant", "content": reply})
    st.session_state["chat_messages"] = messages

    # Persist conversation to disk
    conv_store.save(conv_id, messages)
    st.rerun()
