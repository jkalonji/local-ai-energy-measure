"""Energy of every 100 ms (or any bin size) of a GPU time window, from the ~20 ms samples.

Pick the window in one of four ways:
    python hires_report.py --start 1789910044.2 --end 1789910047.0   # epoch seconds
    python hires_report.py --last 30                                  # the last 30 s
    python hires_report.py --call -1                                  # last logged call (1-based; negative counts from the end)
    python hires_report.py --run-id my-run                            # a "run" row written by a runner
Add --bin-ms 100 (default) to change the bin size and --out bins.csv to save every bin.
Without --log it reads the most recent tracker log; the hi-res samples are the
matching file under hires/ (see gpu_samples.py, needs energy_tracker.py to have run
with hi-res enabled).

Also prints the window's total energy, and for a run the split between time
inside model calls and time between them.
"""

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from attribution import summarize_run
from csv_log import CSV_FIELDS, parse_row
from gpu_samples import DEFAULT_BIN_US, bin_energy, hires_path_for, read_hires
from log_paths import latest_log_file

NUMERIC = ["call_start_ts", "call_end_ts", "prompt_tokens", "completion_tokens"]


def read_rows(log_path: Path) -> pd.DataFrame:
    """Every row of a tracker log as a frame with the current CSV_FIELDS columns."""
    rows = []
    with log_path.open(newline="", encoding="utf-8") as f:
        for fields in csv.reader(f):
            row = parse_row(fields) if fields else None
            if row is not None:
                rows.append(row)
    df = pd.DataFrame(rows, columns=CSV_FIELDS)
    for column in NUMERIC:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def window_from_args(args: argparse.Namespace, rows: pd.DataFrame) -> Tuple[float, float, str]:
    """(start_ts, end_ts, label) in epoch seconds for the window the arguments ask for."""
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None:
            raise SystemExit("--start and --end go together")
        return args.start, args.end, "window"
    if args.last is not None:
        now = time.time()
        return now - args.last, now, f"last {args.last:g} s"
    if args.call is not None:
        if args.call == 0:
            raise SystemExit("--call is 1-based (or negative from the end); 0 is not a call")
        calls = rows[rows["row_type"] == "ollama_call"].dropna(subset=["call_start_ts", "call_end_ts"])
        calls = calls.sort_values("call_start_ts").reset_index(drop=True)
        index = args.call - 1 if args.call > 0 else args.call
        if not -len(calls) <= index < len(calls):
            raise SystemExit(f"--call {args.call}: the log has {len(calls)} call(s)")
        call = calls.iloc[index]
        endpoint = call["endpoint"] if isinstance(call["endpoint"], str) and call["endpoint"] else "native"
        return call["call_start_ts"], call["call_end_ts"], f"call {args.call} ({call['model']}, {endpoint})"
    runs = rows[(rows["row_type"] == "run") & (rows["run_id"] == args.run_id)]
    if runs.empty:
        raise SystemExit(f"no run row with run_id={args.run_id!r} in the log")
    run = runs.iloc[-1]
    return run["call_start_ts"], run["call_end_ts"], f"run {args.run_id} ({run['harness']}, {run['model']})"


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Energy per time bin of a GPU window, from ~20 ms samples.")
    parser.add_argument("--log", type=Path, help="tracker log (default: the most recent one)")
    window = parser.add_mutually_exclusive_group(required=True)
    window.add_argument("--start", type=float, help="window start, epoch seconds (with --end)")
    window.add_argument("--last", type=float, help="the last N seconds")
    window.add_argument("--call", type=int, help="Nth logged Ollama call (1-based, negative from the end)")
    window.add_argument("--run-id", help="run_id of a logged run")
    parser.add_argument("--end", type=float, help="window end, epoch seconds (with --start)")
    parser.add_argument("--bin-ms", type=int, default=DEFAULT_BIN_US // 1000, help="bin size in ms (default: 100)")
    parser.add_argument("--out", type=Path, help="write every bin to this CSV")
    args = parser.parse_args(argv)

    log_path = args.log or latest_log_file()
    if log_path is None:
        raise SystemExit("no tracker log found")
    rows = read_rows(log_path)
    start_ts, end_ts, label = window_from_args(args, rows)
    power, util = read_hires(hires_path_for(log_path))

    start_us, end_us = round(start_ts * 1e6), round(end_ts * 1e6)
    bins = bin_energy(power, util, start_us, end_us, args.bin_ms * 1000)
    total_j = bins["energy_j"].sum()
    covered = bins["covered_s"].sum()
    duration = (end_us - start_us) / 1e6

    print(f"{label}: {duration:.3f} s  ({log_path.name})")
    print(f"energy {total_j:.3f} J = {total_j / 3600:.5f} Wh | mean {total_j / covered if covered else float('nan'):.1f} W "
          f"| samples cover {covered:.3f} of {duration:.3f} s")
    if covered < duration * 0.99:
        print(f"WARNING: {duration - covered:.3f} s of the window have no power samples (tracker down or samples lost); "
              f"energy above is a lower bound.", file=sys.stderr)

    if args.run_id is not None:
        calls = rows[rows["row_type"] == "ollama_call"].dropna(subset=["call_start_ts", "call_end_ts"])
        s = summarize_run(power, calls, start_ts, end_ts)
        print(f"in calls {s['energy_in_calls_j']:.2f} J | between calls {s['energy_between_calls_j']:.2f} J "
              f"({s['in_calls_share']:.0%} in calls) | {s['n_calls']} call(s), "
              f"{s['prompt_tokens']:.0f} prompt / {s['completion_tokens']:.0f} completion tokens")

    if args.out:
        bins.to_csv(args.out, index=False)
        print(f"{len(bins)} bins written to {args.out}")
    else:
        print(bins.head(30).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        if len(bins) > 30:
            print(f"... {len(bins) - 30} more bins (use --out to save all)")


if __name__ == "__main__":
    main()
