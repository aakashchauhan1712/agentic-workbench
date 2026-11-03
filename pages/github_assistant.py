"""
Page: 🐙 GitHub Repository Assistant (MCP)
-------------------------------------------
Integrates the official GitHub MCP server with the Copilot SDK so the
agent can inspect repositories, list files, and read source code.

The GitHub MCP server is accessed via HTTP/SSE at:
    https://api.githubcopilot.com/mcp/

All access is read-only in the initial implementation.

Week 2 concepts demonstrated here
----------------------------------
- MCP server integration (MCPHTTPServerConfig)
- Tool allow-lists / restrictions (tools=[...] on the server config)
"""
import sys
sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

import streamlit as st
from copilot import MCPHTTPServerConfig

from core.agent import create_session_and_client, chat_with_session
from core.config import Settings

# ── Shared state ───────────────────────────────────────────────────────
settings: Settings = st.session_state["settings"]

# ── Page header ────────────────────────────────────────────────────────
st.title("🐙 GitHub Repository Assistant")
st.caption("Ask questions about GitHub repositories. Powered by the GitHub MCP server.")

if not settings.resolved_github_token:
    st.error("No GITHUB_TOKEN found. Add it to your `.env` file and restart.")
    st.stop()

# ── Session state ─────────────────────────────────────────────────────
if "gh_messages" not in st.session_state:
    st.session_state["gh_messages"] = []
if "gh_repo" not in st.session_state:
    st.session_state["gh_repo"] = ""

messages: list[dict] = st.session_state["gh_messages"]

# ── Sidebar: configuration ────────────────────────────────────────────
with st.sidebar:
    st.subheader("🔧 Configuration")
    repo_input = st.text_input(
        "Repository (owner/repo)",
        value=st.session_state["gh_repo"],
        placeholder="e.g. microsoft/vscode",
    )
    if repo_input != st.session_state["gh_repo"]:
        st.session_state["gh_repo"] = repo_input
        # Reset session when repo changes
        st.session_state.pop("gh_client", None)
        st.session_state.pop("gh_session", None)
        st.session_state["gh_messages"] = []
        st.rerun()

    st.divider()
    st.subheader("🛡️ MCP Tool Allow-list")
    tool_policy = st.selectbox(
        "Tool Policy",
        ["All Tools (*)", "Strict Read-Only Allow-list"],
        help="Demonstrates Week 2 MCP server tool allow-lists and restrictions.",
    )
    # Reset session when policy changes
    if st.session_state.get("_last_tool_policy") != tool_policy:
        st.session_state["_last_tool_policy"] = tool_policy
        st.session_state.pop("gh_client", None)
        st.session_state.pop("gh_session", None)

    st.caption(
        f"Active MCP Policy: **{tool_policy}**.\n"
        "Restricts tool availability to adhere to the principle of least privilege."
    )

    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state["gh_messages"] = []
        st.session_state.pop("gh_client", None)
        st.session_state.pop("gh_session", None)
        st.rerun()

    # Quick-start prompts
    st.divider()
    st.subheader("💡 Quick Prompts")
    quick_prompts = [
        "What does this repository do? Give me a summary.",
        "List the top-level files and directories.",
        "What language is this project primarily written in?",
        "Show me the main entry point file.",
        "Explain the folder structure.",
    ]
    for qp in quick_prompts:
        if st.button(qp[:45] + ("…" if len(qp) > 45 else ""), key=f"qp_{qp[:20]}",
                     use_container_width=True):
            st.session_state["_gh_quick_prompt"] = qp


# ── Build MCP-enabled Copilot session ─────────────────────────────────
def _get_gh_session():
    """Return the existing GitHub session or create a new one with MCP configured."""
    if "gh_session" not in st.session_state:
        repo = st.session_state.get("gh_repo", "")
        repo_context = f"The user wants to explore the repository: {repo}. " if repo else ""
        system_msg = (
            f"{repo_context}"
            "You are a GitHub repository expert assistant. "
            "Use the available GitHub tools (provided via MCP) to answer questions about "
            "repositories. Only perform read operations — never write, push, or delete anything. "
            "When listing files, show them in a readable format. "
            "When reading code, provide clear explanations."
        )

        mcp_token = settings.github_mcp_token or settings.github_token

        # Week 2 concept: MCP tool allow-lists
        policy = st.session_state.get("_last_tool_policy", "All Tools (*)")
        if policy == "Strict Read-Only Allow-list":
            # Only allow read-style tools — no write, delete, or push operations
            mcp_tools = ["*get*", "*list*", "*read*", "*search*"]
        else:
            mcp_tools = ["*"]  # All tools

        mcp_servers = {
            "github": MCPHTTPServerConfig(
                url="https://api.githubcopilot.com/mcp/",
                headers={"Authorization": f"Bearer {mcp_token}"},
                tools=mcp_tools,
            )
        }

        # Create client + session together — simple, no threading required
        client, session = create_session_and_client(
            settings=settings,
            system_message=system_msg,
            mcp_servers=mcp_servers,
        )
        st.session_state["gh_client"] = client
        st.session_state["gh_session"] = session

    return st.session_state["gh_session"]


# ── Render messages ────────────────────────────────────────────────────
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not messages:
    repo_display = st.session_state.get("gh_repo") or "a GitHub repository"
    st.info(
        f"Ask me anything about **{repo_display}**. "
        f"Set the repository in the sidebar first, or just ask a question!"
    )

# ── Handle quick prompts ───────────────────────────────────────────────
quick_prompt = st.session_state.pop("_gh_quick_prompt", None)


def _handle_prompt(prompt: str):
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying GitHub via MCP…"):
            try:
                session = _get_gh_session()
                reply = chat_with_session(settings, session, prompt, timeout=180.0)
            except Exception as e:
                st.session_state.pop("gh_client", None)
                st.session_state.pop("gh_session", None)
                reply = f"⚠️ Error: {e}"
        st.markdown(reply)

    messages.append({"role": "assistant", "content": reply})
    st.session_state["gh_messages"] = messages
    st.rerun()


if quick_prompt:
    _handle_prompt(quick_prompt)

if prompt := st.chat_input("Ask about a GitHub repository…"):
    _handle_prompt(prompt)
