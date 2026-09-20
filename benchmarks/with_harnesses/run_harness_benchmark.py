"""Benchmark "modele x harnais": what does a local model cost, and does it work, inside an agent harness?

Each combination (harness, model, task) is run headless in a throw-away workspace, through the
logging proxy, while the GPU tracker records power. The result of a run is:
- did the agent do the task (objective check, see tasks/*.yaml)
- how long it took, how many requests and tokens
- the GPU energy of the whole run, split between time spent inside model requests and time
  between them (harness start-up, tool execution)

Usage (energy_tracker.py and ollama_proxy.py must run, Ollama with OLLAMA_CONTEXT_LENGTH=32768):
    python benchmarks/with_harnesses/run_harness_benchmark.py --harness dsh --models qwen3:4b
    python benchmarks/with_harnesses/run_harness_benchmark.py --harness dsh,ollama-agent-harness --set round_1 --tasks write_file
    python benchmarks/with_harnesses/run_harness_benchmark.py --harness dsh --models qwen3:4b --dry-run   # plan only
    python benchmarks/with_harnesses/run_harness_benchmark.py --report-only                                # rebuild the matrix

Results: results/with_harnesses/{runs.csv, matrix.csv, compatibility_matrix.md}.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from benchmarks import common  # noqa: E402
from benchmarks.with_harnesses import matrix  # noqa: E402
from benchmarks.with_harnesses.definitions import (  # noqa: E402
    HARNESSES_DIR, TASKS_DIR, list_names, load_harness, load_task)
from benchmarks.with_harnesses.execute import Session, run_once, skipped_row  # noqa: E402

TRACKER_STALE_S = 15  # the tracker appends a sample every second


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--harness", help=f"comma-separated harnesses ({', '.join(list_names(HARNESSES_DIR))}), or 'all'")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--models", help="comma-separated model names")
    selection.add_argument("--set", dest="set_name", help="named set from benchmarks/models.yaml")
    selection.add_argument("--all", action="store_true", help="every model of benchmarks/models.yaml (slow)")
    parser.add_argument("--tasks", help=f"comma-separated tasks (default: all of {', '.join(list_names(TASKS_DIR))})")
    parser.add_argument("--repeat", type=int, default=1, help="runs per (harness, model, task) (default 1)")
    parser.add_argument("--timeout", type=int, help="seconds per run, overriding harness and task timeouts")
    parser.add_argument("--include-unsupported", action="store_true",
                        help="also run tool tasks on models Ollama does not report as supporting tools")
    parser.add_argument("--keep-workspaces", action="store_true", help="do not delete the workspace of each run")
    parser.add_argument("--dry-run", action="store_true", help="print the runs that would be done, and stop")
    parser.add_argument("--report-only", action="store_true", help="rebuild matrix.csv and the markdown from runs.csv")
    args = parser.parse_args(argv)
    if not args.report_only and not args.harness:
        parser.error("--harness is required (or use --report-only)")
    if not args.report_only and not (args.models or args.set_name or args.all):
        parser.error("choose the models with --models, --set or --all (nothing runs by default)")
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    return args


def resolve_models(args: argparse.Namespace) -> List[str]:
    if args.models:
        return [m.strip() for m in args.models.split(",") if m.strip()]
    config = common.load_models_file()
    return common.all_model_names(config) if args.all else common.model_set(config, args.set_name)


def preflight() -> None:
    """Fail early, with the fix, when something the measurement depends on is not running."""
    problems = []
    for name, url in (("Ollama", common.OLLAMA_URL), ("the proxy (ollama_proxy.py)", common.PROXY_URL)):
        try:
            requests.get(f"{url}/api/version", timeout=5).raise_for_status()
        except requests.RequestException:
            problems.append(f"{name} does not answer on {url}")
    try:
        log = common.latest_log_file()
        if time.time() - log.stat().st_mtime > TRACKER_STALE_S:
            problems.append(f"{log.name} has not been written for {TRACKER_STALE_S} s: is energy_tracker.py running?")
    except RuntimeError as e:
        problems.append(str(e))
    if problems:
        raise SystemExit("Cannot start:\n  - " + "\n  - ".join(problems))


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    if args.report_only:
        matrix.write_reports()
        print(f"Wrote {matrix.MATRIX_CSV} and {matrix.MATRIX_MD}")
        return

    names = list_names(HARNESSES_DIR) if args.harness == "all" else [h.strip() for h in args.harness.split(",")]
    harnesses = [load_harness(name) for name in names]
    for harness in harnesses:
        if not harness.dir.exists():
            raise SystemExit(f"{harness.name}: install directory {harness.dir} does not exist (edit 'dir' in its yaml)")
    tasks = [load_task(t.strip()) for t in (args.tasks.split(",") if args.tasks else list_names(TASKS_DIR))]
    models = resolve_models(args)
    if args.timeout:
        for item in (*harnesses, *tasks):
            item.timeout_s = args.timeout

    total = len(harnesses) * len(models) * len(tasks) * args.repeat
    print(f"{len(harnesses)} harness(es) x {len(models)} model(s) x {len(tasks)} task(s) x {args.repeat} = {total} runs")
    if args.dry_run:
        for harness in harnesses:
            for model in models:
                print(f"  {harness.name} / {model}: {', '.join(t.id for t in tasks)}")
        return

    preflight()
    batch_id = time.strftime("%Y%m%d_%H%M%S")
    session = Session(log_path=common.latest_log_file(), batch_id=batch_id,
                      transcripts_dir=REPO_ROOT / "logs" / "harness_runs", keep_workspaces=args.keep_workspaces)
    print(f"Tracker log: {session.log_path}   transcripts: {session.transcripts_dir}")

    def record(row: dict) -> None:
        matrix.append_run(row)
        matrix.write_reports()

    for harness in harnesses:
        for model in models:
            capabilities = common.model_capabilities(model)
            runnable = [t for t in tasks if args.include_unsupported or "tools" in capabilities or not t.needs_tools]
            for task in tasks:
                if task not in runnable:
                    for repeat in range(1, args.repeat + 1):
                        record(skipped_row(harness, model, task, repeat, batch_id, "skipped_no_tools",
                                           "Ollama does not report tool support for this model"))
            if not runnable:
                print(f"[{harness.name} / {model}] skipped: no runnable task (no tool support)")
                continue

            common.ollama_stop(model)  # every model starts from a clean GPU, loaded like a harness would
            try:
                common.require_context(model, session.num_ctx)
            except common.ContextMismatch as e:
                raise SystemExit(f"Stopping: the Ollama server does not use the fixed context window.\n{e}")
            except common.ModelLoadError as e:
                print(f"[{harness.name} / {model}] failed to load: {str(e).splitlines()[0][:200]}")
                for task in runnable:
                    for repeat in range(1, args.repeat + 1):
                        record(skipped_row(harness, model, task, repeat, batch_id, "load_failed", str(e).splitlines()[0][:300]))
                continue

            for task in runnable:
                for repeat in range(1, args.repeat + 1):
                    row = run_once(harness, model, task, repeat, session)
                    record(row)
                    energy = row.get("energy_wh")
                    print(f"[{harness.name} / {model} / {task.id} #{repeat}] {row['status']} in {row['duration_s']:.0f} s, "
                          f"{row.get('n_calls', 0)} request(s), "
                          f"{'%.3f Wh' % energy if energy is not None else 'energy unknown'} - {row['check_detail']}")
                    if row["notes"]:
                        print(f"    note: {row['notes']}")
            common.ollama_stop(model)

    print(f"Done. Results: {matrix.MATRIX_MD}")


if __name__ == "__main__":
    main()
