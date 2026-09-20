"""Shared CSV schema and a process-safe row writer for the tracker log.

The log is a single "long" table with a `row_type` discriminator, so a
GPU sample, an Ollama call and a benchmark run can share one timeline:

- "sample": a periodic GPU reading from energy_tracker.py (power,
  GPU utilization, cumulative energy). Its `power_w` is NVML's 1-second
  trailing average, refreshed twice a second: fine for totals, too slow
  for sub-second questions (see gpu_samples.py for those).
- "ollama_call": one completed model request logged by ollama_proxy.py,
  from Ollama's native API (/api/*) or its OpenAI-compatible API (/v1/*).
  `endpoint` says which; `tokens_source` says whether the token counts
  are reported by the server ("usage") or estimated ("chunk_count").
- "run": one benchmark run written by a runner. `call_start_ts` /
  `call_end_ts` hold the run window; `harness`, `run_id`, `task_id` and
  `model` identify it. Calls belong to a run by time overlap.

energy_tracker.py and ollama_proxy.py can run as separate processes at
the same time and both append to the same run's file, so every append
is guarded by a short-lived lock file next to the CSV.

Files written by older versions have fewer columns. `append_row` keeps
writing a file with the columns of its own header, and `parse_row`
reads rows of every known width, so old logs stay readable.
"""

import csv
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# Schema before endpoint/run tagging was added. Still found in existing log files.
LEGACY_V2_FIELDS = [
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

# Sample-row fields, then ollama_call-row fields, then run tagging. Unused
# fields are left empty on a given row (e.g. an "ollama_call" row has no power_w).
CSV_FIELDS = LEGACY_V2_FIELDS + [
    "endpoint",
    "tokens_source",
    "harness",
    "run_id",
    "task_id",
]

# Oldest schema, written by tracker processes started before row_type existed.
OLD_SCHEMA_FIELDS = ["timestamp", "elapsed_s", "power_w", "energy_wh_cumulative"]

_HEADERS = (CSV_FIELDS, LEGACY_V2_FIELDS, OLD_SCHEMA_FIELDS)


def parse_row(fields: List[str]) -> Optional[Dict[str, str]]:
    """Map one raw CSV row to a dict, by its actual width.

    A single file can mix widths (e.g. a tracker started before an update
    keeps writing old rows while the updated proxy appends new ones), so
    each row is parsed independently instead of trusting the header line.
    Returns None for header lines and for rows of an unknown width.
    """
    if fields in _HEADERS:
        return None
    if len(fields) == len(CSV_FIELDS):
        return dict(zip(CSV_FIELDS, fields))
    if len(fields) == len(LEGACY_V2_FIELDS):
        return dict(zip(LEGACY_V2_FIELDS, fields))
    if len(fields) == len(OLD_SCHEMA_FIELDS):
        row = dict(zip(OLD_SCHEMA_FIELDS, fields))
        row["row_type"] = "sample"
        return row
    return None


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


def _columns_of_existing_file(log_path: Path) -> List[str]:
    """Columns to write into an existing file: its own header if it is a known
    full schema, else the current schema (the file then mixes widths)."""
    with log_path.open(newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    if header in (CSV_FIELDS, LEGACY_V2_FIELDS):
        return header
    return CSV_FIELDS


def append_row(log_path: Path, row: Dict[str, Any]) -> None:
    """Append one row to the log, creating the file/header if needed.

    Safe to call concurrently from multiple processes writing to the
    same run's log file (e.g. the tracker and the Ollama proxy). Fields
    the target file has no column for are dropped.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_name(log_path.name + ".lock")
    with _file_lock(lock_path):
        is_new_file = not log_path.exists() or log_path.stat().st_size == 0
        columns = CSV_FIELDS if is_new_file else _columns_of_existing_file(log_path)
        with log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(columns)
            writer.writerow([row.get(field, "") for field in columns])
            f.flush()
