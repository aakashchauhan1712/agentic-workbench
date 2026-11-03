"""
Copilot agent helper.

Wraps the GitHub Copilot SDK so Streamlit pages can call async SDK
functions without needing to understand async / event loops.

How it works (beginner-friendly explanation)
--------------------------------------------
The GitHub Copilot SDK uses Python's `async/await` system internally.
Streamlit's UI runs in normal (synchronous) code.

`asyncio.run()` is Python's built-in bridge: it takes one async function,
runs it to completion, and hands back the result — just like a regular
function call. It creates a fresh event loop for that one task, then
cleans it up automatically.

That's all `run_sync()` does: it calls `asyncio.run()` for you.
"""
import asyncio
import sys

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from copilot import (
    CopilotClient,
    MCPHTTPServerConfig,
    MCPStdioServerConfig,
    PermissionHandler,
    Tool,
)
from copilot.session_events import AssistantMessageData

from core.config import Settings


# ---------------------------------------------------------------------------
# run_sync — the only "bridge" we need
# ---------------------------------------------------------------------------

def run_sync(coro):
    """
    Run an async coroutine from regular (synchronous) Streamlit code.

    Usage:
        result = run_sync(some_async_function(arg1, arg2))

    asyncio.run() works from any thread — including Streamlit's worker
    threads — so no extra threading setup is needed.
    """
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

async def _start_client(settings: Settings) -> CopilotClient:
    """Create and start a CopilotClient (runs inside asyncio.run)."""
    token = (settings.github_token or "").strip() or None

    # Download the Copilot CLI binary if it's missing (needed on cloud)
    try:
        from copilot._cli_download import get_or_download_cli
        get_or_download_cli()
    except Exception:
        pass  # Not fatal — skip silently

    client = CopilotClient(github_token=token)
    await client.start()
    return client


def get_client(settings: Settings) -> CopilotClient:
    """
    Create and start a CopilotClient synchronously.
    Called once from app.py and stored in st.session_state.
    """
    return run_sync(_start_client(settings))


async def _stop_client(client: CopilotClient) -> None:
    """Stop a running CopilotClient (runs inside asyncio.run)."""
    try:
        await client.stop()
    except Exception:
        pass  # Ignore errors on shutdown


def stop_client(client: CopilotClient) -> None:
    """Stop a CopilotClient synchronously."""
    run_sync(_stop_client(client))


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def _create_session(
    settings: Settings,
    tools: list | None = None,
    system_message: str | None = None,
    mcp_servers: dict | None = None,
):
    """
    Create a brand-new CopilotClient + session in one async block.

    Why create the client here too?
    Each asyncio.run() call gets its own event loop. The CopilotClient
    binds to the loop it was started in, so we must create it in the
    same loop as the session. This keeps the code simple and correct.
    """
    token = (settings.github_token or "").strip() or None

    # Download CLI binary if missing
    try:
        from copilot._cli_download import get_or_download_cli
        get_or_download_cli()
    except Exception:
        pass

    client = CopilotClient(github_token=token)
    await client.start()

    sm = {"mode": "replace", "content": system_message} if system_message else None

    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model=settings.copilot_model or None,
        tools=tools or [],
        system_message=sm,
        mcp_servers=mcp_servers,
        github_token=token,
    )

    # Return both so the caller can reuse the client for send_message
    return client, session


async def _send_message(session, message: str, timeout: float = 120.0) -> str:
    """Send one message and wait for the assistant reply (runs inside asyncio.run)."""
    event = await session.send_and_wait(message, timeout=timeout)
    return _extract_text(event)


# ---------------------------------------------------------------------------
# Public helpers used by Streamlit pages
# ---------------------------------------------------------------------------

def create_session_and_client(
    settings: Settings,
    tools: list | None = None,
    system_message: str | None = None,
    mcp_servers: dict | None = None,
):
    """
    Create a CopilotClient and session together.

    Returns: (client, session) — store both in st.session_state.
    On the next user message, pass them to chat_with_session().
    """
    return run_sync(
        _create_session(
            settings=settings,
            tools=tools,
            system_message=system_message,
            mcp_servers=mcp_servers,
        )
    )


def chat_with_session(
    settings: Settings,
    session,
    message: str,
    timeout: float = 120.0,
) -> str:
    """
    Send a message to an existing session and return the reply text.

    Because asyncio.run() creates a fresh loop each time, we must also
    re-attach the session's client to that loop.  The simplest way is to
    run both operations inside one async function.
    """
    async def _run():
        return await _send_message(session, message, timeout=timeout)

    return run_sync(_run())


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text(event) -> str:
    """Pull plain text out of a Copilot SessionEvent (ASSISTANT_MESSAGE)."""
    if event is None:
        return ""

    # Check event.data (AssistantMessageData)
    data = getattr(event, "data", None)
    if data is not None:
        if isinstance(data, AssistantMessageData) and getattr(data, "content", None):
            return data.content
        if hasattr(data, "content") and data.content:
            return data.content
        if isinstance(data, dict) and data.get("content"):
            return data["content"]

    # Check metadata list
    metadata = getattr(event, "metadata", None)
    if isinstance(metadata, list):
        for item in reversed(metadata):
            text = _try_extract_assistant_text(item)
            if text:
                return text

    # Fallback: walk the raw dict representation
    try:
        d = event.to_dict() if hasattr(event, "to_dict") else {}
        return _extract_text_from_dict(d)
    except Exception:
        return str(event)


def _try_extract_assistant_text(item) -> str:
    try:
        if hasattr(item, "type") and str(item.type) == "ASSISTANT_MESSAGE":
            data = getattr(item, "data", None)
            if data and hasattr(data, "content"):
                return data.content or ""
    except Exception:
        pass
    try:
        d = item.to_dict() if hasattr(item, "to_dict") else {}
        return _extract_text_from_dict(d)
    except Exception:
        return ""


def _extract_text_from_dict(d: dict) -> str:
    """Recursively search a dict for an assistant text content field."""
    if not isinstance(d, dict):
        return ""

    if "content" in d and isinstance(d["content"], str) and d["content"]:
        return d["content"]

    data = d.get("data", {})
    if isinstance(data, dict):
        content = data.get("content", "")
        if content and isinstance(content, str):
            return content

    for v in d.values():
        if isinstance(v, dict):
            result = _extract_text_from_dict(v)
            if result:
                return result
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    result = _extract_text_from_dict(item)
                    if result:
                        return result
    return ""
