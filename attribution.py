"""Attribute GPU energy and utilization samples to Ollama call windows.

energy_tracker.py logs periodic "sample" rows (power, GPU util,
cumulative energy). ollama_proxy.py logs "ollama_call" rows with a
start/end timestamp. These functions bracket each call's window
against the nearest samples to compute the energy actually spent, and
the average GPU load, during that specific call.
"""

from typing import Optional

import pandas as pd


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
