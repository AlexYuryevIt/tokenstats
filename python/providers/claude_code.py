"""
Claude Code provider — parses JSONL session transcripts.

Data locations:
  ~/.claude/projects/<project-slug>/sessions/<uuid>.jsonl  (transcripts)
"""
import json
from pathlib import Path

from models import Session, Message
from .base import BaseProvider, register


CLAUDE_DIR = Path.home() / ".claude"

TRANSCRIPT_GLOB = "projects/*/sessions/*.jsonl"


@register
class ClaudeCode(BaseProvider):
    name = "claude"
    display_name = "Claude Code"

    @classmethod
    def detect(cls) -> bool:
        projects = CLAUDE_DIR / "projects"
        return projects.is_dir() and any(projects.glob("*/sessions/*.jsonl"))

    @classmethod
    def _enumerate_sessions(cls) -> list[tuple[str, Path]]:
        """Return (session_id, filepath) for every JSONL transcript."""
        sessions = []
        projects = CLAUDE_DIR / "projects"
        if not projects.is_dir():
            return sessions
        for f in projects.rglob("*.jsonl"):
            if f.parent.name == "sessions":
                sid = f.stem
                sessions.append((sid, f))
        return sessions

    @classmethod
    def _parse_project_from_path(cls, path: Path) -> str:
        """Extract project slug from path like .../projects/<slug>/sessions/<id>.jsonl"""
        parts = path.parts
        try:
            idx = parts.index("projects")
            return parts[idx + 1]
        except (ValueError, IndexError):
            return ""

    @classmethod
    def _parse_summary(cls, filepath: Path) -> str:
        """Extract first user message as a title."""
        try:
            for line in filepath.read_text().splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("type") == "user":
                    content = entry.get("message", {}).get("content", "")
                    if content and len(content) > 10:
                        return content[:80].replace("\n", " ")
            return ""
        except (json.JSONDecodeError, OSError):
            return ""

    @classmethod
    def list_sessions(cls) -> list[Session]:
        from datetime import datetime

        result = []
        for sid, path in cls._enumerate_sessions():
            try:
                title = cls._parse_summary(path)
                mtime_ns = path.stat().st_mtime_ns
                timestamp = mtime_ns // 1_000_000  # ms

                total_in = 0
                total_out = 0
                total_cache_r = 0
                total_cache_w = 0
                steps = 0
                model = ""
                total_cost_usd = 0.0

                for line in path.read_text().splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    typ = entry.get("type")

                    if typ == "assistant":
                        msg = entry.get("message", {})
                        usage = msg.get("usage") or entry.get("usage")
                        if usage:
                            total_in += usage.get("input_tokens", 0) or 0
                            total_out += usage.get("output_tokens", 0) or 0
                            total_cache_r += usage.get("cache_read_input_tokens", 0) or 0
                            total_cache_w += usage.get("cache_creation_input_tokens", 0) or 0
                        if not model and msg.get("model"):
                            model = msg["model"]
                        steps += 1

                    elif typ == "result":
                        u = entry.get("usage", {})
                        if u:
                            total_in = u.get("input_tokens", total_in) or total_in
                            total_out = u.get("output_tokens", total_out) or total_out
                            total_cache_r = u.get("cache_read_input_tokens", total_cache_r) or total_cache_r
                            total_cache_w = u.get("cache_creation_input_tokens", total_cache_w) or total_cache_w
                        val = entry.get("total_cost_usd")
                        if val is not None:
                            total_cost_usd = val

                project = cls._parse_project_from_path(path)

                result.append(Session(
                    id=sid,
                    title=title,
                    provider=cls.name,
                    project=project,
                    input_tokens=total_in,
                    output_tokens=total_out,
                    cache_read=total_cache_r,
                    cache_write=total_cache_w,
                    cost=round(total_cost_usd * 100_000_000),
                    steps=steps,
                    model=model,
                    time_created=timestamp,
                ))

            except (json.JSONDecodeError, OSError) as e:
                continue

        return result

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        for sid, path in cls._enumerate_sessions():
            if sid == session_id:
                return cls._extract_messages(path)
        return []

    @classmethod
    def _extract_messages(cls, filepath: Path) -> list[Message]:
        from datetime import datetime

        messages = []
        for line in filepath.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            typ = entry.get("type")
            if typ != "assistant":
                continue

            msg = entry.get("message", {})
            usage = msg.get("usage") or entry.get("usage")
            ts_str = entry.get("timestamp", "")
            ts = 0
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                pass

            messages.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=(usage or {}).get("input_tokens", 0) or 0,
                output_tokens=(usage or {}).get("output_tokens", 0) or 0,
                reasoning_tokens=(usage or {}).get("reasoning_tokens", 0) or 0,
                cache_read=(usage or {}).get("cache_read_input_tokens", 0) or 0,
                cache_write=(usage or {}).get("cache_creation_input_tokens", 0) or 0,
                finish_reason=(msg.get("stop_reason") or "") if isinstance(msg, dict) else "",
                time_created=int(ts) if isinstance(ts, (int, float)) else None,
            ))
        return messages
