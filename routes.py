from flask import Blueprint, request, jsonify
from services.user_service import (
    create_user, get_user, list_users,
    UserNotFoundError, UserAlreadyExistsError
)
from services.conversation_service import (
    create_conversation, get_conversation, ConversationNotFoundError
)
from services.message_service import (
    send_message, get_messages, acknowledge_message,
    get_pending_messages, set_user_online, set_user_offline, get_online_users
)

bp = Blueprint("api", __name__)


def err(msg, code):
    return jsonify({"error": msg}), code


# ── Health ────────────────────────────────────────────────────────────────────

@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


# ── Users ─────────────────────────────────────────────────────────────────────

@bp.post("/users")
def api_create_user():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(create_user(data.get("name", ""))), 201
    except UserAlreadyExistsError as e:
        return err(str(e), 409)
    except ValueError as e:
        return err(str(e), 400)


@bp.get("/users")
def api_list_users():
    return jsonify(list_users())


@bp.get("/users/<user_id>")
def api_get_user(user_id):
    try:
        return jsonify(get_user(user_id))
    except UserNotFoundError as e:
        return err(str(e), 404)


# ── Online status (Variant 3) ─────────────────────────────────────────────────

@bp.post("/users/<user_id>/status")
def api_set_status(user_id):
    try:
        get_user(user_id)
    except UserNotFoundError as e:
        return err(str(e), 404)

    data = request.get_json(silent=True) or {}
    online = data.get("online", True)

    if online:
        set_user_online(user_id)
        pending = get_pending_messages(user_id)
        for m in pending:
            acknowledge_message(m["id"])
        return jsonify({"user_id": user_id, "online": True,
                        "delivered_on_reconnect": len(pending)})
    else:
        set_user_offline(user_id)
        return jsonify({"user_id": user_id, "online": False})


@bp.get("/users/online/list")
def api_online_list():
    return jsonify({"online_users": get_online_users()})


@bp.get("/users/<user_id>/pending")
def api_pending(user_id):
    try:
        return jsonify(get_pending_messages(user_id))
    except UserNotFoundError as e:
        return err(str(e), 404)


# ── Conversations ─────────────────────────────────────────────────────────────

@bp.post("/conversations")
def api_create_conversation():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(create_conversation(
            data.get("member_ids", []),
            data.get("type", "direct")
        )), 201
    except UserNotFoundError as e:
        return err(str(e), 404)
    except ValueError as e:
        return err(str(e), 400)


@bp.get("/conversations/<conv_id>")
def api_get_conversation(conv_id):
    try:
        return jsonify(get_conversation(conv_id))
    except ConversationNotFoundError as e:
        return err(str(e), 404)


# ── Messages ──────────────────────────────────────────────────────────────────

@bp.post("/messages")
def api_send_message():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(send_message(
            data.get("conversation_id", ""),
            data.get("sender_id", ""),
            data.get("text", "")
        )), 201
    except (UserNotFoundError, ConversationNotFoundError) as e:
        return err(str(e), 404)
    except ValueError as e:
        return err(str(e), 400)


@bp.get("/conversations/<conv_id>/messages")
def api_get_messages(conv_id):
    try:
        limit = int(request.args.get("limit", 50))
        return jsonify(get_messages(conv_id, limit))
    except ConversationNotFoundError as e:
        return err(str(e), 404)


@bp.post("/messages/<message_id>/ack")
def api_ack(message_id):
    try:
        return jsonify(acknowledge_message(message_id))
    except ValueError as e:
        return err(str(e), 404)
