"""
Copilot agent helper.

Wraps the GitHub Copilot SDK so Streamlit pages can interact with it
synchronously without needing complex threading.

How it works (Beginner-Friendly Explanation)
--------------------------------------------
1. Python's GitHub Copilot SDK is asynchronous (`async/await`) because it
   communicates with an external Copilot process in real time.
2. Streamlit apps run in regular synchronous Python code.
3. To bridge them, we keep one persistent event loop (`get_event_loop()`)
   and execute async calls with `loop.run_until_complete(coro)`.
4. This avoids `RuntimeError: Event loop is closed` because the loop stays
   alive across multiple requests (just like Week 1's architecture).
"""
import asyncio
import sys
from typing import Optional

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
# Persistent Event Loop & run_sync Bridge
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the shared persistent event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def run_sync(coro):
    """
    Run an async coroutine from synchronous Streamlit code.

    Keeps the loop open so background JSON-RPC listeners in the Copilot SDK
    continue running smoothly without 'Event loop is closed' errors.
    """
    loop = get_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Client Lifecycle
# ---------------------------------------------------------------------------

_client: Optional[CopilotClient] = None
_client_token: Optional[str] = None


async def _start_client(settings: Settings, force_restart: bool = False) -> CopilotClient:
    global _client, _client_token
    token = (settings.github_token or "").strip() or None

    # Reuse running client if token hasn't changed
    if _client is not None and not force_restart and _client_token == token:
        return _client

    # Stop previous client if needed
    if _client is not None:
        try:
            await _client.stop()
        except Exception:
            pass
        _client = None

    # Download Copilot CLI binary if missing (needed for cloud platforms)
    try:
        from copilot._cli_download import get_or_download_cli
        get_or_download_cli()
    except Exception:
        pass

    _client = CopilotClient(github_token=token)
    _client_token = token
    await _client.start()
    return _client


def get_client(settings: Settings, force_restart: bool = False) -> CopilotClient:
    """Create and start the CopilotClient synchronously."""
    return run_sync(_start_client(settings, force_restart=force_restart))


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

async def create_session(
    client: CopilotClient,
    settings: Settings,
    tools: Optional[list[Tool]] = None,
    system_message: Optional[str] = None,
    mcp_servers: Optional[dict] = None,
):
    """Create a new Copilot conversation session."""
    token = (settings.github_token or "").strip() or None
    sm = {"mode": "replace", "content": system_message} if system_message else None

    try:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=settings.copilot_model or None,
            tools=tools or [],
            system_message=sm,
            mcp_servers=mcp_servers,
            github_token=token,
        )
        return session
    except Exception as err:
        err_msg = str(err)
        if "Bad credentials" in err_msg or "401" in err_msg:
            # Token issue or stale connection — restart client once
            fresh_client = await _start_client(settings, force_restart=True)
            return await fresh_client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=settings.copilot_model or None,
                tools=tools or [],
                system_message=sm,
                mcp_servers=mcp_servers,
                github_token=token,
            )
        raise


async def send_message(session, message: str, timeout: float = 120.0) -> str:
    """Send a message to an active Copilot session and return assistant text."""
    event = await session.send_and_wait(message, timeout=timeout)
    return _extract_text(event)


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def _extract_text(event) -> str:
    """Extract readable text from a Copilot SessionEvent."""
    if event is None:
        return ""

    data = getattr(event, "data", None)
    if data is not None:
        if isinstance(data, AssistantMessageData) and getattr(data, "content", None):
            return data.content
        if hasattr(data, "content") and data.content:
            return data.content
        if isinstance(data, dict) and data.get("content"):
            return data["content"]

    metadata = getattr(event, "metadata", None)
    if isinstance(metadata, list):
        for item in reversed(metadata):
            text = _try_extract_assistant_text(item)
            if text:
                return text

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
            res = _extract_text_from_dict(v)
            if res:
                return res
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    res = _extract_text_from_dict(item)
                    if res:
                        return res
    return ""
