"""
PI Agent provider — parses session data from Pezzo's PI Agent.

Data location:
  ~/.pi/sessions/*.json
"""
import json
from pathlib import Path
from models import Session, Message
from .base import BaseProvider, register


SESSION_DIR = Path.home() / ".pi/sessions"


def pi_cost_to_internal(cost):
    if not isinstance(cost, (int, float)):
        return 0
    if isinstance(cost, float):
        return round(cost * 100_000_000)
    return cost


@register
class PIAgent(BaseProvider):
    name = "pi_agent"
    display_name = "PI Agent"

    @classmethod
    def detect(cls) -> bool:
        return SESSION_DIR.is_dir()

    @classmethod
    def list_sessions(cls) -> list[Session]:
        if not SESSION_DIR.is_dir():
            return []

        sessions = []
        for f in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            sid = data.get("session_id") or data.get("id") or f.stem
            title = data.get("title") or data.get("summary", "") or ""
            ts = data.get("created_at") or int(f.stat().st_mtime * 1000)

            total_in = 0
            total_out = 0
            total_cost = 0
            steps = 0
            model = data.get("model", "")

            messages = data.get("messages", data.get("history", []))
            for msg in messages:
                role = msg.get("role", "")
                usage = msg.get("usage") or msg.get("token_usage") or {}
                total_in += usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
                total_out += usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
                total_cost += usage.get("cost", 0) or 0
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
                cost=pi_cost_to_internal(total_cost),
                steps=steps,
                model=model if isinstance(model, str) else "",
                time_created=int(ts) if isinstance(ts, int) else int(ts or 0),
            ))
        return sessions

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        if not SESSION_DIR.is_dir():
            return []

        for f in SESSION_DIR.glob("*.json"):
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
        for msg in data.get("messages", data.get("history", [])):
            if msg.get("role") != "assistant":
                continue
            usage = msg.get("usage") or msg.get("token_usage") or {}
            step_cost = pi_cost_to_internal(usage.get("cost", 0) or 0)
            finish_reason = msg.get("finish_reason", "") or ""
            timestamp = msg.get("timestamp") or 0
            messages.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0,
                output_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0,
                reasoning_tokens=usage.get("reasoning_tokens", 0) or 0,
                cache_read=0,
                cache_write=0,
                cost=step_cost,
                finish_reason=finish_reason,
                time_created=int(timestamp) if isinstance(timestamp, (int, float)) else None,
            ))
        return messages
