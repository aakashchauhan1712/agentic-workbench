"""
Conversation persistence – save/load/list chat histories as JSON files.
Each conversation is stored in data/conversations/<id>.json
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import Settings


class ConversationStore:
    """Manages persisted conversation histories."""

    def __init__(self, settings: Settings) -> None:
        self.dir = settings.conversations_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def save(
        self,
        conv_id: str,
        messages: list[dict],
        title: Optional[str] = None,
    ) -> None:
        """Persist a conversation to disk."""
        record = {
            "id": conv_id,
            "title": title or self._auto_title(messages),
            "updated_at": datetime.utcnow().isoformat(),
            "messages": messages,
        }
        path = self._path(conv_id)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, conv_id: str) -> Optional[dict]:
        """Return conversation record or None."""
        path = self._path(conv_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_all(self) -> list[dict]:
        """Return metadata for all conversations, newest first."""
        records = []
        for p in sorted(self.dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                records.append(
                    {
                        "id": data["id"],
                        "title": data.get("title", data["id"]),
                        "updated_at": data.get("updated_at", ""),
                    }
                )
            except Exception:
                continue
        return records

    def delete(self, conv_id: str) -> None:
        self._path(conv_id).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _path(self, conv_id: str) -> Path:
        return self.dir / f"{conv_id}.json"

    def _auto_title(self, messages: list[dict]) -> str:
        for m in messages:
            if m.get("role") == "user":
                text = m.get("content", "")
                return (text[:50] + "…") if len(text) > 50 else text
        return "Untitled"

