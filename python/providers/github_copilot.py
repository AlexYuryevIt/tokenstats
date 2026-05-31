"""
GitHub Copilot CLI provider — parses session JSON files.

Data locations:
  ~/.local/share/github-copilot-cli/sessions/*.json
  ~/.config/github-copilot/sessions/*.json
"""
import json
from pathlib import Path
from typing import Optional

from models import Session, Message
from .base import BaseProvider, register


CANDIDATE_DIRS = [
    Path.home() / ".local/share/github-copilot-cli/sessions",
    Path.home() / ".config/github-copilot/sessions",
]


def _find_sessions_dir() -> Optional[Path]:
    for d in CANDIDATE_DIRS:
        if d.is_dir():
            return d
    return None


@register
class GitHubCopilot(BaseProvider):
    name = "github_copilot"
    display_name = "GitHub Copilot CLI"

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

            sid = data.get("id") or f.stem
            title = data.get("title") or data.get("summary", "") or ""
            ts = data.get("created_at") or int(f.stat().st_mtime * 1000)

            total_in = 0
            total_out = 0
            steps = 0
            model = ""

            messages = data.get("messages", [])
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                usage = msg.get("usage") or {}
                if usage:
                    total_in += usage.get("input_tokens", 0) or 0
                    total_out += usage.get("output_tokens", 0) or 0
                else:
                    if role == "assistant":
                        total_out += len(str(content)) // 4
                    elif role == "user":
                        total_in += len(str(content)) // 4
                if role == "assistant":
                    steps += 1
                    if not model and msg.get("model"):
                        model = msg["model"]

            sessions.append(Session(
                id=sid,
                title=title[:80],
                provider=cls.name,
                input_tokens=total_in,
                output_tokens=total_out,
                steps=steps,
                model=model,
                time_created=ts if isinstance(ts, int) else int(ts),
            ))
        return sessions

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        sdir = _find_sessions_dir()
        if not sdir:
            return []

        for f in sdir.glob("*.json"):
            if f.stem == session_id:
                return cls._extract_messages(f)

        for f in sdir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("id") == session_id:
                    return cls._extract_messages(f)
            except (json.JSONDecodeError, OSError):
                continue
        return []

    @classmethod
    def _extract_messages(cls, filepath: Path) -> list[Message]:
        try:
            data = json.loads(filepath.read_text())
        except (json.JSONDecodeError, OSError):
            return []

        messages = []
        for msg in data.get("messages", []):
            if msg.get("role") != "assistant":
                continue
            usage = msg.get("usage") or {}
            messages.append(Message(
                session_id=data.get("id", filepath.stem),
                role="assistant",
                input_tokens=usage.get("input_tokens", 0) or 0,
                output_tokens=usage.get("output_tokens", 0) or 0,
                cache_read=usage.get("cache_read_input_tokens", 0) or 0,
                cache_write=usage.get("cache_creation_input_tokens", 0) or 0,
                finish_reason=msg.get("finish_reason", "") or "",
            ))
        return messages
