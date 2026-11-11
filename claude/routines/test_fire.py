#!/usr/bin/env python3
"""Tests for fire.py (no network, no Keychain)."""
import io
import json
import unittest
import urllib.error

import fire

R = {"ping": {"trigger": "trig_01XttsW9zn29Diwu7vMN3drZ", "keychain": "claude-routine-ping"}}
TOKEN = "sk-ant-oat01-FAKEFAKEFAKEFAKE"


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FireTest(unittest.TestCase):
    def test_request_shape(self):
        seen = {}

        def opener(req, timeout):
            seen["req"] = req
            return Resp(json.dumps({"claude_code_session_url": "https://claude.ai/code/session_x"}).encode())

        name, url = fire.fire("ping hello there", R, lambda s: TOKEN, opener)
        req = seen["req"]
        self.assertEqual((name, url), ("ping", "https://claude.ai/code/session_x"))
        self.assertEqual(req.full_url,
                         "https://api.anthropic.com/v1/claude_code/routines/trig_01XttsW9zn29Diwu7vMN3drZ/fire")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Anthropic-beta"), fire.BETA)
        self.assertEqual(json.loads(req.data), {"text": "hello there"})

    def test_unknown_and_empty(self):
        for q in ("", "nope hi"):
            with self.assertRaises(fire.Bad):
                fire.fire(q, R, lambda s: TOKEN, None)

    def test_errors_never_show_token(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

        with self.assertRaises(fire.Bad) as cm:
            fire.fire("ping", R, lambda s: TOKEN, opener)
        self.assertIn("401", str(cm.exception))
        self.assertNotIn(TOKEN, str(cm.exception))

    def test_shipped_routines_json_is_valid(self):
        self.assertIn("ping", fire.load_routines())


if __name__ == "__main__":
    unittest.main()
