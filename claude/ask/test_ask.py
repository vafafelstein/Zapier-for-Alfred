#!/usr/bin/env python3
"""Offline tests for ask.py: no network, no Keychain."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import ask  # noqa: E402


class Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_returning(payload, seen):
    def op(req, timeout=0):
        seen.append(req)
        return Resp(json.dumps(payload).encode())
    return op


OK = {"model": "claude-opus-5-5", "stop_reason": "end_turn",
      "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Thirty days."}],
      "usage": {"input_tokens": 1000, "output_tokens": 500}}


class T(unittest.TestCase):
    def test_request_shape(self):
        seen = []
        text, model, tin, tout, _ = ask.ask("998 window?", "low", get_key=lambda: "sk-test", opener=opener_returning(OK, seen))
        self.assertEqual(text, "Thirty days.")
        req = seen[0]
        body = json.loads(req.data)
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertEqual(body["output_config"], {"effort": "low"})
        self.assertEqual(body["fallbacks"], "default")
        self.assertNotIn("thinking", body)
        self.assertNotIn("temperature", body)
        h = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(h["x-api-key"], "sk-test")
        self.assertEqual(h["anthropic-version"], "2026-10-21")
        self.assertEqual(h["anthropic-beta"], "server-side-fallback-2026-07-01")

    def test_deep_effort(self):
        seen = []
        ask.ask("q", "high", get_key=lambda: "k", opener=opener_returning(OK, seen))
        self.assertEqual(json.loads(seen[0].data)["output_config"]["effort"], "high")

    def test_refusal(self):
        r = dict(OK, stop_reason="refusal", stop_details={"category": "cyber"}, content=[])
        with self.assertRaisesRegex(ask.Bad, "declined.*cyber"):
            ask.ask("q", get_key=lambda: "k", opener=opener_returning(r, []))

    def test_empty_and_long(self):
        with self.assertRaises(ask.Bad):
            ask.ask("  ", get_key=lambda: "k", opener=opener_returning(OK, []))
        with self.assertRaises(ask.Bad):
            ask.ask("x" * (ask.MAX_Q + 1), get_key=lambda: "k", opener=opener_returning(OK, []))

    def test_http_error_message(self):
        def op(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(
                json.dumps({"error": {"message": "This API key is not scoped to a workspace"}}).encode()))
        with self.assertRaisesRegex(ask.Bad, "HTTP 400.*not scoped"):
            ask.ask("q", get_key=lambda: "k", opener=op)

    def test_cost_and_usage_log_has_no_text(self):
        self.assertAlmostEqual(ask.cost("claude-opus-5-5", 1_000_000, 1_000_000), 24.0)
        with tempfile.TemporaryDirectory() as d:
            ask.STATE, ask.LOG = d, os.path.join(d, "usage.log")
            now = dt.datetime(2026, 11, 12, 1, 0, tzinfo=dt.timezone.utc)
            ask.log("claude-opus-5-5", "low", 1000, 500, now=now)
            line = open(ask.LOG).read()
            self.assertEqual(len(line.strip().split("\t")), 7)
            self.assertNotIn("998", line)
            self.assertIn("1 asks, about $0.01", ask.usage(ask.LOG, today=dt.date(2026, 11, 20), who="ultra"))
            ask.log("claude-opus-5-5", "low", 1000, 500, now=now, who="firm")
            with open(ask.LOG, "a") as fh:
                fh.write("2026-11-12T00:25:05-08:00\tclaude-opus-5-5\tlow\t94\t4\t0.0005\n")
            self.assertIn("ultra key, 2026-11: 2 asks", ask.usage(ask.LOG, today=dt.date(2026, 11, 20), who="ultra"))
            self.assertIn("firm key, 2026-11: 1 asks", ask.usage(ask.LOG, today=dt.date(2026, 11, 20), who="firm"))

    def test_clip_rewrite_and_undo(self):
        with tempfile.TemporaryDirectory() as d:
            ask.STATE, ask.LOG, ask.UNDO = d, os.path.join(d, "usage.log"), os.path.join(d, "undo.txt")
            board = {"v": "pls send the bills asap"}
            seen = []
            def asker(q, effort, system=None):
                seen.append((q, system)); return ("Please send the bills promptly.", "claude-opus-5-5", 50, 10, "end_turn")
            msg = ask.clip("make it polite", get=lambda: board["v"], put=lambda t: board.update(v=t), asker=asker)
            self.assertEqual(board["v"], "Please send the bills promptly.")
            self.assertIn("<text>\npls send the bills asap\n</text>", seen[0][0])
            self.assertEqual(seen[0][1], ask.REWRITE)
            self.assertIn("Rewritten", msg)
            self.assertEqual(oct(os.stat(ask.UNDO).st_mode & 0o777), "0o600")
            ask.clip("undo", get=lambda: board["v"], put=lambda t: board.update(v=t))
            self.assertEqual(board["v"], "pls send the bills asap")
            self.assertNotIn("bills", open(ask.LOG).read())
            with self.assertRaisesRegex(ask.Bad, "empty"):
                ask.clip("fix", get=lambda: "  ", put=lambda t: None, asker=asker)

    def test_presets(self):
        self.assertIn("spelling", ask.expand("g"))
        self.assertIn("Spanish", ask.expand("ES"))
        self.assertEqual(ask.expand("make it sing"), "make it sing")

    def test_label(self):
        self.assertEqual(ask.label("anthropic-api-firm"), "firm")
        self.assertEqual(ask.label("anthropic-api-ultra"), "ultra")

    def test_test_endpoint_no_beta(self):
        seen = []
        out = ask.test(get_key=lambda: "k", opener=opener_returning({"data": []}, seen))
        self.assertIn("200", out)
        self.assertNotIn("anthropic-beta", {k.lower() for k, _ in seen[0].header_items()})


if __name__ == "__main__":
    unittest.main(verbosity=1)
