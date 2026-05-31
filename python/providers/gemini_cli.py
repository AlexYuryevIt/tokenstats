"""
Gemini CLI provider — parses conversation data from Google's Gemini CLI.

Data location:
  ~/.local/share/google-gemini/sessions/*.json
  ~/.config/google-gemini/sessions/*.json
"""
import json
from pathlib import Path
from typing import Optional

from models import Session, Message
from .base import BaseProvider, register


CANDIDATE_DIRS = [
    Path.home() / ".local/share/google-gemini/sessions",
    Path.home() / ".config/google-gemini/sessions",
]


def _find_sessions_dir() -> Optional[Path]:
    for d in CANDIDATE_DIRS:
        if d.is_dir():
            return d
    return None


@register
class GeminiCLI(BaseProvider):
    name = "gemini_cli"
    display_name = "Gemini CLI"

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
            title = data.get("title") or data.get("name", "") or ""
            ts = data.get("create_time") or data.get("created_at") or int(f.stat().st_mtime * 1000)

            total_in = 0
            total_out = 0
            total_reasoning = 0
            steps = 0
            model = data.get("model", "")

            messages = data.get("messages", data.get("turns", []))
            for msg in messages:
                role = msg.get("role", "")
                usage = msg.get("usage_metadata") or msg.get("usage") or {}
                if usage:
                    total_in += usage.get("prompt_token_count", usage.get("input_tokens", 0)) or 0
                    total_out += usage.get("candidates_token_count", usage.get("output_tokens", 0)) or 0
                    total_reasoning += usage.get("reasoning_token_count", 0) or 0
                else:
                    content = msg.get("content") or msg.get("text") or msg.get("parts", [])
                    text = ""
                    if isinstance(content, list):
                        for p in content:
                            if isinstance(p, dict):
                                text += p.get("text", "")
                            elif isinstance(p, str):
                                text += p
                    else:
                        text = str(content)
                    if role == "assistant" or role == "model":
                        total_out += len(text) // 4
                    elif role == "user":
                        total_in += len(text) // 4

                if role == "assistant" or role == "model":
                    steps += 1

            sessions.append(Session(
                id=sid,
                title=title[:80],
                provider=cls.name,
                project="",
                input_tokens=total_in,
                output_tokens=total_out,
                reasoning_tokens=total_reasoning,
                cache_read=0,
                cache_write=0,
                cost=0,
                steps=steps,
                model=model,
                time_created=ts if isinstance(ts, int) else int(ts or 0),
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
        for msg in data.get("messages", data.get("turns", [])):
            if msg.get("role") not in ("assistant", "model"):
                continue
            usage = msg.get("usage_metadata") or msg.get("usage") or {}
            finish_reason = msg.get("finish_reason", "") or ""
            timestamp = msg.get("timestamp") or 0
            messages.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=usage.get("prompt_token_count", usage.get("input_tokens", 0)) or 0,
                output_tokens=usage.get("candidates_token_count", usage.get("output_tokens", 0)) or 0,
                reasoning_tokens=usage.get("reasoning_token_count", 0) or 0,
                cache_read=0,
                cache_write=0,
                cost=0,
                finish_reason=finish_reason,
                time_created=int(timestamp) if isinstance(timestamp, (int, float)) else None,
            ))
        return messages
