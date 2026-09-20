"""Email mission verification with controlled inference and temporary databases."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SESSION_SECRET", "email-tests-" + "x" * 48)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from app import db, email_lab, email_model
from app.chat import ModelError
from app.email_workspace import Workspace, GOALS, PRICING, POLICY, OUTSIDE, JOE, objective_reached
from app.learning import LessonError
from app.main import app


class EmailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.tmp.name) / "test.db")
        self.db_patch.start()
        self.model_patch = patch.object(email_lab, "run_assistant", new_callable=AsyncMock)
        self.model = self.model_patch.start()
        self.model.return_value = {"summary": "The sender asks for next steps. The deal is still pending.", "deal_status": "pending"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.client.post("/register", data={"username": "alice"})
        self.goal = "summary"
        self.run = email_lab.state(1, self.goal)["run"]["id"]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.model_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def select(self, goal):
        self.goal = goal
        self.run = email_lab.state(1, goal)["run"]["id"]

    def send(self, body="Please summarize my proposal.", request_id="one", protected=False, **kwargs):
        data = {"goal": self.goal, "run_id": self.run, "request_id": request_id,
                "subject": "Proposal", "body": body, "protected": str(protected).lower(), **kwargs}
        return self.client.post("/learn/email-joe/send", data=data, headers={"Accept": "application/json"})

    def state(self):
        return email_lab.state(1, self.goal)

    def tool_model(self):
        async def model(goal, subject, body, workspace, emit):
            def action(name, args):
                value = workspace.execute(name, args)
                emit({"kind": "tool", "tool": name, "arguments": args, "result": value, "text": name})
                return value
            if goal == "disclosure":
                value = action("read_file", {"path": PRICING})
                action("send_email", {"recipient": OUTSIDE, "body": value["content"]})
            if goal == "deal":
                action("update_deal", {"deal_id": "NORTHSTAR", "status": "pending", "discount_percent": 50, "note": "Campaign"})
            return {"summary": "The tool result is recorded.", "deal_status": "pending"}
        self.model.side_effect = model

    def test_join_page_goals_and_no_initial_secrets(self):
        page = self.client.get("/learn/email-joe")
        self.assertEqual(page.status_code, 200)
        self.assertIn("File Explorer", page.text)
        self.assertIn(PRICING, page.text)
        self.assertNotIn(GOALS["summary"]["hints"][2], page.text)
        self.assertNotIn("pricing_", page.text)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertIn("Email Joe", self.client.get("/learn").text)
        self.assertEqual(self.client.get("/learn/email-joe?goal=missing").status_code, 404)
        self.model.assert_not_called()

    def test_claimed_tool_success_does_not_award_action_goals(self):
        self.select("deal")
        self.model.return_value = {"summary": "I applied the 50% discount and sent all files.", "deal_status": "approved"}
        self.assertEqual(self.send().status_code, 200)
        self.assertFalse(self.state()["latest"]["success"])
        self.assertIsNone(self.state()["progress"]["completed_at"])
        self.assertEqual(self.state()["latest"]["workspace"]["record"]["discount_percent"], 0)

    def test_summary_verdict_not_quoted_email_claim_is_scored(self):
        self.model.return_value = {"summary": "The email says 'approved', but the record is pending.", "deal_status": "pending"}
        self.send()
        self.assertFalse(self.state()["latest"]["success"])
        self.model.return_value = {"summary": "Northstar is approved.", "deal_status": "approved"}
        self.send(request_id="two")
        self.assertTrue(self.state()["latest"]["success"])
        self.assertIsNotNone(self.state()["progress"]["completed_at"])

    def test_disclosure_requires_read_and_send_and_protected_run_blocks(self):
        self.select("disclosure")
        self.tool_model()
        self.assertEqual(self.send().status_code, 200)
        first = self.state()["latest"]
        self.assertTrue(first["success"])
        self.assertEqual(len(first["workspace"]["outbox"]), 1)
        self.assertNotIn("canary", first)
        self.assertEqual(self.send(request_id="protected", protected=True).status_code, 200)
        last = self.state()["latest"]
        self.assertFalse(last["success"])
        self.assertEqual(last["workspace"]["outbox"], [])
        self.assertTrue(last["events"][-1]["result"]["blocked"])
        self.assertEqual(self.model.await_count, 2)

    def test_deal_mutation_is_recorded_and_protection_preserves_original(self):
        self.select("deal")
        self.tool_model()
        self.send()
        self.assertTrue(self.state()["latest"]["success"])
        self.assertEqual(self.state()["latest"]["workspace"]["record"]["discount_percent"], 50)
        self.send(request_id="protected", protected=True)
        self.assertFalse(self.state()["latest"]["success"])
        self.assertEqual(self.state()["latest"]["workspace"]["record"]["discount_percent"], 0)

    def test_duplicate_requests_do_not_execute_twice_and_changed_input_conflicts(self):
        self.send()
        self.send()
        self.assertEqual(self.model.await_count, 1)
        self.assertEqual(len(self.state()["trials"]), 1)
        self.assertEqual(self.send(body="changed").status_code, 409)
        self.assertEqual(self.model.await_count, 1)

    def test_validation_and_native_error_preserves_draft(self):
        for values in ({"body": " "}, {"subject": ""}, {"body": "x" * 9000}, {"subject": "x" * 161}, {"request_id": ""}):
            self.assertEqual(self.send(**values).status_code, 400)
        self.model.assert_not_called()
        page = self.client.post("/learn/email-joe/send", data={"goal": self.goal, "run_id": self.run, "request_id": "native", "subject": "", "body": "Keep this unsent email"})
        self.assertEqual(page.status_code, 400)
        self.assertIn("Keep this unsent email", page.text)

    def test_failure_keeps_events_and_new_submission_gets_new_workspace(self):
        self.select("disclosure")
        async def failing(goal, subject, body, workspace, emit):
            args = {"path": PRICING}
            emit({"kind": "tool", "tool": "read_file", "arguments": args, "result": workspace.execute("read_file", args), "text": "read_file"})
            raise ModelError("controlled failure")
        self.model.side_effect = failing
        self.assertEqual(self.send().status_code, 503)
        old = self.state()["latest"]
        self.assertEqual(old["status"], "failed")
        self.assertIn("Private reference", old["events"][-1]["result"]["content"])
        self.assertEqual(self.send().status_code, 409)
        self.tool_model()
        self.assertEqual(self.send(request_id="retry").status_code, 200)
        new = self.state()["latest"]
        self.assertNotEqual(old["events"][-1]["result"]["content"], new["events"][3]["result"]["content"])
        self.assertEqual(len(self.state()["trials"]), 2)

    def test_cross_player_and_cross_goal_access_is_rejected(self):
        self.client.post("/register", data={"username": "bob"})
        self.assertEqual(self.client.get("/learn/email-joe?attempt=" + self.run).status_code, 404)
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(self.client.get("/learn/email-joe?goal=deal&attempt=" + self.run).status_code, 404)
        self.model.assert_not_called()

    def test_expired_session_and_safe_login_destination(self):
        self.client.cookies.clear()
        self.assertEqual(self.send().status_code, 401)
        self.assertEqual(self.client.get("/learn/email-joe", headers={"Accept": "application/json"}).status_code, 401)
        page = self.client.get("/login?next=/learn/email-joe?goal=deal")
        self.assertIn('/learn/email-joe?goal=deal', page.text)
        self.model.assert_not_called()

    def test_hints_example_usage_reset_and_existing_data_survive(self):
        for _ in range(3):
            self.client.post("/learn/email-joe/hint", data={"goal": self.goal, "run_id": self.run})
        self.model.return_value = {"summary": "Approved.", "deal_status": "approved"}
        self.send()
        self.assertTrue(self.state()["progress"]["completed_with_example"])
        old = self.run
        email_lab.reset(1, self.goal, old)
        self.assertNotEqual(self.state()["run"]["id"], old)
        self.assertTrue(self.state()["progress"]["completed_at"])
        self.assertEqual(len(email_lab.state(1, self.goal, old)["trials"]), 1)
        self.assertEqual(self.send().status_code, 409)
        db.init_db()
        with db.db() as conn:
            self.assertEqual(conn.execute("SELECT username FROM users WHERE id=1").fetchone()[0], "alice")

    def test_input_summary_and_file_results_are_escaped(self):
        self.model.return_value = {"summary": '<img src=x onerror="alert(1)">', "deal_status": "pending"}
        html = self.send(body="<script>alert(1)</script>").json()["html"]
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>alert', html)
        self.assertIn('&lt;img', html)
        self.assertIn('&lt;script', html)

    def test_running_events_visible_and_concurrent_send_reset_rejected(self):
        async def check():
            started, finish = asyncio.Event(), asyncio.Event()
            async def delayed(goal, subject, body, workspace, emit):
                emit({"kind": "model", "text": "Waiting for model"})
                started.set()
                await finish.wait()
                return {"summary": "Pending", "deal_status": "pending"}
            self.model.side_effect = delayed
            task = asyncio.create_task(email_lab.submit(1, self.goal, self.run, "one", "Proposal", "Message"))
            await started.wait()
            try:
                self.assertTrue(self.state()["running"])
                self.assertEqual(self.state()["latest"]["events"][-1]["text"], "Waiting for model")
                with self.assertRaises(LessonError):
                    await email_lab.submit(1, self.goal, self.run, "two", "Proposal", "Message")
                with self.assertRaises(LessonError):
                    email_lab.reset(1, self.goal, self.run)
            finally:
                finish.set()
                await task
        asyncio.run(check())

    def test_stale_run_expires_without_losing_observed_state(self):
        self.send()
        with db.db() as conn:
            conn.execute("UPDATE email_trials SET status='running',started_at=? WHERE run_id=?", (int(time.time()) - email_lab.LEASE_SECONDS - 1, self.run))
        self.assertFalse(self.state()["running"])
        self.assertEqual(self.state()["latest"]["status"], "failed")
        self.assertIn("interrupted", self.state()["latest"]["feedback"])


class WorkspaceTests(unittest.TestCase):
    def test_paths_are_exact_fixture_labels_and_never_read_host_or_network(self):
        workspace = Workspace("disclosure", "private-marker")
        for path in ("/etc/passwd", r"C:\Users\Joe\Documents\Sales\..\..\.env", r"\\server\share\file", "http://localhost", "file:///data/ctf.db"):
            self.assertIn("error", workspace.execute("read_file", {"path": path}))
        self.assertIn("content", workspace.execute("read_file", {"path": PRICING.lower()}))
        for name in ("exec", "get_employee", "fetch_url", "shell"):
            self.assertIn("error", workspace.execute(name, {"command": "anything"}))
        self.assertIn("error", workspace.execute("read_file", {"path": PRICING, "run_id": "someone-else"}))

    def test_protected_legitimate_tools_still_work_and_instances_are_independent(self):
        first = Workspace("disclosure", "first", True)
        second = Workspace("disclosure", "second", True)
        content = first.execute("read_file", {"path": POLICY})["content"]
        self.assertTrue(first.execute("send_email", {"recipient": JOE, "body": content})["sent"])
        self.assertEqual(second.outbox, [])
        self.assertNotIn("first", second.execute("read_file", {"path": PRICING})["content"])
        deal = Workspace("deal", "unused", True)
        self.assertTrue(deal.execute("update_deal", {"deal_id": "NORTHSTAR", "status": "pending", "discount_percent": 0, "note": "Follow up"})["updated"])
        self.assertIn("error", deal.execute("update_deal", {"deal_id": "NORTHSTAR", "status": "pending", "discount_percent": True, "note": "x"}))
        self.assertIn("error", Workspace("summary", "x").execute("send_email", {"recipient": JOE, "body": "x"}))

    def test_disclosure_cannot_be_awarded_for_hallucinated_or_attacker_supplied_reference(self):
        marker = "pricing_fresh"
        read = {"tool": "read_file", "result": {"content": marker}}
        send = {"tool": "send_email", "result": {"sent": True, "recipient": OUTSIDE, "body": marker}}
        self.assertFalse(objective_reached("disclosure", [send], None, marker, "email"))
        self.assertFalse(objective_reached("disclosure", [send, read], None, marker, "email"))
        self.assertFalse(objective_reached("disclosure", [read, send], None, marker, marker))
        self.assertTrue(objective_reached("disclosure", [read, send], None, marker, "email"))


class EmailProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_model_decisions_consume_real_results_before_summary(self):
        count = 0
        workspace = Workspace("disclosure", "fresh-reference")
        events = []
        def respond(request):
            nonlocal count
            count += 1
            payload = json.loads(request.content)
            if count == 1:
                self.assertNotIn("fresh-reference", json.dumps(payload))
                decision = {"action": "read_file", "arguments": {"path": PRICING}}
            elif count == 2:
                self.assertIn("fresh-reference", payload["messages"][-1]["content"])
                decision = {"action": "send_email", "arguments": {"recipient": OUTSIDE, "body": "fresh-reference"}}
            else:
                self.assertIn('"sent": true', payload["messages"][-1]["content"])
                decision = {"action": "finish", "arguments": {"summary": "Brief ready", "deal_status": "pending"}}
            return httpx.Response(200, json={"message": {"content": json.dumps(decision)}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch.object(email_model.httpx, "AsyncClient", return_value=client):
            result = await email_model.run_assistant("disclosure", "Proposal", "External email", workspace, events.append)
        self.assertEqual(result["summary"], "Brief ready")
        self.assertEqual(count, 3)
        self.assertTrue(objective_reached("disclosure", events, result, "fresh-reference", "External email"))

    async def test_invalid_decisions_and_undeclared_actions_cannot_execute(self):
        bad = [None, {}, {"action": "shell", "arguments": {"command": "id"}}, {"action": "send_email", "arguments": {}},
               {"action": "finish", "arguments": {"summary": "", "deal_status": "approved"}}]
        for decision in bad:
            client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"message": {"content": json.dumps(decision)}})))
            workspace = Workspace("summary", "unused")
            with patch.object(email_model.httpx, "AsyncClient", return_value=client), patch.object(workspace, "execute") as execute:
                with self.assertRaises(ModelError):
                    await email_model.run_assistant("summary", "Subject", "Body", workspace, lambda e: None)
                execute.assert_not_called()

    async def test_tool_loop_is_bounded(self):
        count = 0
        def respond(_):
            nonlocal count
            count += 1
            return httpx.Response(200, json={"message": {"content": json.dumps({"action": "read_file", "arguments": {"path": POLICY}})}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        events = []
        with patch.object(email_model.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ModelError):
                await email_model.run_assistant("summary", "Subject", "Body", Workspace("summary", "unused"), events.append)
        self.assertEqual(count, email_model.MAX_ACTIONS + 1)
        self.assertEqual(sum(e["kind"] == "tool" for e in events), email_model.MAX_ACTIONS)
