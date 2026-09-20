"""Results of the with_harnesses benchmark: the run history, and the model x harness matrix.

results/with_harnesses/runs.csv is an append-only history, one row per run. A batch is one
invocation of run_harness_benchmark.py; for each (harness, model, task) only the most recent batch
counts, so re-running a combination replaces its old results without deleting the history.

The matrix cell of a (model, harness) pair is "passed/runs · median energy", over the runs that
actually executed. Combinations that were not run (the model lacks tool support, or failed to
load) are shown as such and never counted as failures of the harness.
"""

import csv
from pathlib import Path
from typing import Dict, List

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "with_harnesses"
RUNS_CSV = RESULTS_DIR / "runs.csv"
MATRIX_CSV = RESULTS_DIR / "matrix.csv"
MATRIX_MD = RESULTS_DIR / "compatibility_matrix.md"

RUN_FIELDS = [
    "run_id", "batch_id", "started_at", "harness", "model", "task_id", "repeat", "status", "exit_code",
    "duration_s", "check_detail", "num_ctx_expected", "num_ctx_observed", "n_calls", "prompt_tokens",
    "completion_tokens", "tokens_source", "energy_j", "energy_wh", "energy_in_calls_j",
    "energy_between_calls_j", "in_calls_share", "mean_power_w", "coverage", "notes",
]
MEASURED = ("pass", "fail", "error", "timeout")
NOT_RUN = {"skipped_no_tools": "no tool support", "load_failed": "failed to load"}
NUMERIC = ["repeat", "exit_code", "duration_s", "num_ctx_expected", "num_ctx_observed", "n_calls", "prompt_tokens",
           "completion_tokens", "energy_j", "energy_wh", "energy_in_calls_j", "energy_between_calls_j",
           "in_calls_share", "mean_power_w", "coverage"]


def _format(value: object) -> object:
    if isinstance(value, float):
        return "" if pd.isna(value) else f"{value:.6g}"
    return "" if value is None else value


def append_run(row: Dict[str, object], path: Path = RUNS_CSV) -> None:
    """Append one result row, writing the header if the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    if not is_new:
        with path.open(newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        if header != RUN_FIELDS:
            raise ValueError(f"{path.name} has a different column layout than this version writes: move it aside first")
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(RUN_FIELDS)
        writer.writerow([_format(row.get(field, "")) for field in RUN_FIELDS])


def read_runs(path: Path = RUNS_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=RUN_FIELDS)
    runs = pd.read_csv(path, dtype=str, keep_default_na=False)
    for column in NUMERIC:
        runs[column] = pd.to_numeric(runs[column], errors="coerce")
    return runs


def current_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """For every (harness, model, task), only the rows of its most recent batch."""
    if runs.empty:
        return runs
    latest = runs.groupby(["harness", "model", "task_id"])["batch_id"].transform("max")
    return runs[runs["batch_id"] == latest]


def build_matrix(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per (model, harness) with pass counts and median cost of the runs that executed."""
    rows: List[dict] = []
    for (model, harness), group in current_runs(runs).groupby(["model", "harness"]):
        done = group[group["status"].isin(MEASURED)]
        passed = int((done["status"] == "pass").sum())
        not_run = sorted(set(group["status"]) - set(MEASURED))
        rows.append({
            "model": model, "harness": harness, "runs": len(done), "passed": passed,
            "pass_rate": passed / len(done) if len(done) else float("nan"),
            "median_energy_wh": done["energy_wh"].median() if len(done) else float("nan"),
            "median_duration_s": done["duration_s"].median() if len(done) else float("nan"),
            "not_run": ", ".join(not_run),
        })
    return pd.DataFrame(rows, columns=["model", "harness", "runs", "passed", "pass_rate", "median_energy_wh",
                                       "median_duration_s", "not_run"])


def _energy(value: float) -> str:
    if pd.isna(value):
        return "?"
    return f"{value:.2f} Wh" if value >= 0.01 else f"{value:.4f} Wh"


def _cell(row: pd.Series) -> str:
    if not row["runs"]:
        reason = ", ".join(NOT_RUN.get(s, s) for s in row["not_run"].split(", ") if s)
        return f"n/a ({reason})" if reason else "n/a"
    text = f"{int(row['passed'])}/{int(row['runs'])} · {_energy(row['median_energy_wh'])}"
    if row["not_run"]:
        text += " (+ some not run)"
    return text


def _table(header: List[str], rows: List[List[str]]) -> List[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def render_markdown(runs: pd.DataFrame) -> str:
    current = current_runs(runs)
    matrix = build_matrix(runs)
    lines = [
        "# Model x harness compatibility matrix",
        "",
        "Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run "
        "(harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples "
        "of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context "
        "window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).",
        "",
    ]
    if matrix.empty:
        return "\n".join(lines + ["No run recorded yet."]) + "\n"
    harnesses = sorted(matrix["harness"].unique())
    by_pair = {(r["model"], r["harness"]): _cell(r) for _, r in matrix.iterrows()}
    lines += _table(["Model", *harnesses],
                    [[model, *(by_pair.get((model, h), "not tested") for h in harnesses)]
                     for model in sorted(matrix["model"].unique())])

    lines += ["", "## Detail per task", ""]
    detail: List[List[str]] = []
    for (model, harness, task), group in current.sort_values(["model", "harness", "task_id"]).groupby(
            ["model", "harness", "task_id"], sort=False):
        done = group[group["status"].isin(MEASURED)]
        if done.empty:
            detail.append([model, harness, task, NOT_RUN.get(group["status"].iloc[0], group["status"].iloc[0]), "", "", "", ""])
            continue
        statuses = ", ".join(f"{n} {s}" for s, n in done["status"].value_counts().items())
        share = done["in_calls_share"].median()
        detail.append([model, harness, task, statuses, _energy(done["energy_wh"].median()),
                       f"{done['duration_s'].median():.0f} s",
                       "" if pd.isna(share) else f"{share:.0%}", f"{int(done['n_calls'].median())}"])
    lines += _table(["Model", "Harness", "Task", "Result", "Median energy", "Median time", "Energy in model calls",
                     "Requests"], detail)

    warnings = []
    for _, r in current[current["status"].isin(MEASURED)].iterrows():
        if pd.notna(r["num_ctx_observed"]) and r["num_ctx_observed"] != r["num_ctx_expected"]:
            warnings.append(f"- `{r['run_id']}`: context {int(r['num_ctx_observed'])} observed, {int(r['num_ctx_expected'])} expected "
                            "(the harness set its own context window)")
        if r["notes"]:
            warnings.append(f"- `{r['run_id']}`: {r['notes']}")
    if warnings:
        lines += ["", "## Warnings", "", *warnings]
    return "\n".join(lines) + "\n"


def write_reports(runs_path: Path = RUNS_CSV, matrix_csv: Path = MATRIX_CSV, matrix_md: Path = MATRIX_MD) -> None:
    runs = read_runs(runs_path)
    matrix = build_matrix(runs)
    matrix_csv.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(matrix_csv, index=False, float_format="%.6g")
    matrix_md.write_text(render_markdown(runs), encoding="utf-8")
