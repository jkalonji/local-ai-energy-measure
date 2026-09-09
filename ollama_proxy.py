"""Transparent logging reverse proxy in front of Ollama.

Forwards every request unchanged to a real Ollama server, but for
/api/generate and /api/chat it also extracts token counts and
generation speed (TPS) from the response — streamed or not — and
appends an "ollama_call" row to the currently active tracker log (see
log_paths.py / csv_log.py), timestamped with the call's start/end so
the dashboard can attribute GPU energy and load to it precisely.

Point your Ollama client at this proxy instead of talking to Ollama
directly, e.g.:
    OLLAMA_HOST=http://localhost:11435 ollama run llama3.1
or set the base URL of whatever tool you use (Open WebUI, a script,
etc.) to http://localhost:11435 — everything else (tags, ps, pulling
models...) is passed through untouched.

Run with:
    python ollama_proxy.py
(optionally alongside energy_tracker.py, in another terminal, so the
GPU samples and the Ollama calls land in the same log file)
"""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen

from csv_log import append_row
from log_paths import latest_log_file, new_log_path

STAT_PATHS = {"/api/generate", "/api/chat"}
HOP_BY_HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding"}


class ProxyHandler(BaseHTTPRequestHandler):
    ollama_url = "http://localhost:11434"

    def log_message(self, fmt, *args) -> None:  # noqa: D401 - silence default per-request logging
        pass

    def do_GET(self) -> None:
        self._forward(stat=False)

    def do_POST(self) -> None:
        self._forward(stat=self.path in STAT_PATHS)

    def do_DELETE(self) -> None:
        self._forward(stat=False)

    def _forward(self, stat: bool) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""

        req = Request(self.ollama_url.rstrip("/") + self.path, data=body or None, method=self.command)
        for key, value in self.headers.items():
            if key.lower() not in ("host", "content-length"):
                req.add_header(key, value)

        call_start = time.time()
        try:
            upstream = urlopen(req)
        except URLError as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Could not reach Ollama at {self.ollama_url}: {e}".encode())
            return

        self.send_response(upstream.status)
        for key, value in upstream.headers.items():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(key, value)
        self.end_headers()

        last_stats = None
        for line in upstream:
            self.wfile.write(line)
            self.wfile.flush()
            if stat:
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("done"):
                    last_stats = obj

        call_end = time.time()
        if stat and last_stats:
            self._log_call(call_start, call_end, last_stats)

    def _log_call(self, start_ts: float, end_ts: float, stats: dict) -> None:
        eval_count = stats.get("eval_count", 0) or 0
        eval_duration_s = (stats.get("eval_duration", 0) or 0) / 1e9
        prompt_tokens = stats.get("prompt_eval_count", 0) or 0
        tps = eval_count / eval_duration_s if eval_duration_s > 0 else 0.0
        model = stats.get("model", "")

        log_path = latest_log_file() or new_log_path()
        append_row(log_path, {
            "row_type": "ollama_call",
            "timestamp": f"{end_ts:.3f}",
            "call_start_ts": f"{start_ts:.3f}",
            "call_end_ts": f"{end_ts:.3f}",
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": eval_count,
            "total_tokens": prompt_tokens + eval_count,
            "tps": f"{tps:.2f}",
        })
        print(f"[ollama_proxy] {model}: {eval_count} tokens @ {tps:.1f} tok/s -> {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transparent logging proxy in front of Ollama.")
    parser.add_argument("--port", type=int, default=11435, help="Port to listen on (default: 11435).")
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Real Ollama server URL to forward to (default: http://localhost:11434).",
    )
    args = parser.parse_args()

    ProxyHandler.ollama_url = args.ollama_url
    server = ThreadingHTTPServer(("localhost", args.port), ProxyHandler)
    print(f"Ollama logging proxy listening on http://localhost:{args.port} -> {args.ollama_url}")
    print("Point your Ollama client at this address to log token/TPS stats (Ctrl+C to stop).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
