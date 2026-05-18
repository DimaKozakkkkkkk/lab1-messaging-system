"""
Message Service — Variant 3: Offline Message Delivery

Flow:
  1. Message saved to DB with status='sent'
  2. Added to in-memory queue (simulates RabbitMQ/SQS)
  3. Background worker polls queue every second:
     - recipient online  → status = 'delivered'
     - recipient offline → retry with exponential backoff (max 5 attempts)
  4. When user reconnects (set online), pending messages are auto-delivered
  5. Client can also manually POST /messages/{id}/ack
"""

import uuid
import time
import threading
import logging
from collections import deque
from datetime import datetime, timezone
from typing import List

from storage.database import get_connection
from services.conversation_service import get_conversation, ConversationNotFoundError
from services.user_service import get_user, UserNotFoundError

logger = logging.getLogger(__name__)

# ── Online registry & delivery queue (in-memory) ─────────────────────────────
_online_users: set = set()
_online_lock = threading.Lock()
_delivery_queue: deque = deque()
_queue_lock = threading.Lock()

MAX_RETRIES = 5
RETRY_DELAYS = [2, 4, 8, 16, 30]  # seconds (exponential backoff)


def set_user_online(user_id: str):
    with _online_lock:
        _online_users.add(user_id)


def set_user_offline(user_id: str):
    with _online_lock:
        _online_users.discard(user_id)


def is_user_online(user_id: str) -> bool:
    with _online_lock:
        return user_id in _online_users


def get_online_users() -> List[str]:
    with _online_lock:
        return list(_online_users)


def send_message(conversation_id: str, sender_id: str, text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("Message text cannot be empty")

    conv = get_conversation(conversation_id)
    get_user(sender_id)

    if sender_id not in conv["members"]:
        raise ValueError(f"User '{sender_id}' is not a member of this conversation")

    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, sender_id, text, status, created_at) "
            "VALUES (?, ?, ?, ?, 'sent', ?)",
            (msg_id, conversation_id, sender_id, text, now)
        )
        conn.commit()

    recipients = [uid for uid in conv["members"] if uid != sender_id]
    with _queue_lock:
        _delivery_queue.append({
            "message_id": msg_id,
            "recipient_ids": recipients,
            "attempts": 0,
            "next_attempt_at": time.time(),
        })

    logger.info(f"[MsgService] {msg_id} saved, queued for {recipients}")
    return {"id": msg_id, "conversation_id": conversation_id,
            "sender_id": sender_id, "text": text, "status": "sent", "created_at": now}


def get_messages(conversation_id: str, limit: int = 50) -> List[dict]:
    get_conversation(conversation_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, conversation_id, sender_id, text, status, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
            (conversation_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def acknowledge_message(message_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            raise ValueError(f"Message '{message_id}' not found")
        conn.execute("UPDATE messages SET status = 'delivered' WHERE id = ?", (message_id,))
        conn.commit()
    return {"message_id": message_id, "status": "delivered"}


def get_pending_messages(user_id: str) -> List[dict]:
    get_user(user_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT m.id, m.conversation_id, m.sender_id, m.text, m.status, m.created_at "
            "FROM messages m "
            "JOIN conversation_members cm ON cm.conversation_id = m.conversation_id "
            "WHERE cm.user_id = ? AND m.sender_id != ? AND m.status != 'delivered' "
            "ORDER BY m.created_at ASC",
            (user_id, user_id)
        ).fetchall()
    return [dict(r) for r in rows]


def _delivery_worker():
    logger.info("[DeliveryWorker] Started")
    while True:
        now = time.time()
        retry_later = []

        with _queue_lock:
            items = list(_delivery_queue)
            _delivery_queue.clear()

        for item in items:
            if item["next_attempt_at"] > now:
                retry_later.append(item)
                continue

            msg_id = item["message_id"]
            still_pending = []

            for recipient_id in item["recipient_ids"]:
                if is_user_online(recipient_id):
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE messages SET status = 'delivered' WHERE id = ?", (msg_id,)
                        )
                        conn.commit()
                    logger.info(f"[DeliveryWorker] ✓ {msg_id} → {recipient_id}")
                else:
                    still_pending.append(recipient_id)
                    logger.info(f"[DeliveryWorker] ✗ {recipient_id} offline")

            if still_pending:
                attempts = item["attempts"] + 1
                if attempts >= MAX_RETRIES:
                    logger.warning(f"[DeliveryWorker] Max retries for {msg_id}, giving up")
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE messages SET status = 'queued' WHERE id = ? AND status = 'sent'",
                            (msg_id,)
                        )
                        conn.commit()
                else:
                    delay = RETRY_DELAYS[min(attempts - 1, len(RETRY_DELAYS) - 1)]
                    retry_later.append({
                        **item,
                        "recipient_ids": still_pending,
                        "attempts": attempts,
                        "next_attempt_at": now + delay,
                    })

        with _queue_lock:
            _delivery_queue.extendleft(reversed(retry_later))

        time.sleep(1)


def start_delivery_worker():
    t = threading.Thread(target=_delivery_worker, daemon=True)
    t.start()
