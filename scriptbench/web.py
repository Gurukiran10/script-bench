"""Local web UI: python -m scriptbench.web  ->  http://127.0.0.1:8000

Standard library only. It binds to localhost, so the API key never leaves
this machine and nobody else can spend your quota.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .generator import generate_detailed
from .llm import LLMError

PAGE = (Path(__file__).parent / "index.html").read_bytes()
MAX_BODY_BYTES = 10_000


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self._send(404, "text/plain", b"not found")
            return
        self._send(200, "text/html; charset=utf-8", PAGE)

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self._send(404, "text/plain", b"not found")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": "request too large"})
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object with niche, topic and seconds")
            result = generate_detailed(
                str(data.get("niche", "")),
                str(data.get("topic", "")),
                int(data.get("seconds", 0)),
                offline=bool(data.get("offline")),
            )
        except (ValueError, TypeError) as err:
            self._json(400, {"error": str(err)})
            return
        except LLMError as err:
            message = ("Every AI model is busy right now (Google reports high demand)."
                       if err.transient else str(err).split("\n")[0])
            self._json(503, {"error": message, "transient": err.transient})
            return
        payload = {**result.script, "meta": result.meta}
        if result.meta["engine"] == "templates" and not data.get("offline"):
            payload["notice"] = ("No API key found, so this is the quick template instead of the AI writer. "
                                 "Add GEMINI_API_KEY (or GROQ_API_KEY) to .env and restart to use the AI writer.")
        self._json(200, payload)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, "application/json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # keep the console readable
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scriptbench.web")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Script Bench running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
