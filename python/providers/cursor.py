"""
Cursor provider — parses state.vscdb SQLite + agent-transcript JSONL files.

Data locations (macOS):
  ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb  (main KV store)
  ~/.cursor/projects/<project-id>/agent-transcripts/*.jsonl            (agent transcripts)

Linux:
  ~/.config/Cursor/User/globalStorage/state.vscdb
"""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from models import Session, Message
from .base import BaseProvider, register


CURSOR_DB_CANDIDATES = [
    Path.home() / "Library/Application Support/Cursor/User/globalStorage/state.vscdb",
    Path.home() / ".config/Cursor/User/globalStorage/state.vscdb",
]

CURSOR_AGENT_DIR = Path.home() / ".cursor/projects"


def _find_db() -> Optional[str]:
    for p in CURSOR_DB_CANDIDATES:
        if p.exists() and p.stat().st_size > 0:
            return str(p)
    return None


def _connect(path: str):
    db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    return db


@register
class Cursor(BaseProvider):
    name = "cursor"
    display_name = "Cursor"

    _db_path: Optional[str] = None

    @classmethod
    def detect(cls) -> bool:
        cls._db_path = _find_db()
        return cls._db_path is not None

    @classmethod
    def list_sessions(cls) -> list[Session]:
        sessions: dict[str, Session] = {}

        # Parse from state.vscdb (composerData + bubbleId)
        if cls._db_path:
            try:
                db = _connect(cls._db_path)
                cur = db.execute(
                    "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
                )
                for row in cur.fetchall():
                    try:
                        val = json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
                        # Try bytes
                        if isinstance(row["value"], bytes):
                            val = json.loads(row["value"].decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                    composer_id = row["key"].split(":", 1)[1] if ":" in row["key"] else row["key"]
                    title = cls._composer_title(val)
                    ts = cls._composer_timestamp(val)

                    # Sum bubble tokens
                    bubble_ids = cls._collect_bubble_ids(val)
                    total_in = 0
                    total_out = 0
                    steps = 0
                    for bid in bubble_ids:
                        bubble = cls._get_bubble(db, composer_id, bid)
                        if bubble:
                            tc = bubble.get("tokenCount", {})
                            total_in += tc.get("inputTokens", 0) or 0
                            total_out += tc.get("outputTokens", 0) or 0
                            steps += 1

                    sessions[composer_id] = Session(
                        id=composer_id,
                        title=title,
                        provider=cls.name,
                        input_tokens=total_in,
                        output_tokens=total_out,
                        reasoning_tokens=0,
                        cache_read=0,
                        cache_write=0,
                        cost=0,
                        steps=steps,
                        model="",
                        project="",
                        time_created=ts,
                    )
                db.close()
            except (sqlite3.Error, OSError):
                pass

        # Parse from agent-transcripts JSONL
        if CURSOR_AGENT_DIR.is_dir():
            for jsonl_file in CURSOR_AGENT_DIR.rglob("agent-transcripts/*.jsonl"):
                try:
                    sid = jsonl_file.stem
                    if sid in sessions:
                        continue  # prefer SQLite data
                    title = ""
                    total_in = 0
                    total_out = 0
                    steps = 0
                    ts = int(jsonl_file.stat().st_mtime * 1000)

                    for line in jsonl_file.read_text().splitlines():
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        if entry.get("role") == "assistant":
                            steps += 1
                            # Estimate tokens from text length
                            content = json.dumps(entry.get("content", ""))
                            total_out += len(content) // 4
                        elif entry.get("role") == "user":
                            content = entry.get("content", "")
                            if isinstance(content, str):
                                total_in += len(content) // 4
                            elif isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict):
                                        txt = block.get("text", "")
                                        total_in += len(txt) // 4

                    if steps > 0:
                        sessions[sid] = Session(
                            id=sid,
                            title=title or sid[:16],
                            provider=cls.name,
                            input_tokens=total_in,
                            output_tokens=total_out,
                            reasoning_tokens=0,
                            cache_read=0,
                            cache_write=0,
                            cost=0,
                            steps=steps,
                            model="",
                            project="",
                            time_created=ts if isinstance(ts, int) else int(ts),
                        )
                except (json.JSONDecodeError, OSError):
                    continue

        return list(sessions.values())

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        messages = []
        if cls._db_path:
            try:
                db = _connect(cls._db_path)
                bubbles = cls._get_bubbles_for_composer(db, session_id)
                db.close()
                for bid, bubble in bubbles:
                    tc = bubble.get("tokenCount", {})
                    messages.append(Message(
                        session_id=session_id,
                        role="assistant",
                        input_tokens=tc.get("inputTokens", 0) or 0,
                        output_tokens=tc.get("outputTokens", 0) or 0,
                    ))
            except (sqlite3.Error, OSError):
                pass
        return messages

    @staticmethod
    def _composer_title(val: dict) -> str:
        headers = val.get("fullConversationHeadersOnly") or val.get("conversationHeaders") or []
        if headers:
            first = headers[0]
            if isinstance(first, dict):
                return first.get("summary") or first.get("title") or ""
        return ""

    @staticmethod
    def _composer_timestamp(val: dict) -> int:
        headers = val.get("fullConversationHeadersOnly") or val.get("conversationHeaders") or []
        if headers:
            first = headers[0]
            if isinstance(first, dict):
                ts = first.get("createdAt") or first.get("timestamp") or 0
                return ts if isinstance(ts, int) else 0
        return 0

    @staticmethod
    def _collect_bubble_ids(val: dict) -> list[str]:
        ids = []
        headers = val.get("fullConversationHeadersOnly") or val.get("conversationHeaders") or []
        for h in headers:
            if isinstance(h, dict):
                bid = h.get("bubbleId") or h.get("id")
                if bid:
                    ids.append(bid)
        return ids

    @staticmethod
    def _get_bubble(db, composer_id: str, bubble_id: str) -> Optional[dict]:
        key = f"bubbleId:{composer_id}:{bubble_id}"
        cur = db.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return None
        try:
            val = row["value"]
            if isinstance(val, bytes):
                return json.loads(val.decode("utf-8"))
            if isinstance(val, str):
                return json.loads(val)
            return val
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return None

    @staticmethod
    def _get_bubbles_for_composer(db, composer_id: str) -> list[tuple[str, dict]]:
        prefix = f"bubbleId:{composer_id}:"
        cur = db.execute(
            "SELECT key, value FROM cursorDiskKV WHERE key LIKE ?", (prefix + "%",)
        )
        result = []
        for row in cur.fetchall():
            bid = row["key"].rsplit(":", 1)[1]
            val = row["value"]
            try:
                if isinstance(val, bytes):
                    val = json.loads(val.decode("utf-8"))
                elif isinstance(val, str):
                    val = json.loads(val)
                result.append((bid, val))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return result
