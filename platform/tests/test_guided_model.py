"""Protocol checks for model-selected, schema-validated fixture actions."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.chat import ModelError
from app.guided_model import call_guided_action
from app.workflows import persona_for, tool_result


class GuidedActionTests(unittest.IsolatedAsyncioTestCase):
    async def run_response(self, decision, executor, status=200, envelope=None):
        def respond(request):
            payload = json.loads(request.content)
            self.assertNotIn("tools", payload)  # Bypass native tool-call parsing.
            self.assertEqual(payload["options"], {"temperature": 0.2, "num_predict": 512})
            self.assertEqual(payload["format"]["required"], ["call_tool", "arguments", "reply"])
            return httpx.Response(status, json=envelope if envelope is not None else {
                "message": {"content": json.dumps(decision)}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("app.guided_model.httpx.AsyncClient", return_value=client):
            return await call_guided_action(persona_for("tool-access"), [{"role": "user", "content": "Lookup 99"}], tool_executor=executor)

    async def test_model_arguments_reach_only_declared_fixture_executor(self):
        executor = Mock(return_value='{"employee_id":99}')
        with patch("app.chat._execute_tool") as legacy:
            result = await self.run_response({"call_tool": True, "arguments": {"employee_id": 99}, "reply": "Requesting the record."}, executor)
        self.assertEqual(result, "Requesting the record.")
        executor.assert_called_once_with("lookup_employee", {"employee_id": 99})
        legacy.assert_not_called()

    async def test_refusal_and_claim_without_action_never_execute(self):
        executor = Mock()
        result = await self.run_response({"call_tool": False, "arguments": None, "reply": "I accessed employee 99."}, executor)
        self.assertEqual(result, "I accessed employee 99.")
        executor.assert_not_called()

    async def test_invalid_decisions_fail_before_execution(self):
        executor = Mock()
        for decision in (
            [], {}, {"call_tool": "true", "arguments": {}, "reply": "ok"},
            {"call_tool": True, "arguments": None, "reply": "ok"},
            {"call_tool": False, "arguments": {}, "reply": "ok"},
            {"call_tool": True, "arguments": {}, "reply": ""},
            {"call_tool": True, "arguments": {}, "reply": "ok", "tool": "fetch_url"},
        ):
            with self.subTest(decision=decision), self.assertRaises(ModelError):
                await self.run_response(decision, executor)
        executor.assert_not_called()

    async def test_service_empty_or_native_tool_response_is_not_an_action(self):
        executor = Mock()
        for envelope in ({"message": {"content": ""}}, {"message": {"content": "not json"}},
                         {"message": None}, {"message": {"content": "{}", "tool_calls": [{"function": {"name": "fetch_url"}}]}}):
            with self.subTest(envelope=envelope), self.assertRaises(ModelError):
                await self.run_response(None, executor, envelope=envelope)
        with self.assertRaises(ModelError):
            await self.run_response(None, executor, status=503)
        executor.assert_not_called()

    async def test_invalid_fixture_arguments_remain_within_boundary(self):
        results=[]
        def executor(name,args):
            result=tool_result("tool-access",name,args)
            results.append(result)
            return json.dumps(result)
        await self.run_response({"call_tool": True, "arguments": {"employee_id": "1 UNION SELECT * FROM users"}, "reply": "Requesting lookup."}, executor)
        self.assertIn("error", results[0])
