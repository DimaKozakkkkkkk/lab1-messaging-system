from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    name: str


@dataclass
class Conversation:
    id: str
    type: str  # "direct" | "group"
    created_at: datetime


@dataclass
class Message:
    id: str
    conversation_id: str
    sender_id: str
    text: str
    status: str  # "sent" | "queued" | "delivered"
    created_at: datetime
