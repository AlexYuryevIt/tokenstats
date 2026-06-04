"""
Goose provider — parses session data from Goose (Block's open-source agent).

Data location:
  ~/.local/share/goose/sessions/*.json
  ~/.config/goose/sessions/*.json
"""
import json
import os
from pathlib import Path
from typing import Optional

from models import Session, Message
from .base import BaseProvider, register


CANDIDATE_DIRS = [
    Path.home() / ".local/share/goose/sessions",
    Path.home() / ".config/goose/sessions",
    Path(os.environ.get("APPDATA", "")) / "Block" / "goose" / "data" / "sessions",
]


def _find_sessions_dir() -> Optional[Path]:
    for d in CANDIDATE_DIRS:
        if d.is_dir():
            return d
    return None


@register
class Goose(BaseProvider):
    name = "goose"
    display_name = "Goose"

    @classmethod
    def detect(cls) -> bool:
        return _find_sessions_dir() is not None

    @classmethod
    def list_sessions(cls) -> list[Session]:
        sdir = _find_sessions_dir()
        if not sdir:
            return []

        sessions = []
        for f in sorted(sdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            sid = data.get("session_id") or data.get("id") or f.stem
            title = data.get("title") or data.get("summary", "") or ""
            ts = data.get("created_at") or int(f.stat().st_mtime * 1000)

            total_in = 0
            total_out = 0
            steps = 0
            model = data.get("model", "")

            messages = data.get("messages", data.get("conversation", data.get("history", [])))
            for msg in messages:
                role = msg.get("role", "")
                usage = msg.get("usage") or msg.get("tokens") or {}

                inp = usage.get("input_tokens", usage.get("input", 0)) or 0
                out = usage.get("output_tokens", usage.get("output", 0)) or 0

                if not inp and not out:
                    content = msg.get("content", "")
                    text = str(content) if isinstance(content, str) else json.dumps(content)
                    if role == "assistant":
                        out = len(text) // 4
                    else:
                        inp = len(text) // 4

                total_in += inp
                total_out += out
                if role == "assistant":
                    steps += 1
                    if not model and msg.get("model"):
                        model = msg["model"]

            sessions.append(Session(
                id=sid,
                title=title[:80],
                provider=cls.name,
                project="",
                input_tokens=total_in,
                output_tokens=total_out,
                reasoning_tokens=0,
                cache_read=0,
                cache_write=0,
                cost=0,
                steps=steps,
                model=model if isinstance(model, str) else "",
                time_created=int(ts) if isinstance(ts, int) else int(ts or 0),
            ))
        return sessions

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        sdir = _find_sessions_dir()
        if not sdir:
            return []

        for f in sdir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            cid = data.get("session_id") or data.get("id") or f.stem
            if cid == session_id:
                return cls._extract_messages(data, session_id)
        return []

    @classmethod
    def _extract_messages(cls, data: dict, session_id: str) -> list[Message]:
        messages = []
        for msg in data.get("messages", data.get("conversation", data.get("history", []))):
            if msg.get("role") != "assistant":
                continue
            usage = msg.get("usage") or msg.get("tokens") or {}
            finish_reason = msg.get("finish_reason", "") or ""
            model_name = msg.get("model") or ""
            timestamp = msg.get("timestamp") or 0
            messages.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=usage.get("input_tokens", usage.get("input", 0)) or 0,
                output_tokens=usage.get("output_tokens", usage.get("output", 0)) or 0,
                reasoning_tokens=usage.get("reasoning_tokens", 0) or 0,
                cache_read=usage.get("cache_read_input_tokens", 0) or 0,
                cache_write=usage.get("cache_creation_input_tokens", 0) or 0,
                cost=0,
                finish_reason=finish_reason,
                time_created=int(timestamp) if isinstance(timestamp, (int, float)) else None,
            ))
        return messages
