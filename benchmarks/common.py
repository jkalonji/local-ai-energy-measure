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


def model_capabilities(model: str, ollama_url: str = OLLAMA_URL) -> List[str]:
    """Capabilities Ollama reports for `model` (e.g. completion, tools, thinking, vision).

    Older Ollama versions do not report the field; the result is then empty.
    """
    response = requests.post(f"{ollama_url}/api/show", json={"model": model}, timeout=30)
    response.raise_for_status()
    return response.json().get("capabilities", [])
