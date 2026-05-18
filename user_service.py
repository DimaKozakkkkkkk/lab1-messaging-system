import uuid
from typing import List
from storage.database import get_connection


class UserNotFoundError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


def create_user(name: str) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("User name cannot be empty")
    user_id = str(uuid.uuid4())
    try:
        with get_connection() as conn:
            conn.execute("INSERT INTO users (id, name) VALUES (?, ?)", (user_id, name))
            conn.commit()
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise UserAlreadyExistsError(f"User '{name}' already exists")
        raise
    return {"id": user_id, "name": name}


def get_user(user_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise UserNotFoundError(f"User '{user_id}' not found")
    return {"id": row["id"], "name": row["name"]}


def list_users() -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM users ORDER BY name").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]
