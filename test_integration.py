"""
Integration Tests — Variant 3: Offline Message Delivery
Uses Flask test client (no external dependencies needed).

Scenario tested:
  1. Create User A (Alice) and User B (Bob)
  2. Bob is offline
  3. Create conversation between them
  4. Alice sends a message → status = 'sent'
  5. Bob comes online → pending messages auto-delivered
  6. Message status = 'delivered'
"""

import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestMessenger(unittest.TestCase):

    def setUp(self):
        """Create a fresh temp DB and Flask test client for every test."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.environ["MESSENGER_DB"] = self.db_path

        # Re-import to pick up new DB path
        import importlib
        import storage.database as db_mod
        importlib.reload(db_mod)

        import services.user_service as u
        import services.conversation_service as c
        import services.message_service as m
        importlib.reload(u)
        importlib.reload(c)
        importlib.reload(m)
        import api.routes as r
        importlib.reload(r)

        from main import create_app
        self.app = create_app(self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def create_user(self, name):
        r = self.client.post("/users", json={"name": name})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def create_conversation(self, member_ids, conv_type="direct"):
        r = self.client.post("/conversations",
                             json={"member_ids": member_ids, "type": conv_type})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def send_message(self, conv_id, sender_id, text):
        r = self.client.post("/messages", json={
            "conversation_id": conv_id,
            "sender_id": sender_id,
            "text": text
        })
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    # ── Tests ─────────────────────────────────────────────────────────────────

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_create_user(self):
        user = self.create_user("Alice")
        self.assertEqual(user["name"], "Alice")
        self.assertIn("id", user)

    def test_duplicate_user_returns_409(self):
        self.create_user("Alice")
        r = self.client.post("/users", json={"name": "Alice"})
        self.assertEqual(r.status_code, 409)

    def test_empty_name_returns_400(self):
        r = self.client.post("/users", json={"name": "   "})
        self.assertEqual(r.status_code, 400)

    def test_unknown_user_returns_404(self):
        r = self.client.get("/users/nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_send_to_unknown_conversation_returns_404(self):
        alice = self.create_user("Alice")
        r = self.client.post("/messages", json={
            "conversation_id": "bad-id",
            "sender_id": alice["id"],
            "text": "Hello"
        })
        self.assertEqual(r.status_code, 404)

    def test_empty_message_text_returns_400(self):
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")
        conv = self.create_conversation([alice["id"], bob["id"]])
        r = self.client.post("/messages", json={
            "conversation_id": conv["id"],
            "sender_id": alice["id"],
            "text": "   "
        })
        self.assertEqual(r.status_code, 400)

    def test_non_member_cannot_send(self):
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")
        charlie = self.create_user("Charlie")
        conv = self.create_conversation([alice["id"], bob["id"]])
        r = self.client.post("/messages", json={
            "conversation_id": conv["id"],
            "sender_id": charlie["id"],
            "text": "Hello!"
        })
        self.assertEqual(r.status_code, 400)

    def test_message_has_required_fields(self):
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")
        conv = self.create_conversation([alice["id"], bob["id"]])
        msg = self.send_message(conv["id"], alice["id"], "Hi Bob!")
        self.assertIn("id", msg)
        self.assertIn("sender_id", msg)
        self.assertIn("created_at", msg)
        self.assertEqual(msg["sender_id"], alice["id"])

    def test_message_history_in_order(self):
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")
        conv = self.create_conversation([alice["id"], bob["id"]])
        self.send_message(conv["id"], alice["id"], "First")
        self.send_message(conv["id"], alice["id"], "Second")
        self.send_message(conv["id"], alice["id"], "Third")

        r = self.client.get(f"/conversations/{conv['id']}/messages")
        self.assertEqual(r.status_code, 200)
        texts = [m["text"] for m in r.get_json()]
        self.assertEqual(texts, ["First", "Second", "Third"])

    def test_manual_ack(self):
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")
        conv = self.create_conversation([alice["id"], bob["id"]])
        msg = self.send_message(conv["id"], alice["id"], "Ping")

        r = self.client.post(f"/messages/{msg['id']}/ack")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "delivered")

    def test_offline_delivery_core_flow(self):
        """
        CORE INTEGRATION TEST — Variant 3 offline delivery scenario.

        1. Alice and Bob created
        2. Bob is OFFLINE
        3. Alice sends a message → status = 'sent'
        4. Pending messages visible for Bob
        5. Bob comes ONLINE → messages auto-delivered on reconnect
        6. Message status = 'delivered'
        """
        import services.message_service as msg_svc

        # Step 1: Create users
        alice = self.create_user("Alice")
        bob = self.create_user("Bob")

        # Step 2: Bob is offline
        msg_svc.set_user_offline(bob["id"])

        # Step 3: Create conversation & Alice sends message
        conv = self.create_conversation([alice["id"], bob["id"]])
        msg = self.send_message(conv["id"], alice["id"], "Hello Bob, are you there?")

        self.assertEqual(msg["status"], "sent")
        self.assertEqual(msg["text"], "Hello Bob, are you there?")

        # Step 4: Check Bob's pending messages — should see Alice's message
        r = self.client.get(f"/users/{bob['id']}/pending")
        self.assertEqual(r.status_code, 200)
        pending = r.get_json()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], msg["id"])
        self.assertEqual(pending[0]["status"], "sent")

        # Step 5: Bob comes ONLINE → auto-delivery
        r = self.client.post(f"/users/{bob['id']}/status", json={"online": True})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["online"])
        self.assertEqual(data["delivered_on_reconnect"], 1)

        # Step 6: Verify message is now 'delivered'
        r = self.client.get(f"/conversations/{conv['id']}/messages")
        self.assertEqual(r.status_code, 200)
        messages = r.get_json()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["status"], "delivered")

    def test_list_users(self):
        self.create_user("Alice")
        self.create_user("Bob")
        r = self.client.get("/users")
        self.assertEqual(r.status_code, 200)
        names = [u["name"] for u in r.get_json()]
        self.assertIn("Alice", names)
        self.assertIn("Bob", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
