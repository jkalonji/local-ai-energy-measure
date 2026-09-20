"""Run one harness on one task with one model, and measure what it cost.

The harness is a child process working in a throw-away workspace. Its model requests go through
the logging proxy (ollama_proxy.py), so the tracker log ends up with one `ollama_call` row per
request. After the process ends, the ~20 ms GPU power samples (gpu_samples.py) of the run window
give the exact energy, split between the time a request was in flight and the time it was not.

Everything between process start and process end counts, including the harness's own start-up and
the GPU's idle draw: that is what using the harness costs in practice.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from attribution import summarize_run
from benchmarks import common
from csv_log import append_row
from gpu_samples import hires_path_for, read_hires
from hires_report import read_rows

from .checks import run_checks
from .definitions import Harness, Task, render

TRANSCRIPT_LIMIT = 200_000  # characters kept per stream in the saved transcript
SETTLE_S = 1.5  # let the tracker drain its sample buffer (0.5 s) and the proxy finish writing


@dataclass
class ProcessResult:
    exit_code: Optional[int]   # None when the process was killed on timeout
    stdout: str
    stderr: str
    timed_out: bool


@dataclass
class Session:
    """What a run needs from the outside world."""
    log_path: Path
    batch_id: str
    proxy_url: str = common.PROXY_URL
    ollama_url: str = common.OLLAMA_URL
    num_ctx: int = common.HARNESS_NUM_CTX
    transcripts_dir: Optional[Path] = None
    keep_workspaces: bool = False
    settle_s: float = SETTLE_S


def _kill_tree(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":  # node spawns children of its own
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def run_process(argv: List[str], cwd: Path, env: Dict[str, str], timeout_s: float) -> ProcessResult:
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return ProcessResult(proc.returncode, stdout, stderr, False)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        stdout, stderr = proc.communicate()
        return ProcessResult(None, stdout or "", stderr or "", True)


def measure_run(log_path: Path, start_ts: float, end_ts: float) -> Dict[str, object]:
    """Energy and request statistics of the window [start_ts, end_ts] from the tracker log."""
    rows = read_rows(log_path)
    calls = rows[rows["row_type"] == "ollama_call"]
    calls = calls[(calls["call_end_ts"] >= start_ts) & (calls["call_start_ts"] <= end_ts)]
    sources = sorted({s for s in calls["tokens_source"] if s})
    measured: Dict[str, object] = {
        "n_calls": len(calls),
        "prompt_tokens": calls["prompt_tokens"].sum(min_count=1),
        "completion_tokens": calls["completion_tokens"].sum(min_count=1),
        "tokens_source": "+".join(sources),
    }
    try:
        power, _ = read_hires(hires_path_for(log_path))
    except FileNotFoundError:
        return {**measured, "notes": "no hi-res power log: was the tracker started with --no-hires?"}
    summary = summarize_run(power, calls, start_ts, end_ts)
    covered_s = summary["covered_s"]
    measured.update({
        "energy_j": summary["energy_total_j"],
        "energy_wh": summary["energy_total_j"] / 3600,
        "energy_in_calls_j": summary["energy_in_calls_j"],
        "energy_between_calls_j": summary["energy_between_calls_j"],
        "in_calls_share": summary["in_calls_share"],
        "mean_power_w": summary["energy_total_j"] / covered_s if covered_s > 0 else None,
        "coverage": covered_s / summary["run_s"] if summary["run_s"] > 0 else None,
    })
    if not covered_s:
        measured["notes"] = "no GPU power samples in the run window"
    elif measured["coverage"] < 0.99:
        measured["notes"] = f"GPU power samples cover only {measured['coverage']:.0%} of the run"
    return measured


def observed_context(model: str, ollama_url: str = common.OLLAMA_URL) -> Optional[int]:
    """Context window Ollama has allocated for `model` right now (None if it is not loaded)."""
    try:
        loaded = requests.get(f"{ollama_url}/api/ps", timeout=10).json().get("models", [])
    except (requests.RequestException, ValueError):
        return None
    return next((m.get("context_length") for m in loaded if model in (m.get("name"), m.get("model"))), None)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in text)


def _save_transcript(session: Session, run_id: str, argv: List[str], result: ProcessResult) -> None:
    if session.transcripts_dir is None:
        return
    session.transcripts_dir.mkdir(parents=True, exist_ok=True)
    text = (f"$ {' '.join(argv)}\nexit code: {result.exit_code}{' (timed out)' if result.timed_out else ''}\n\n"
            f"--- stdout ---\n{result.stdout[-TRANSCRIPT_LIMIT:]}\n\n--- stderr ---\n{result.stderr[-TRANSCRIPT_LIMIT:]}\n")
    (session.transcripts_dir / f"{_slug(run_id)}.txt").write_text(text, encoding="utf-8")


def run_once(harness: Harness, model: str, task: Task, repeat: int, session: Session,
             sleep: Callable[[float], None] = time.sleep) -> Dict[str, object]:
    """Run `harness` on `task` with `model`; return one flat result row (see matrix.RUN_FIELDS)."""
    run_id = f"{harness.name}--{_slug(model)}--{task.id}--{repeat}--{session.batch_id}"
    root = Path(tempfile.mkdtemp(prefix="harness_run_"))
    try:
        workspace, home = root / "workspace", root / "home"
        workspace.mkdir()
        home.mkdir()
        for relative, content in task.files.items():
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        values = {
            "task": task.prompt, "model": model, "proxy_url": session.proxy_url,
            "v1_url": f"{session.proxy_url}/v1", "num_ctx": session.num_ctx, "workspace": workspace,
            "home": home, "harness_dir": harness.dir, "python": sys.executable,
        }
        for relative, content in harness.files.items():
            target = home / render(relative, values)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(content, values), encoding="utf-8", newline="\n")
        argv = [render(part, values) for part in harness.command]
        env = {**os.environ, **{key: render(value, values) for key, value in harness.env.items()}}

        start_ts = time.time()
        result = run_process(argv, workspace, env, task.timeout_s or harness.timeout_s)
        end_ts = time.time()
        sleep(session.settle_s)

        if result.timed_out:
            passed, detail = False, "timed out"
        else:
            passed, detail = run_checks(task, workspace, result.stdout)
        status = "timeout" if result.timed_out else "pass" if passed else ("error" if result.exit_code else "fail")

        append_row(session.log_path, {
            "row_type": "run", "timestamp": end_ts, "call_start_ts": start_ts, "call_end_ts": end_ts,
            "model": model, "harness": harness.name, "run_id": run_id, "task_id": task.id,
        })
        row: Dict[str, object] = {
            "run_id": run_id, "batch_id": session.batch_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_ts)),
            "harness": harness.name, "model": model, "task_id": task.id, "repeat": repeat,
            "status": status, "exit_code": result.exit_code, "duration_s": end_ts - start_ts,
            "check_detail": detail, "num_ctx_expected": session.num_ctx,
            "num_ctx_observed": observed_context(model, session.ollama_url),
        }
        measurement = measure_run(session.log_path, start_ts, end_ts)
        notes = [measurement.pop("notes", "")]
        if not measurement["n_calls"]:
            notes.append("no model request went through the proxy: the harness bypassed it")
        row.update(measurement)
        row["notes"] = "; ".join(n for n in notes if n)
        _save_transcript(session, run_id, argv, result)
        return row
    finally:
        if session.keep_workspaces:
            print(f"  workspace kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


def skipped_row(harness: Harness, model: str, task: Task, repeat: int, batch_id: str, status: str, why: str) -> Dict[str, object]:
    """A result row for a combination that was not run (model lacks a capability, or failed to load)."""
    return {
        "run_id": f"{harness.name}--{_slug(model)}--{task.id}--{repeat}--{batch_id}", "batch_id": batch_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "harness": harness.name, "model": model,
        "task_id": task.id, "repeat": repeat, "status": status, "notes": why,
    }
