from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
FHIR_DIR = REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


@contextmanager
def patched_env(updates: dict[str, str | None]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class ProviderAssistantApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        files = sorted(FHIR_DIR.glob("*.json"))
        if not files:
            raise RuntimeError(f"No patient bundles found in {FHIR_DIR}")

        cls.patient_id = files[0].stem
        cls.client = TestClient(app)

    def _payload(self, question: str = "Any active blood thinner risk?") -> dict[str, object]:
        return {
            "patient_id": self.patient_id,
            "question": question,
            "history": [],
            "stance": "opinionated",
        }

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_assistant_chat_deterministic_mode(self) -> None:
        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "deterministic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "true",
                "ANTHROPIC_API_KEY": None,
            }
        ):
            response = self.client.post("/api/assistant/chat", json=self._payload())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["engine"], "deterministic")
        self.assertIn(body["confidence"], {"high", "medium", "low"})
        self.assertIsInstance(body["citations"], list)
        self.assertIsInstance(body["follow_ups"], list)

    def test_assistant_chat_anthropic_missing_key_falls_back(self) -> None:
        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "anthropic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "true",
                "ANTHROPIC_API_KEY": None,
            }
        ):
            with patch("api.core.provider_assistant_agent_sdk._REPO_ENV_PATH", Path("/tmp/nonexistent.env")):
                response = self.client.post("/api/assistant/chat", json=self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine"], "deterministic-fallback")

    def test_assistant_chat_anthropic_missing_key_without_fallback_returns_503(self) -> None:
        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "anthropic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "false",
                "ANTHROPIC_API_KEY": None,
            }
        ):
            with patch("api.core.provider_assistant_agent_sdk._REPO_ENV_PATH", Path("/tmp/nonexistent.env")):
                response = self.client.post("/api/assistant/chat", json=self._payload())

        self.assertEqual(response.status_code, 503)
        self.assertIn("ANTHROPIC_API_KEY", response.json().get("detail", ""))

    def test_assistant_chat_placeholder_key_is_rejected(self) -> None:
        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "anthropic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "false",
                "ANTHROPIC_API_KEY": "sk-ant-YOUR_KEY_HERE",
            }
        ):
            with patch("api.core.provider_assistant_agent_sdk._REPO_ENV_PATH", Path("/tmp/nonexistent.env")):
                response = self.client.post("/api/assistant/chat", json=self._payload())

        self.assertEqual(response.status_code, 503)
        self.assertIn("ANTHROPIC_API_KEY", response.json().get("detail", ""))

    def test_traces_list_and_detail_endpoints(self) -> None:
        # Generate at least one assistant request so traces can exist when tracing is enabled.
        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "deterministic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "true",
                "ANTHROPIC_API_KEY": None,
            }
        ):
            self.client.post("/api/assistant/chat", json=self._payload("Trace smoke test question"))

        response = self.client.get("/api/traces/")
        if response.status_code == 503:
            self.assertIn("Traces API is disabled", response.json().get("detail", ""))
            return

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tracing_enabled", body)

        if not body["tracing_enabled"]:
            self.assertIn("message", body)
            return

        self.assertIn("traces", body)
        self.assertIn("count", body)
        traces = body["traces"]
        self.assertIsInstance(traces, list)

        if traces:
            trace_id = traces[0]["trace_id"]
            detail_response = self.client.get(f"/api/traces/{trace_id}")
            self.assertEqual(detail_response.status_code, 200)
            detail = detail_response.json()
            self.assertEqual(detail.get("trace_id"), trace_id)
            self.assertIn("spans", detail)

    def test_traces_summary_endpoint(self) -> None:
        response = self.client.get("/api/traces/summary")
        if response.status_code == 503:
            self.assertIn("Traces API is disabled", response.json().get("detail", ""))
            return

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tracing_enabled", body)

        if not body["tracing_enabled"]:
            self.assertIn("message", body)
            return

        self.assertIn("total_traces", body)
        self.assertIn("by_engine", body)
        self.assertIn("by_status", body)

    def test_assistant_chat_anthropic_live_if_enabled(self) -> None:
        """
        Optional live Anthropic check.

        Enable only when you intentionally want to validate end-to-end LLM runtime:
        - RUN_ANTHROPIC_LIVE_TESTS=1
        - ANTHROPIC_API_KEY=<real key>
        """
        if os.getenv("RUN_ANTHROPIC_LIVE_TESTS") != "1":
            self.skipTest("Set RUN_ANTHROPIC_LIVE_TESTS=1 to run live Anthropic test.")

        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key or "YOUR_KEY_HERE" in api_key:
            self.skipTest("Set ANTHROPIC_API_KEY to a real key for live Anthropic test.")

        with patched_env(
            {
                "PROVIDER_ASSISTANT_MODE": "anthropic",
                "PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC": "false",
                "PROVIDER_ASSISTANT_MAX_TURNS": "3",
            }
        ):
            response = self.client.post(
                "/api/assistant/chat",
                json=self._payload("Any active blood thinner risk before surgery?"),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["engine"], "anthropic-agent-sdk")
        self.assertIn(body["confidence"], {"high", "medium", "low"})


if __name__ == "__main__":
    unittest.main()
