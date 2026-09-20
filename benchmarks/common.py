"""Helpers shared by the benchmark scripts under benchmarks/.

Scripts must put the repository root on sys.path before importing this module,
because it reuses the root-level `log_paths` module.
"""

import csv
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml

import log_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"
MODELS_FILE = Path(__file__).with_name("models.yaml")

OLLAMA_URL = "http://localhost:11434"
PROXY_URL = "http://localhost:11435"

# Context window for every with_harnesses run. Harnesses talk to the OpenAI-compatible /v1 API,
# which cannot carry num_ctx, so it is imposed on the Ollama server (OLLAMA_CONTEXT_LENGTH) and
# checked with require_context() before a run. without_harness keeps its own NUM_CTX=8192.
HARNESS_NUM_CTX = 32768


class ModelLoadError(RuntimeError):
    """Ollama could not load one model (typically out of memory)."""


class ContextMismatch(RuntimeError):
    """The Ollama server does not give harness requests the expected context window."""


def load_models_file(path: Path = MODELS_FILE) -> Dict:
    """Parse models.yaml and check that every set only names declared models."""
    with path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    declared = {m["name"] for m in config["models"]}
    for set_name, names in config["sets"].items():
        unknown = [n for n in names if n not in declared]
        if unknown:
            raise ValueError(f"{path.name}: set '{set_name}' names undeclared models: {unknown}")
    return config


def all_model_names(config: Dict) -> List[str]:
    """Every declared model name, in file order."""
    return [m["name"] for m in config["models"]]


def model_set(config: Dict, set_name: str) -> List[str]:
    """Model names of the set `set_name`; raises KeyError listing the valid sets."""
    try:
        return list(config["sets"][set_name])
    except KeyError:
        raise KeyError(f"unknown set '{set_name}', choose one of: {', '.join(config['sets'])}") from None


def latest_log_file(log_dir: Path = LOG_DIR) -> Path:
    """Most recent tracker log; raises if energy_tracker.py never wrote one."""
    path = log_paths.latest_log_file(log_dir)
    if path is None:
        raise RuntimeError("No tracker log file found - is energy_tracker.py running?")
    return path


def avg_power_in_window(log_path: Path, start_ts: float, end_ts: float) -> Tuple[Optional[float], int]:
    """Mean GPU power (W) of the tracker samples in [start_ts, end_ts], and the sample count.

    Returns (None, 0) when no sample falls in the window.
    """
    powers = []
    with log_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["row_type"] != "sample":
                continue
            ts = float(row["timestamp"])
            if start_ts <= ts <= end_ts:
                powers.append(float(row["power_w"]))
    if not powers:
        return None, 0
    return sum(powers) / len(powers), len(powers)


def ollama_stop(model: str) -> None:
    """Unload `model` from VRAM so the next model starts from a clean GPU."""
    try:
        subprocess.run(["ollama", "stop", model], capture_output=True, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] ollama stop {model} failed: {e}")


def warmup(model: str, num_ctx: int, proxy_url: str = PROXY_URL) -> None:
    """Load `model` into VRAM with a tiny generation so the measured call excludes load time."""
    try:
        requests.post(
            f"{proxy_url}/api/generate",
            json={
                "model": model, "prompt": "Bonjour", "stream": False,
                "options": {"num_predict": 5, "num_ctx": num_ctx},
            },
            timeout=180,
        )
    except requests.RequestException as e:
        print(f"  [warn] warm-up {model} failed: {e}")


def require_context(model: str, num_ctx: int = HARNESS_NUM_CTX, ollama_url: str = OLLAMA_URL) -> None:
    """Fail unless a harness-style request loads `model` with a `num_ctx` context window.

    Loads the model the way a harness does (OpenAI-compatible /v1, no num_ctx, straight to Ollama
    so nothing is logged) and reads the context actually allocated from /api/ps. A model already
    loaded with another context is reloaded at the server default, so this reports that default.
    """
    reply = requests.post(
        f"{ollama_url}/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "Bonjour"}], "max_tokens": 1},
        timeout=300,
    )
    if not reply.ok:
        raise ModelLoadError(
            f"{model} could not be loaded by a /v1 request without num_ctx (HTTP {reply.status_code}): "
            f"{reply.text[:300]}\n{_CONTEXT_FIX.format(num_ctx=num_ctx)}"
        )
    loaded = requests.get(f"{ollama_url}/api/ps", timeout=30).json().get("models", [])
    actual = next((m.get("context_length") for m in loaded if model in (m.get("name"), m.get("model"))), None)
    if actual != num_ctx:
        raise ContextMismatch(f"{model} runs with context {actual}, expected {num_ctx}.\n{_CONTEXT_FIX.format(num_ctx=num_ctx)}")


_CONTEXT_FIX = (
    "Harnesses cannot set num_ctx per request. Quit Ollama, then start it with the variable set:\n"
    "  cmd:        set OLLAMA_CONTEXT_LENGTH={num_ctx} & ollama serve\n"
    "  PowerShell: $env:OLLAMA_CONTEXT_LENGTH = {num_ctx}; ollama serve\n"
    "  (or run `setx OLLAMA_CONTEXT_LENGTH {num_ctx}` once and restart the Ollama app)"
)


def model_capabilities(model: str, ollama_url: str = OLLAMA_URL) -> List[str]:
    """Capabilities Ollama reports for `model` (e.g. completion, tools, thinking, vision).

    Older Ollama versions do not report the field; the result is then empty.
    """
    response = requests.post(f"{ollama_url}/api/show", json={"model": model}, timeout=30)
    response.raise_for_status()
    return response.json().get("capabilities", [])
