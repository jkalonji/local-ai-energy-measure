"""Transparent logging reverse proxy in front of Ollama.

Forwards every request unchanged to a real Ollama server, but for the
generation endpoints it also extracts token counts from the response -
streamed or not - and appends an "ollama_call" row to the currently
active tracker log (see log_paths.py / csv_log.py), timestamped with the
call's start/end so GPU energy can be attributed to it precisely.

Logged endpoints:
- Ollama native API: /api/generate, /api/chat. Token counts and speed
  (tok/s) come from Ollama's own final object.
- OpenAI-compatible API: /v1/chat/completions, /v1/completions. Token
  counts come from the `usage` field, which a streaming client only gets
  if it asks for it (`stream_options.include_usage`). Requests are never
  modified, so without it the completion count is estimated from the
  number of streamed content chunks (`tokens_source` = "chunk_count",
  prompt tokens unknown). No tok/s is logged for these: the API reports
  no generation duration.

Point your Ollama client at this proxy instead of talking to Ollama
directly, e.g.:
    OLLAMA_HOST=http://localhost:11435 ollama run llama3.1
or set the base URL of whatever tool you use (Open WebUI, an agent
harness using http://localhost:11435/v1, a script, etc.) - everything
else (tags, ps, pulling models...) is passed through untouched.

Run with:
    python ollama_proxy.py
(optionally alongside energy_tracker.py, in another terminal, so the
GPU samples and the Ollama calls land in the same log file)
"""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from csv_log import append_row
from log_paths import latest_log_file, new_log_path

NATIVE_PATHS = {"/api/generate", "/api/chat"}
OPENAI_PATHS = {"/v1/chat/completions", "/v1/completions"}
STAT_PATHS = NATIVE_PATHS | OPENAI_PATHS
HOP_BY_HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding"}


class CallStats:
    """Accumulates token stats from the lines of one upstream response.

    Understands Ollama's native JSON lines and OpenAI-style responses: one
    JSON object, or Server-Sent Events ("data: {...}" lines) when streamed.
    """

    def __init__(self) -> None:
        self.model = ""
        self._native_final: Optional[dict] = None
        self._usage: Optional[dict] = None
        self._content_chunks = 0

    def feed(self, line: bytes) -> None:
        text = line.strip()
        if text.startswith(b"data:"):
            text = text[len(b"data:"):].strip()
        if not text or text == b"[DONE]":
            return
        try:
            obj = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(obj, dict):
            return
        self.model = obj.get("model") or self.model
        if obj.get("done"):
            self._native_final = obj
            return
        if obj.get("usage"):
            self._usage = obj["usage"]
        for choice in obj.get("choices") or []:
            delta = choice.get("delta") or {}
            if (choice.get("text") or delta.get("content") or delta.get("reasoning")
                    or delta.get("reasoning_content") or delta.get("tool_calls")):
                self._content_chunks += 1

    def summary(self) -> Optional[dict]:
        """Token counts of the call, or None if the response had nothing to count.

        Keys: model, prompt_tokens (None if unknown), completion_tokens,
        eval_duration_s (None unless native API), tokens_source.
        """
        if self._native_final is not None:
            final = self._native_final
            return {
                "model": self.model,
                "prompt_tokens": final.get("prompt_eval_count", 0) or 0,
                "completion_tokens": final.get("eval_count", 0) or 0,
                "eval_duration_s": (final.get("eval_duration", 0) or 0) / 1e9,
                "tokens_source": "usage",
            }
        if self._usage is not None:
            return {
                "model": self.model,
                "prompt_tokens": self._usage.get("prompt_tokens", 0) or 0,
                "completion_tokens": self._usage.get("completion_tokens", 0) or 0,
                "eval_duration_s": None,
                "tokens_source": "usage",
            }
        if self._content_chunks:
            return {
                "model": self.model,
                "prompt_tokens": None,
                "completion_tokens": self._content_chunks,
                "eval_duration_s": None,
                "tokens_source": "chunk_count",
            }
        return None


class ProxyHandler(BaseHTTPRequestHandler):
    ollama_url = "http://localhost:11434"

    def log_message(self, fmt, *args) -> None:  # noqa: D401 - silence default per-request logging
        pass

    def do_GET(self) -> None:
        self._forward(stat=False)

    def do_HEAD(self) -> None:
        self._forward(stat=False)

    def do_POST(self) -> None:
        self._forward(stat=urlsplit(self.path).path in STAT_PATHS)

    def do_PUT(self) -> None:
        self._forward(stat=False)

    def do_PATCH(self) -> None:
        self._forward(stat=False)

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
        except HTTPError as e:
            # A real error response from Ollama itself (e.g. model not found) -
            # relay its actual status and body instead of masking it.
            self.send_response(e.code)
            for key, value in e.headers.items():
                if key.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(e.read())
            return
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

        stats = CallStats() if stat else None
        for line in upstream:
            self.wfile.write(line)
            self.wfile.flush()
            if stats is not None:
                stats.feed(line)

        call_end = time.time()
        summary = stats.summary() if stats is not None else None
        if summary is not None:
            self._log_call(call_start, call_end, urlsplit(self.path).path, summary)

    def _log_call(self, start_ts: float, end_ts: float, endpoint: str, summary: dict) -> None:
        completion = summary["completion_tokens"]
        prompt = summary["prompt_tokens"]
        eval_duration_s = summary["eval_duration_s"]
        tps = f"{completion / eval_duration_s:.2f}" if eval_duration_s else ""

        log_path = latest_log_file() or new_log_path()
        append_row(log_path, {
            "row_type": "ollama_call",
            "timestamp": f"{end_ts:.3f}",
            "call_start_ts": f"{start_ts:.3f}",
            "call_end_ts": f"{end_ts:.3f}",
            "model": summary["model"],
            "prompt_tokens": "" if prompt is None else prompt,
            "completion_tokens": completion,
            "total_tokens": "" if prompt is None else prompt + completion,
            "tps": tps,
            "endpoint": endpoint,
            "tokens_source": summary["tokens_source"],
        })
        speed = f" @ {tps} tok/s" if tps else ""
        print(f"[ollama_proxy] {summary['model']}: {completion} tokens ({summary['tokens_source']}){speed} "
              f"via {endpoint} -> {log_path}")


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
