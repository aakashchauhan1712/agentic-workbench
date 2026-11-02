"""
Copilot agent bridge.
Wraps the GitHub Copilot SDK so that Streamlit pages interact with it
through a thread-safe async interface.

Key design decisions
--------------------
* Runs a dedicated background asyncio event loop thread (_AsyncBridge)
  so Streamlit's script-runner worker threads can dispatch coroutines
  cleanly via run_sync() without event loop collisions or shutdown errors.
* Automatically refreshes CopilotClient when GITHUB_TOKEN is updated.
* Each conversation retains its own Copilot session for continuous context.
* Extracts assistant message text from SessionEvent (ASSISTANT_MESSAGE).
"""
import asyncio
import sys
import threading
from typing import Optional

sys.path.insert(0, "C:/Users/Akash/AppData/Roaming/Python/Python312/site-packages")

from copilot import (
    CopilotClient,
    MCPHTTPServerConfig,
    MCPStdioServerConfig,
    PermissionHandler,
    SessionEventType,
    Tool,
)
from copilot.session_events import AssistantMessageData

from core.config import Settings


# -----------------------------------------------------------------------
# Thread-safe asyncio bridge
# -----------------------------------------------------------------------

class _AsyncBridge:
    """Dedicated background event loop thread for running async Copilot SDK tasks."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="CopilotAsyncLoop", daemon=True
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro, timeout: float = 180.0):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)


_bridge: Optional[_AsyncBridge] = None


def get_bridge() -> _AsyncBridge:
    global _bridge
    if _bridge is None:
        _bridge = _AsyncBridge()
    return _bridge


def run_sync(coro, timeout: float = 180.0):
    """Run an async coroutine thread-safely from any Streamlit runner thread."""
    return get_bridge().run(coro, timeout=timeout)


# -----------------------------------------------------------------------
# Client lifecycle
# -----------------------------------------------------------------------

_client: Optional[CopilotClient] = None
_client_token: Optional[str] = None


async def _start_client(settings: Settings, force_restart: bool = False) -> CopilotClient:
    global _client, _client_token
    token = (settings.github_token or "").strip() or None

    # If client is already running and token hasn't changed, reuse it
    if _client is not None and not force_restart and _client_token == token:
        return _client

    # Stop old client if running
    if _client is not None:
        try:
            await _client.stop()
        except Exception:
            pass
        _client = None

    # Ensure runtime binary exists (critical for Linux / Streamlit Cloud)
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
    return run_sync(_start_client(settings, force_restart=force_restart))


async def _stop_client():
    global _client, _client_token
    if _client is not None:
        try:
            await _client.stop()
        except Exception:
            pass
        _client = None
        _client_token = None


# -----------------------------------------------------------------------
# Session management
# -----------------------------------------------------------------------

async def create_session(
    client: CopilotClient,
    settings: Settings,
    tools: Optional[list[Tool]] = None,
    system_message: Optional[str] = None,
    mcp_servers: Optional[dict] = None,
) -> "CopilotSession":  # type: ignore[name-defined]
    """Create a new Copilot session."""
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
        # If token/session failed with 401 or bad credentials, retry with fresh client once
        if "Bad credentials" in err_msg or "401" in err_msg:
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
    """Send a message to an existing session and return the assistant reply text."""
    event = await session.send_and_wait(message, timeout=timeout)
    return _extract_text(event)


def _extract_text(event) -> str:
    """Pull plain text out of a SessionEvent (ASSISTANT_MESSAGE)."""
    if event is None:
        return ""

    # 1. Primary check: event.data (AssistantMessageData)
    data = getattr(event, "data", None)
    if data is not None:
        if isinstance(data, AssistantMessageData) and getattr(data, "content", None):
            return data.content
        if hasattr(data, "content") and data.content:
            return data.content
        if isinstance(data, dict) and data.get("content"):
            return data["content"]

    # 2. Check metadata list if present
    metadata = getattr(event, "metadata", None)
    if metadata is not None:
        if isinstance(metadata, list):
            for item in reversed(metadata):
                text = _try_extract_assistant_text(item)
                if text:
                    return text

    # 3. Fallback: walk the raw dict
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
    """Recursively look for content in a dict representation of an event."""
    if not isinstance(d, dict):
        return ""

    # Direct content field
    if "content" in d and isinstance(d["content"], str) and d["content"]:
        return d["content"]

    # Look in data.content
    data = d.get("data", {})
    if isinstance(data, dict):
        content = data.get("content", "")
        if content and isinstance(content, str):
            return content

    # Recurse into nested structures
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
