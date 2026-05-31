"""
Cline provider — parses per-task JSON conversation files.

Data locations:
  ~/.cline/data/tasks/<taskId>/api_conversation_history.json  (transcripts)
  ~/.cline/data/taskHistory.json                              (task index)
"""
import json
from pathlib import Path
from models import Session, Message
from .base import BaseProvider, register


CLINE_DATA = Path.home() / ".cline/data"


@register
class Cline(BaseProvider):
    name = "cline"
    display_name = "Cline"

    @classmethod
    def detect(cls) -> bool:
        task_history = CLINE_DATA / "taskHistory.json"
        return task_history.is_file()

    @classmethod
    def _task_history(cls) -> list[dict]:
        path = CLINE_DATA / "taskHistory.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("tasks", data.get("history", []))
        except (json.JSONDecodeError, OSError):
            pass
        return []

    @classmethod
    def list_sessions(cls) -> list[Session]:
        sessions = []
        for task in cls._task_history():
            task_id = task.get("id", "")
            if not task_id:
                continue
            title = task.get("title") or task.get("task") or ""
            ts = task.get("ts") or task.get("timestamp") or task.get("time_created") or 0

            transcript = cls._load_transcript(task_id)
            total_in = 0
            total_out = 0
            steps = 0
            model = ""

            for msg in transcript:
                if msg.get("role") == "assistant":
                    usage = msg.get("usage", {})
                    total_in += usage.get("input_tokens", 0) or 0
                    total_out += usage.get("output_tokens", 0) or 0
                    if not model and msg.get("model"):
                        model = msg["model"]
                    steps += 1

            sessions.append(Session(
                id=task_id,
                title=title,
                provider=cls.name,
                project="",
                input_tokens=total_in,
                output_tokens=total_out,
                reasoning_tokens=0,
                cache_read=0,
                cache_write=0,
                cost=0,
                steps=steps,
                model=model,
                time_created=ts if isinstance(ts, int) else int(ts or 0),
            ))
        return sessions

    @classmethod
    def _load_transcript(cls, task_id: str) -> list[dict]:
        """Load conversation transcript from JSON file."""
        path = CLINE_DATA / "tasks" / task_id / "api_conversation_history.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text())
            # Normalize list vs dict structure
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("conversations", data.get("messages", data.get("history", [])))
        except (json.JSONDecodeError, OSError):
            pass
        return []

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        transcript = cls._load_transcript(session_id)
        messages = []
        for msg in transcript:
            if msg.get("role") != "assistant":
                continue
            usage = msg.get("usage", {})
            messages.append(Message(
                session_id=session_id,
                role="assistant",
                input_tokens=usage.get("input_tokens", 0) or 0,
                output_tokens=usage.get("output_tokens", 0) or 0,
                cache_read=usage.get("cache_read_input_tokens", 0) or 0,
                cache_write=usage.get("cache_creation_input_tokens", 0) or 0,
                finish_reason=msg.get("stop_reason", "") or "",
            ))
        return messages
