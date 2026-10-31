"""Driver interface so the auto-reply engine is testable with a fake."""
from dataclasses import dataclass, field
from typing import List, Protocol

@dataclass
class ChatRef:
    key: str            # stable-ish id (title)
    name: str
    is_group: bool = False
    unread: int = 0
    last: str = ""

@dataclass
class ChatMessage:
    msg_id: str         # data-id from WhatsApp, or a hash
    sender: str
    text: str
    incoming: bool
    timestamp: str = ""
    media: str = ""     # "" | "voice" | "image" | "video" | "document" | "sticker" -> flagged for manual handling

class WhatsAppDriver(Protocol):
    def is_ready(self) -> bool: ...
    def list_unread_chats(self) -> List[ChatRef]: ...
    def open_chat(self, chat: ChatRef) -> None: ...
    def read_messages(self, limit: int = 20) -> List[ChatMessage]: ...
    def chat_phone(self) -> str: ...
    def send_text(self, text: str, typing_delay_ms: int = 60) -> None: ...
