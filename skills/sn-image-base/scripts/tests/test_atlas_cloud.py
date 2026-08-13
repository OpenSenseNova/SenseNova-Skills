from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sn_image_base.generation.atlas_cloud import AtlasCloudText2ImageClient

PNG = b"\x89PNG\r\n\x1a\n"


class AtlasHandler(BaseHTTPRequestHandler):
    polls = 0
    submitted: dict | None = None
    authorization: str | None = None
    download_authorization: str | None = None

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/api/v1/model/generateImage":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        type(self).submitted = json.loads(self.rfile.read(length))
        type(self).authorization = self.headers.get("authorization")
        self._json({"code": 200, "data": {"id": "task-1", "status": "created"}})

    def do_GET(self) -> None:
        if self.path == "/api/v1/model/result/task-1":
            type(self).polls += 1
            if type(self).polls == 1:
                self._json({"id": "task-1", "status": "processing", "outputs": []})
            else:
                host = self.headers["host"]
                self._json(
                    {
                        "data": {
                            "id": "task-1",
                            "status": "completed",
                            "outputs": [f"http://{host}/image.png"],
                        }
                    }
                )
            return
        if self.path == "/image.png":
            type(self).download_authorization = self.headers.get("authorization")
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG)))
            self.end_headers()
            self.wfile.write(PNG)
            return
        self.send_error(404)

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AtlasCloudClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        AtlasHandler.polls = 0
        AtlasHandler.submitted = None
        AtlasHandler.authorization = None
        AtlasHandler.download_authorization = None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AtlasHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}/api/v1"

    async def asyncTearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    async def test_generates_and_downloads_png(self) -> None:
        client = AtlasCloudText2ImageClient(
            api_key="test-key",
            base_url=self.base_url,
            model="bytedance/seedream-v5.0-lite",
            timeout=2,
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "portrait.png"
            try:
                result = await client.generate(
                    "editorial portrait",
                    image_size="2k",
                    aspect_ratio="3:4",
                    output_path=output,
                    poll_interval=0,
                )
            finally:
                await client.aclose()
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["task_id"], "task-1")
            self.assertEqual(output.read_bytes(), PNG)
        self.assertEqual(AtlasHandler.authorization, "Bearer test-key")
        self.assertIsNone(AtlasHandler.download_authorization)
        self.assertEqual(
            AtlasHandler.submitted,
            {
                "model": "bytedance/seedream-v5.0-lite",
                "prompt": "editorial portrait",
                "size": "1728*2304",
                "output_format": "png",
            },
        )
        self.assertEqual(AtlasHandler.polls, 2)

    def test_resolves_landscape_4k_size(self) -> None:
        self.assertEqual(
            AtlasCloudText2ImageClient._resolve_size("4K", "16:9"),
            "4096*2304",
        )

    def test_2k_sizes_meet_atlas_minimum_pixel_count(self) -> None:
        for aspect_ratio in ("3:4", "1:1", "16:9", "21:9"):
            width, height = (
                int(value)
                for value in AtlasCloudText2ImageClient._resolve_size(
                    "2K", aspect_ratio
                ).split("*")
            )
            self.assertGreaterEqual(width * height, 3_686_400)

    def test_rejects_invalid_aspect_ratio(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid aspect ratio"):
            AtlasCloudText2ImageClient._resolve_size("2K", "wide")

    def test_build_payload_keeps_negative_prompt_optional(self) -> None:
        client = AtlasCloudText2ImageClient(
            api_key="test-key",
            base_url=self.base_url,
            model="model",
        )
        self.assertEqual(
            client.build_payload("prompt", "model", size="2048*2048"),
            {
                "model": "model",
                "prompt": "prompt",
                "size": "2048*2048",
                "output_format": "png",
            },
        )
