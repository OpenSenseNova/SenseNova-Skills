"""Exercise the CLI and real MCP SDK transport against observable HTTP fixtures."""

import asyncio
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search.py"
spec = importlib.util.spec_from_file_location("search_web", SCRIPT)
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)
REAL_CLIENT = httpx.AsyncClient


class SearchTests(unittest.TestCase):
    def run_cli(self, argv, *, tool_error=False, status=None, slow=False):
        requests = []

        async def respond(request):
            body = json.loads(request.content) if request.content else {}
            requests.append((request, body))
            if slow:
                await asyncio.sleep(1)
            if status:
                return httpx.Response(status, headers={"Retry-After": "60"})
            if "id" not in body:
                return httpx.Response(202)
            if body["method"] == "initialize":
                result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "fixture", "version": "1"}}
            elif body["method"] == "tools/list":
                result = {"tools": [{"name": name, "inputSchema": {"type": "object"}}
                                    for name in ("web_search", "web_fetch")]}
            elif body["method"] == "tools/call":
                payload = {"results": [{"title": "Agent Skills", "url": "https://agentskills.io/specification",
                                        "excerpts": ["Skills contain a SKILL.md file."]}]}
                result = {"content": [{"type": "text", "text": json.dumps(payload)}],
                          "structuredContent": payload, "isError": tool_error}
            else:
                self.fail(f"Unexpected MCP method: {body['method']}")
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

        def client(**kwargs):
            return REAL_CLIENT(transport=httpx.MockTransport(respond), **kwargs)

        stdout = io.StringIO()
        with patch.object(search.httpx, "AsyncClient", client), contextlib.redirect_stdout(stdout):
            code = search.main(argv)
        text = stdout.getvalue()
        return code, json.loads(text) if text else None, requests

    def assert_requests(self, requests, tool, arguments):
        self.assertTrue(requests)
        for request, _ in requests:
            self.assertEqual(str(request.url), "https://search.parallel.ai/mcp")
            self.assertEqual(request.headers["User-Agent"], search.USER_AGENT)
            self.assertNotIn("Authorization", request.headers)
        messages = [body for _, body in requests]
        self.assertIn("initialize", [body.get("method") for body in messages])
        dispatched = [body for body in messages if body.get("method") == "tools/call"]
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]["params"]["name"], tool)
        self.assertEqual(dispatched[0]["params"]["arguments"], arguments)

    def test_search_dispatch_ignores_environment_credentials(self):
        with patch.dict("os.environ", {"PARALLEL_API_KEY": "unused-sentinel", "SN_API_KEY": "unused-sentinel"}):
            code, output, requests = self.run_cli([
                "search", "Find the skill specification", "--query", "Agent Skills specification",
                "--query", "Agent Skills format", "--session-id", "conversation-123"])
        self.assertEqual(code, 0)
        self.assertTrue(output["success"])
        self.assertEqual(output["result"]["structuredContent"]["results"][0]["title"], "Agent Skills")
        self.assert_requests(requests, "web_search", {"objective": "Find the skill specification",
            "search_queries": ["Agent Skills specification", "Agent Skills format"], "session_id": "conversation-123"})

    def test_fetch_dispatch_and_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results" / "page.json"
            code, stdout, requests = self.run_cli(["fetch", "https://agentskills.io/specification",
                "--objective", "Required frontmatter", "--output", str(output_path)])
            self.assertEqual(code, 0)
            self.assertIsNone(stdout)
            self.assertTrue(json.loads(output_path.read_text())["success"])
        self.assert_requests(requests, "web_fetch", {"urls": ["https://agentskills.io/specification"],
            "objective": "Required frontmatter"})

    def test_tool_error_preserves_response_and_exits_one(self):
        code, output, _ = self.run_cli(["search", "Find sources", "--query", "skills"], tool_error=True)
        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertTrue(output["result"]["isError"])
        self.assertIn("content", output["result"])

    def test_transport_failure_exits_one(self):
        code, output, _ = self.run_cli(["fetch", "https://agentskills.io"], status=503)
        self.assertEqual(code, 1)
        self.assertFalse(output["success"])
        self.assertIn("MCP request failed", output["error"])

    def test_total_timeout(self):
        code, output, _ = self.run_cli(["fetch", "https://agentskills.io", "--timeout", "0.01"], slow=True)
        self.assertEqual(code, 1)
        self.assertIn("timed out", output["error"])

    def test_invalid_arguments(self):
        cases = [
            ["search", "goal"], ["search", " ", "--query", "query"],
            ["search", "goal", "--query", " "], ["fetch", "file:///etc/passwd"],
            ["fetch", "https://user:password@example.com"],
            ["fetch", "https://example.com", "--objective", "x" * 201],
            ["fetch", "https://example.com", "--session-id", "x" * 101],
            ["fetch"] + ["https://example.com"] * 21,
        ]
        cases += [["fetch", "https://example.com", "--timeout", value] for value in ("0", "-1", "nan", "inf")]
        for argv in cases:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    search.parse_args(argv)
                self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
