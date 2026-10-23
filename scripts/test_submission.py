"""Offline HTTP request and failure checks; no Dune credits are used."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import fetch_burn as m


class SubmissionTests(unittest.TestCase):
    def test_auto_omits_tier_and_keeps_fresh_sql(self):
        response = io.BytesIO(b'{"execution_id":"test-execution"}')
        with patch.object(m, "DUNE_API_KEY", "offline-test"), patch.object(m, "DUNE_PERFORMANCE", "auto"), patch.object(m.urllib.request, "urlopen", return_value=response) as opened:
            execution, sql, _ = m.execute_fresh_query()
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.dune.com/api/v1/sql/execute")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"sql": sql})
        self.assertIn("LIMIT 32", sql)
        self.assertEqual(execution, "test-execution")

    def test_explicit_tier_is_preserved(self):
        with patch.object(m, "DUNE_PERFORMANCE", "small"), patch.object(m, "request_json", return_value={"execution_id": "test"}) as send:
            m.execute_fresh_query()
        self.assertEqual(send.call_args.kwargs["payload"]["performance"], "small")

    def test_invalid_default_fails_once_with_actionable_message(self):
        error = urllib.error.HTTPError("https://api.dune.com/api/v1/sql/execute", 400, "Bad Request", {}, io.BytesIO(b'{"error":"Invalid performance tier"}'))
        with tempfile.TemporaryDirectory() as directory, patch.object(m, "OUT_DIR", Path(directory)), patch.object(m, "DUNE_API_KEY", "offline-test"), patch.object(m, "DUNE_PERFORMANCE", "auto"), patch.object(m.urllib.request, "urlopen", side_effect=error) as opened:
            with self.assertRaises(SystemExit):
                m.execute_fresh_query()
            status = json.loads((Path(directory) / "status.json").read_text())
        self.assertEqual(opened.call_count, 1)
        self.assertFalse(status["ok"])
        self.assertIn("account/team", status["message"])
        self.assertNotIn("offline-test", status["message"])

    def test_other_http_errors_still_fail(self):
        error = urllib.error.HTTPError("https://api.dune.com/api/v1/sql/execute", 401, "Unauthorized", {}, io.BytesIO(b'{"error":"Unauthorized"}'))
        with tempfile.TemporaryDirectory() as directory, patch.object(m, "OUT_DIR", Path(directory)), patch.object(m, "DUNE_API_KEY", "offline-test"), patch.object(m.urllib.request, "urlopen", side_effect=error) as opened:
            with self.assertRaises(SystemExit):
                m.execute_fresh_query()
            status = json.loads((Path(directory) / "status.json").read_text())
        self.assertEqual(opened.call_count, 1)
        self.assertIn("HTTP 401", status["message"])


if __name__ == "__main__":
    unittest.main()
