#!/usr/bin/env python3
"""Serve a project locally while refusing hidden files such as .env."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


class SafeHandler(SimpleHTTPRequestHandler):
    def hidden_path(self) -> bool:
        path = PurePosixPath(unquote(urlsplit(self.path).path))
        return any(part.startswith(".") for part in path.parts if part not in {".", ".."})

    def do_GET(self) -> None:
        if self.hidden_path():
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self.hidden_path():
            self.send_error(404)
            return
        super().do_HEAD()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    handler = partial(SafeHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {root} at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
