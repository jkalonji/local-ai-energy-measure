"""Tests for ollama_proxy.py against a fake Ollama: what gets logged, and that responses pass through untouched."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import csv_log
import ollama_proxy
from ollama_proxy import CallStats


def sse(*objects):
    body = b"".join(b"data: " + json.dumps(o).encode() + b"\n\n" for o in objects)
    return body + b"data: [DONE]\n\n"


def chunk(text="", finish=None, **extra):
    return {"model": "m", "choices": [{"index": 0, "delta": {"content": text} if text else {}, "finish_reason": finish}], **extra}


NATIVE_STREAM = (
    json.dumps({"model": "m", "response": "a", "done": False}).encode() + b"\n"
    + json.dumps({"model": "m", "response": "", "done": True, "prompt_eval_count": 4,
                  "eval_count": 10, "eval_duration": 500_000_000}).encode() + b"\n"
)
V1_NON_STREAM = json.dumps({"model": "m", "choices": [{"message": {"content": "hi"}}],
                            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}).encode() + b"\n"
V1_STREAM_USAGE = sse(chunk("a"), chunk("b"), chunk(finish="stop"),
                      {"model": "m", "choices": [], "usage": {"prompt_tokens": 16, "completion_tokens": 20}})
V1_STREAM_NO_USAGE = sse(chunk("a"), chunk("b"), chunk("c"), chunk(finish="stop"))

RESPONSES = {
    "/api/generate": NATIVE_STREAM,
    "/v1/chat/completions?mode=plain": V1_NON_STREAM,
    "/v1/chat/completions?mode=usage": V1_STREAM_USAGE,
    "/v1/chat/completions?mode=nousage": V1_STREAM_NO_USAGE,
    "/api/tags": b'{"models": []}\n',
}


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _reply(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        body = RESPONSES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "model not found"}')
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _reply


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class ProxyEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = serve(FakeOllama)
        cls._old_url = ollama_proxy.ProxyHandler.ollama_url
        ollama_proxy.ProxyHandler.ollama_url = f"http://127.0.0.1:{cls.upstream.server_port}"
        cls.proxy = serve(ollama_proxy.ProxyHandler)

    @classmethod
    def tearDownClass(cls):
        cls.proxy.shutdown()
        cls.upstream.shutdown()
        ollama_proxy.ProxyHandler.ollama_url = cls._old_url

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "energy_test.csv"
        for name in ("latest_log_file", "new_log_path"):
            patcher = mock.patch.object(ollama_proxy, name, return_value=self.log)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, path, method="POST"):
        req = urllib.request.Request(f"http://127.0.0.1:{self.proxy.server_port}{path}", data=b"{}", method=method)
        with urllib.request.urlopen(req) as response:
            return response.read()

    def rows(self):
        if not self.log.exists():
            return []
        import csv
        with self.log.open(newline="", encoding="utf-8") as f:
            return [csv_log.parse_row(r) for r in csv.reader(f) if csv_log.parse_row(r)]

    def test_native_call_keeps_server_reported_counts_and_speed(self):
        self.assertEqual(self.call("/api/generate"), NATIVE_STREAM)
        (row,) = self.rows()
        self.assertEqual((row["endpoint"], row["tokens_source"], row["model"]), ("/api/generate", "usage", "m"))
        self.assertEqual((row["prompt_tokens"], row["completion_tokens"], row["total_tokens"]), ("4", "10", "14"))
        self.assertEqual(row["tps"], "20.00")
        self.assertEqual(row["row_type"], "ollama_call")
        self.assertLessEqual(float(row["call_start_ts"]), float(row["call_end_ts"]))

    def test_openai_non_streaming_call_uses_usage_and_logs_no_speed(self):
        self.assertEqual(self.call("/v1/chat/completions?mode=plain"), V1_NON_STREAM)
        (row,) = self.rows()
        self.assertEqual((row["endpoint"], row["tokens_source"]), ("/v1/chat/completions", "usage"))
        self.assertEqual((row["prompt_tokens"], row["completion_tokens"], row["total_tokens"]), ("7", "3", "10"))
        self.assertEqual(row["tps"], "")

    def test_openai_stream_with_include_usage_reads_the_final_usage_chunk(self):
        self.assertEqual(self.call("/v1/chat/completions?mode=usage"), V1_STREAM_USAGE)
        (row,) = self.rows()
        self.assertEqual((row["tokens_source"], row["prompt_tokens"], row["completion_tokens"]), ("usage", "16", "20"))

    def test_openai_stream_without_usage_estimates_from_chunks_and_says_so(self):
        self.assertEqual(self.call("/v1/chat/completions?mode=nousage"), V1_STREAM_NO_USAGE)
        (row,) = self.rows()
        self.assertEqual(row["tokens_source"], "chunk_count")
        self.assertEqual((row["prompt_tokens"], row["completion_tokens"], row["total_tokens"]), ("", "3", ""))

    def test_other_endpoints_pass_through_without_a_log_row(self):
        self.assertEqual(self.call("/api/tags", method="GET"), b'{"models": []}\n')
        self.assertEqual(self.rows(), [])

    def test_upstream_errors_are_relayed_and_not_logged(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.call("/api/chat")
        self.assertEqual(caught.exception.code, 404)
        self.assertEqual(caught.exception.read(), b'{"error": "model not found"}')
        self.assertEqual(self.rows(), [])


class CallStatsTest(unittest.TestCase):
    def feed(self, *lines):
        stats = CallStats()
        for line in lines:
            stats.feed(line)
        return stats.summary()

    def test_garbage_and_non_object_lines_are_ignored(self):
        self.assertIsNone(self.feed(b"", b"\n", b"not json", b"[1, 2]", b"data: [DONE]", b"data: {broken"))

    def test_tool_call_and_reasoning_deltas_count_as_output(self):
        summary = self.feed(
            b'data: {"model":"m","choices":[{"delta":{"reasoning":"hmm"}}]}',
            b'data: {"model":"m","choices":[{"delta":{"tool_calls":[{"id":"1"}]}}]}',
            b'data: {"model":"m","choices":[{"delta":{}}]}',
        )
        self.assertEqual((summary["completion_tokens"], summary["tokens_source"]), (2, "chunk_count"))

    def test_legacy_completions_text_chunks_count(self):
        summary = self.feed(b'data: {"model":"m","choices":[{"text":"a"}]}', b'data: {"model":"m","choices":[{"text":"b"}]}')
        self.assertEqual(summary["completion_tokens"], 2)

    def test_usage_wins_over_chunk_count(self):
        summary = self.feed(b'data: {"model":"m","choices":[{"delta":{"content":"a"}}]}',
                            b'data: {"model":"m","choices":[],"usage":{"prompt_tokens":5,"completion_tokens":9}}')
        self.assertEqual((summary["prompt_tokens"], summary["completion_tokens"], summary["tokens_source"]), (5, 9, "usage"))


if __name__ == "__main__":
    unittest.main()
