"""Attribute GPU energy and utilization samples to Ollama call windows.

energy_tracker.py logs periodic "sample" rows (power, GPU util,
cumulative energy). ollama_proxy.py logs "ollama_call" rows with a
start/end timestamp. These functions bracket each call's window
against the nearest samples to compute the energy actually spent, and
the average GPU load, during that specific call. Those samples are 1 s
averages, so the numbers are coarse for calls shorter than a few seconds.

summarize_run works from the ~20 ms samples of gpu_samples.py instead,
and splits a whole benchmark run's energy into the time the model was
answering and the time it was not (tool execution, harness overhead).
"""

from typing import Dict, List, Optional, Tuple

import pandas as pd

from gpu_samples import energy_between


def energy_for_window(samples: pd.DataFrame, start_ts: float, end_ts: float) -> Optional[float]:
    """Energy (Wh) consumed between start_ts and end_ts.

    Uses the cumulative-energy sample just before start_ts and the one
    just after end_ts, so the result reflects exactly the window - no
    interpolation. Returns None if the window isn't bracketed by
    samples on both sides (e.g. no tracker was running for the call).
    """
    before = samples[samples["timestamp"] <= start_ts]
    after = samples[samples["timestamp"] >= end_ts]
    if before.empty or after.empty:
        return None
    e0 = before.iloc[-1]["energy_wh_cumulative"]
    e1 = after.iloc[0]["energy_wh_cumulative"]
    return max(e1 - e0, 0.0)


def avg_gpu_util_for_window(samples: pd.DataFrame, start_ts: float, end_ts: float) -> Optional[float]:
    """Average GPU utilization (%) over samples falling within the window."""
    window = samples[(samples["timestamp"] >= start_ts) & (samples["timestamp"] <= end_ts)]
    if window.empty:
        return None
    return window["gpu_util_pct"].mean()


def attribute_calls(samples: pd.DataFrame, calls: pd.DataFrame) -> pd.DataFrame:
    """Return `calls` with energy_wh_call / avg_gpu_util_call columns added."""
    samples = samples.sort_values("timestamp")
    calls = calls.copy()
    calls["energy_wh_call"] = calls.apply(
        lambda r: energy_for_window(samples, r["call_start_ts"], r["call_end_ts"]), axis=1
    )
    calls["avg_gpu_util_call"] = calls.apply(
        lambda r: avg_gpu_util_for_window(samples, r["call_start_ts"], r["call_end_ts"]), axis=1
    )
    return calls


def _merged_windows(calls: pd.DataFrame, run_start_ts: float, run_end_ts: float) -> List[Tuple[float, float]]:
    """Call windows clipped to the run and merged where they overlap (concurrent calls)."""
    windows = sorted(
        (max(r.call_start_ts, run_start_ts), min(r.call_end_ts, run_end_ts))
        for r in calls.itertuples()
        if r.call_end_ts >= run_start_ts and r.call_start_ts <= run_end_ts
    )
    merged: List[List[float]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def summarize_run(power: pd.DataFrame, calls: pd.DataFrame, run_start_ts: float, run_end_ts: float) -> Dict[str, float]:
    """Energy split of one run, from the ~20 ms power samples of gpu_samples.read_hires.

    `calls` needs call_start_ts / call_end_ts (epoch seconds) and may have
    prompt_tokens / completion_tokens; calls overlapping the run window count.
    energy_in_calls_j is the energy while at least one call was in flight;
    energy_between_calls_j is the rest of the run (GPU waiting on tools,
    harness overhead). covered_s below run_s means power samples are missing.
    """
    ts = power["timestamp_us"].to_numpy()
    mw = power["power_mw"].to_numpy()
    if calls.empty:  # e.g. the harness bypassed the proxy: no window, no columns
        calls = pd.DataFrame({"call_start_ts": [], "call_end_ts": [], "prompt_tokens": [], "completion_tokens": []})

    def joules(start_s: float, end_s: float) -> Tuple[float, float]:
        return energy_between(ts, mw, round(start_s * 1e6), round(end_s * 1e6))

    total_j, covered_s = joules(run_start_ts, run_end_ts)
    windows = _merged_windows(calls, run_start_ts, run_end_ts)
    in_calls_j = sum(joules(a, b)[0] for a, b in windows)
    in_run = calls[(calls["call_end_ts"] >= run_start_ts) & (calls["call_start_ts"] <= run_end_ts)]
    return {
        "run_s": run_end_ts - run_start_ts,
        "covered_s": covered_s,
        "energy_total_j": total_j,
        "energy_in_calls_j": in_calls_j,
        "energy_between_calls_j": total_j - in_calls_j,
        "in_calls_share": in_calls_j / total_j if total_j > 0 else float("nan"),
        "n_calls": len(in_run),
        "prompt_tokens": float(in_run["prompt_tokens"].sum()) if "prompt_tokens" in in_run else float("nan"),
        "completion_tokens": float(in_run["completion_tokens"].sum()) if "completion_tokens" in in_run else float("nan"),
    }
