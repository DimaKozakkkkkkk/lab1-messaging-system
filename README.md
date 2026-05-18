# 🧪 Lab 2 — Messenger Prototype

**Variant 3 — Offline Message Delivery**  
**Course:** Software Design and Documentation

---

## 📋 Description

A working prototype of a messenger that **guarantees message delivery even when the recipient is offline**.

Key features:
- Messages are **persisted to SQLite** — never lost after restart
- An **in-memory queue** (simulating RabbitMQ) buffers messages for offline users
- A **background delivery worker** retries delivery with exponential backoff
- When a user **comes back online**, pending messages are auto-delivered
- Clients can also manually **ACK** any message

This implements the architecture designed in Lab 1 (Variant 3).

---

## 🗂️ Project Structure

```
messenger/
├── main.py                     # App entry point
├── requirements.txt
├── postman_collection.json     # Postman API collection
│
├── models/
│   └── models.py               # User, Conversation, Message dataclasses
│
├── services/
│   ├── user_service.py         # User CRUD logic
│   ├── conversation_service.py # Conversation logic
│   └── message_service.py      # Send, queue, deliver, retry logic
│
├── storage/
│   └── database.py             # SQLite init and connection
│
├── api/
│   └── routes.py               # Flask route handlers
│
└── tests/
    └── test_integration.py     # Integration tests (unittest)
```

---

## ▶️ How to Run

### 1. Install dependencies

```bash
pip install flask
```

### 2. Start the server

```bash
cd messenger
python main.py
```

Server starts at `http://localhost:8000`

### 3. Run tests

```bash
cd messenger
python tests/test_integration.py
```

Expected output: **13 tests, all OK**

---

## 📡 API Endpoints

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/users` | Create a user `{"name": "Alice"}` |
| `GET` | `/users` | List all users |
| `GET` | `/users/{id}` | Get user by ID |
| `POST` | `/users/{id}/status` | Set online/offline `{"online": true}` |
| `GET` | `/users/{id}/pending` | Get undelivered messages for user |

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/conversations` | Create conversation `{"member_ids": ["id1","id2"]}` |
| `GET` | `/conversations/{id}` | Get conversation info |
| `GET` | `/conversations/{id}/messages` | Get message history |

### Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/messages` | Send a message |
| `POST` | `/messages/{id}/ack` | Acknowledge (mark as delivered) |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

---

## 🔁 Offline Delivery Flow

```
Alice sends message
       │
       ▼
  Saved to DB (status: sent)
       │
       ▼
  Enqueued in memory queue
       │
       ▼
  DeliveryWorker checks if Bob is online
       │
  Bob offline ──► Retry with exponential backoff (2s, 4s, 8s, 16s, 30s)
       │
  Bob online  ──► status = 'delivered'
       │
  Bob reconnects ──► GET /users/{id}/pending auto-delivers all pending
```

---

## 🧪 Postman Testing

1. Import `postman_collection.json` into Postman
2. Start the server (`python main.py`)
3. Run the collection **in order** (requests 1–9)
4. The collection uses variables — IDs are saved automatically

---

## 🛡️ Error Handling

| Situation | HTTP Code |
|-----------|-----------|
| Empty message text | `400 Bad Request` |
| User does not exist | `404 Not Found` |
| Invalid conversation | `404 Not Found` |
| Non-member sends message | `400 Bad Request` |
| Duplicate user name | `409 Conflict` |

---

## 🗄️ Data Model

```
User          Conversation       Message
────          ────────────       ───────
id (uuid)     id (uuid)          id (uuid)
name          type               conversation_id
              created_at         sender_id
                                 text
                                 status: sent|delivered|queued
                                 created_at
```

---

## 💬 Defense Questions — Answers

**1. How does your system ensure that messages are not lost?**  
Messages are immediately written to SQLite before any delivery attempt. Even if the server restarts, all messages remain in the DB.

**2. What happens if the recipient is offline?**  
The message stays in the queue and the delivery worker retries with exponential backoff (up to 5 times). When the user comes back online, `GET /users/{id}/pending` retrieves all undelivered messages.

**3. How are messages uniquely identified?**  
Every message gets a UUID4 `id`, plus `sender_id` and `created_at` timestamp.

**4. What errors may occur when sending a message?**  
Empty text (400), unknown conversation (404), unknown sender (404), sender not in conversation (400).

**5. How would your system change to support 1 million users?**  
Replace the in-memory queue with a real message broker (RabbitMQ / Kafka), replace SQLite with PostgreSQL, add horizontal scaling for the delivery workers, and use Redis for the online-user registry.
