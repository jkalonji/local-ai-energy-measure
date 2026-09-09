"""Shared CSV schema and a process-safe row writer for the tracker log.

The log is a single "long" table with a `row_type` discriminator, so a
GPU sample and an Ollama call can share one timeline:

- "sample": a periodic GPU reading from energy_tracker.py (power,
  GPU utilization, cumulative energy).
- "ollama_call": one completed Ollama request logged by
  ollama_proxy.py (tokens, generation speed, call time window).

energy_tracker.py and ollama_proxy.py can run as separate processes at
the same time and both append to the same run's file, so every append
is guarded by a short-lived lock file next to the CSV.
"""

import csv
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

# Sample-row fields, then ollama_call-row fields. Unused fields are left
# empty on a given row (e.g. an "ollama_call" row has no power_w).
CSV_FIELDS = [
    "row_type",
    "timestamp",
    "elapsed_s",
    "power_w",
    "gpu_util_pct",
    "energy_wh_cumulative",
    "call_start_ts",
    "call_end_ts",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "tps",
]


@contextmanager
def _file_lock(lock_path: Path, timeout: float = 5.0, poll: float = 0.05) -> Iterator[None]:
    start = time.time()
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Could not acquire lock on {lock_path} within {timeout}s")
            time.sleep(poll)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def append_row(log_path: Path, row: Dict[str, Any]) -> None:
    """Append one row to the log, creating the file/header if needed.

    Safe to call concurrently from multiple processes writing to the
    same run's log file (e.g. the tracker and the Ollama proxy).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_name(log_path.name + ".lock")
    with _file_lock(lock_path):
        is_new_file = not log_path.exists() or log_path.stat().st_size == 0
        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(CSV_FIELDS)
            writer.writerow([row.get(field, "") for field in CSV_FIELDS])
            f.flush()
