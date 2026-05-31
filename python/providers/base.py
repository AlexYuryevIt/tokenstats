from abc import ABC, abstractmethod
from typing import Optional

from models import Session, Message

_registry: dict[str, type["BaseProvider"]] = {}


def register(provider_cls: type["BaseProvider"]):
    _registry[provider_cls.name] = provider_cls
    return provider_cls


def get_provider(name: str) -> Optional[type["BaseProvider"]]:
    return _registry.get(name)


def all_providers() -> list[type["BaseProvider"]]:
    return list(_registry.values())


def detect_providers() -> list[type["BaseProvider"]]:
    return [p for p in _registry.values() if p.detect()]


class BaseProvider(ABC):
    name: str = ""
    display_name: str = ""

    @classmethod
    @abstractmethod
    def detect(cls) -> bool: ...

    @classmethod
    @abstractmethod
    def list_sessions(cls) -> list[Session]: ...

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        for s in cls.list_sessions():
            if s.id == session_id:
                return s
        return None

    @classmethod
    @abstractmethod
    def get_messages(cls, session_id: str) -> list[Message]: ...
