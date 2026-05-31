import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from models import Session, Message
from .base import BaseProvider, register

DB_CANDIDATES = [
    Path.home() / ".local/share/opencode/opencode.db",
    Path.home() / ".opencode/opencode.db",
    Path.home() / "Library/Application Support/opencode/opencode.db",
]


def _find_db() -> Optional[str]:
    env = os.environ.get("OPENCODE_DB")
    if env:
        p = Path(env)
        if p.exists() and p.stat().st_size > 0:
            return str(p)
    for p in DB_CANDIDATES:
        if p.exists() and p.stat().st_size > 0:
            return str(p)
    return None


def _connect(db_path: str):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


@register
class OpenCode(BaseProvider):
    name = "opencode"
    display_name = "OpenCode"

    _db_path: Optional[str] = None

    @classmethod
    def detect(cls) -> bool:
        cls._db_path = _find_db()
        return cls._db_path is not None

    @classmethod
    def list_sessions(cls) -> list[Session]:
        db = _connect(cls._db_path)
        cur = db.execute("""
            SELECT id, title, tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write, cost, time_created, model,
                   directory
            FROM session
            WHERE tokens_input > 0 OR tokens_output > 0
            ORDER BY time_created DESC
        """)
        sessions = []
        for r in cur.fetchall():
            sid = r[0]
            title = r[1] or ""
            steps = db.execute(
                "SELECT COUNT(*) FROM message WHERE session_id = ? AND data LIKE '%\"role\":\"assistant\"%'",
                (sid,),
            ).fetchone()[0]
            model_raw = r[9] or ""
            model_name = model_raw
            if isinstance(model_raw, str) and model_raw.startswith("{"):
                try:
                    m = json.loads(model_raw)
                    pid = m.get("providerID", "?")
                    mid = m.get("modelID", m.get("id", "?"))
                    model_name = f"{pid}/{mid}"
                except json.JSONDecodeError:
                    pass
            dir_raw = r[10] or ""
            project = dir_raw.rstrip("/").split("/")[-1] if dir_raw else ""

            sessions.append(Session(
                id=sid,
                title=title,
                provider=cls.name,
                project=project,
                input_tokens=r[2] or 0,
                output_tokens=r[3] or 0,
                reasoning_tokens=r[4] or 0,
                cache_read=r[5] or 0,
                cache_write=r[6] or 0,
                cost=int(r[7]) if r[7] else 0,
                steps=steps,
                model=model_name,
                time_created=r[8],
            ))
        db.close()
        return sessions

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        for s in cls.list_sessions():
            if s.id == session_id:
                return s
        return None

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        db = _connect(cls._db_path)
        msgs = db.execute(
            "SELECT data FROM message WHERE session_id = ? ORDER BY time_created",
            (session_id,),
        ).fetchall()
        assistant_msgs = [m for m in msgs if '"role":"assistant"' in m[0]]
        result = []
        for m_raw in assistant_msgs:
            d = json.loads(m_raw[0])
            t = d.get("tokens", {})
            step_cost = d.get("cost", 0) or 0
            if isinstance(step_cost, float):
                step_cost = round(step_cost * 100_000_000)
            result.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=t.get("input", 0) or 0,
                output_tokens=t.get("output", 0) or 0,
                reasoning_tokens=t.get("reasoning", 0) or 0,
                cache_read=t.get("cache", {}).get("read", 0) or 0,
                cache_write=t.get("cache", {}).get("write", 0) or 0,
                cost=step_cost,
                finish_reason=d.get("finish", ""),
                time_created=d.get("time", {}).get("created") if isinstance(d.get("time"), dict) else None,
                time_completed=d.get("time", {}).get("completed") if isinstance(d.get("time"), dict) else None,
            ))
        db.close()
        return result
