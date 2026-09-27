"""A dedicated Ollama server for the benchmarks, whose default context window is fixed.

Agent harnesses talk to Ollama's OpenAI-compatible /v1 API, which cannot carry `num_ctx`: a model
gets the server's default context. The Ollama desktop app passes its own "Context length" setting
to its server (262144 on this machine), which beats OLLAMA_CONTEXT_LENGTH, and qwen3:4b then asks
for ~150 GB of KV cache and fails to load.

So the benchmarks do not use the app's server. They use a second `ollama serve` of their own, on
BENCH_URL, started with OLLAMA_CONTEXT_LENGTH=NUM_CTX. It reads the same model store as the app,
which keeps running untouched for everyday use. `ensure_server` starts it when nothing answers
there, detached, so it outlives the process that started it and later runs reuse it; its output
goes to logs/ollama_bench_server.log. ollama_proxy.py and the benchmark runners call it, so nothing
has to be started by hand.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

BENCH_PORT = 11436
BENCH_URL = f"http://127.0.0.1:{BENCH_PORT}"
NUM_CTX = 32768
LOG_FILE = Path(__file__).resolve().parent / "logs" / "ollama_bench_server.log"
START_TIMEOUT_S = 60


def is_up(url: str = BENCH_URL) -> bool:
    try:
        return requests.get(f"{url}/api/version", timeout=3).ok
    except requests.RequestException:
        return False


def ensure_server(url: str = BENCH_URL, num_ctx: int = NUM_CTX, log_file: Path = LOG_FILE,
                  timeout_s: float = START_TIMEOUT_S) -> bool:
    """Make sure the benchmark Ollama server answers on `url`; return True if it was started now.

    Only BENCH_URL is managed: any other URL is someone else's server and is left alone.
    """
    if is_up(url) or url.rstrip("/") != BENCH_URL:
        return False
    executable = shutil.which("ollama")
    if executable is None:
        raise RuntimeError("cannot start the benchmark Ollama server: `ollama` is not on the PATH")
    env = {**os.environ, "OLLAMA_HOST": f"127.0.0.1:{BENCH_PORT}", "OLLAMA_CONTEXT_LENGTH": str(num_ctx)}
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as log:
        log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ollama serve on {url}, context {num_ctx} ---\n")
        log.flush()
        if sys.platform == "win32":
            detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            detach = {"start_new_session": True}
        subprocess.Popen([executable, "serve"], env=env, stdin=subprocess.DEVNULL, stdout=log,
                         stderr=subprocess.STDOUT, **detach)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_up(url):
            print(f"Started the benchmark Ollama server on {url} (context {num_ctx}, log: {log_file})")
            return True
        time.sleep(0.5)
    raise RuntimeError(f"the benchmark Ollama server did not answer on {url} within {timeout_s:.0f} s: see {log_file}")
