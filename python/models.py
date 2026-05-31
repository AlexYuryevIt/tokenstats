from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    session_id: str
    role: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: int = 0
    finish_reason: str = ""
    time_created: Optional[int] = None
    time_completed: Optional[int] = None


@dataclass
class Session:
    id: str
    title: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: int = 0
    steps: int = 0
    model: str = ""
    project: str = ""
    time_created: Optional[int] = None
    messages: list[Message] = field(default_factory=list)
