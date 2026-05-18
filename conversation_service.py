import uuid
from datetime import datetime, timezone
from typing import List
from storage.database import get_connection
from services.user_service import get_user, UserNotFoundError


class ConversationNotFoundError(Exception):
    pass


def create_conversation(member_ids: List[str], conv_type: str = "direct") -> dict:
    if len(member_ids) < 2:
        raise ValueError("A conversation requires at least 2 members")
    for uid in member_ids:
        get_user(uid)
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, type, created_at) VALUES (?, ?, ?)",
            (conv_id, conv_type, now)
        )
        conn.executemany(
            "INSERT INTO conversation_members (conversation_id, user_id) VALUES (?, ?)",
            [(conv_id, uid) for uid in member_ids]
        )
        conn.commit()
    return {"id": conv_id, "type": conv_type, "created_at": now, "members": member_ids}


def get_conversation(conv_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, type, created_at FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if not row:
            raise ConversationNotFoundError(f"Conversation '{conv_id}' not found")
        members = conn.execute(
            "SELECT user_id FROM conversation_members WHERE conversation_id = ?", (conv_id,)
        ).fetchall()
    return {
        "id": row["id"],
        "type": row["type"],
        "created_at": row["created_at"],
        "members": [m["user_id"] for m in members]
    }
