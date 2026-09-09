"""Streamlit dashboard for the GPU energy tracker.

Reads the CSV log(s) written by energy_tracker.py (and, if used,
ollama_proxy.py) and displays:
- a power-over-time and GPU-utilization-over-time curve (live if the
  tracker is currently running)
- a cumulative cost curve (USD), based on a selectable country's
  electricity price (see pricing.py / config/electricity_prices.json)
- if ollama_proxy.py was used: tokens, generation speed (tokens/s),
  and the exact GPU energy/load attributed to each Ollama call, plus a
  playful rowing-machine energy equivalent (see human_analogy.py)

Each run of energy_tracker.py writes its own timestamped file under
logs/ (see log_paths.py). By default this dashboard always follows the
most recent one, so restarting the tracker automatically switches the
dashboard to the new run without any manual action.

Run with:
    streamlit run dashboard.py
"""

import csv
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from attribution import attribute_calls
from csv_log import CSV_FIELDS
from human_analogy import format_rowing_equivalent
from log_paths import LOGS_DIR, latest_log_file, list_log_files
from pricing import get_prices_usd_per_kwh

st.set_page_config(page_title="GPU Energy Dashboard", page_icon="⚡", layout="wide")
st.title("⚡ GPU Energy Consumption Dashboard")

with st.sidebar:
    st.header("Settings")
    auto_latest = st.checkbox("Always use the most recent log file", value=True)
    selected_path_str: Optional[str] = None
    if not auto_latest:
        if st.button("🔄 Refresh file list"):
            st.rerun()
        available = list_log_files()
        options = [str(p) for p in available]
        if options:
            selected_path_str = st.selectbox("Log file", options=options)
        else:
            st.warning(f"No log files found in `{LOGS_DIR}/`.")
    live = st.checkbox("Live refresh", value=True)
    refresh_s = st.slider("Refresh interval (s)", 1, 30, 3, disabled=not live)


@st.cache_resource
def load_prices() -> dict[str, float]:
    """Fetch USD/kWh per country once per dashboard session."""
    return get_prices_usd_per_kwh()


prices = load_prices()

with st.sidebar:
    country = st.selectbox("Country (electricity rate)", options=list(prices.keys()), index=0)
    st.caption(f"Selected rate: {prices[country]:.4f} $/kWh")
    with st.expander("All rates (USD/kWh)"):
        for c, p in prices.items():
            st.write(f"{c}: {p:.4f} $/kWh")

NUMERIC_FIELDS = [
    "timestamp", "elapsed_s", "power_w", "gpu_util_pct", "energy_wh_cumulative",
    "call_start_ts", "call_end_ts", "prompt_tokens", "completion_tokens", "total_tokens", "tps",
]

# Old (pre row_type/gpu_util_pct/Ollama) log schema, still written by any
# tracker process started before this schema existed.
OLD_SCHEMA_FIELDS = ["timestamp", "elapsed_s", "power_w", "energy_wh_cumulative"]


def _parse_row(fields: list[str]) -> Optional[dict]:
    """Map one raw CSV row to a CSV_FIELDS dict, by its actual width.

    A single file can mix old-schema and new-schema rows (e.g. a
    tracker process started before an update keeps writing old rows,
    while ollama_proxy.py appends new-schema rows to the same file) -
    each row is parsed independently rather than trusting the file's
    single header line for every row.
    """
    if fields in (CSV_FIELDS, OLD_SCHEMA_FIELDS):
        return None  # header line
    if len(fields) == len(CSV_FIELDS):
        return dict(zip(CSV_FIELDS, fields))
    if len(fields) == len(OLD_SCHEMA_FIELDS):
        row = dict(zip(OLD_SCHEMA_FIELDS, fields))
        row["row_type"] = "sample"
        return row
    return None  # malformed/unrecognized row width


def read_log(path: Path) -> pd.DataFrame:
    """Read a log file and normalize it to the current CSV_FIELDS schema."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=CSV_FIELDS)

    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for fields in csv.reader(f):
            if not fields:
                continue
            row = _parse_row(fields)
            if row is not None:
                rows.append(row)

    df = pd.DataFrame(rows, columns=CSV_FIELDS)
    if df.empty:
        return df
    df["row_type"] = df["row_type"].fillna("sample")
    for col in NUMERIC_FIELDS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _render_charts(
    auto_latest: bool,
    selected_path_str: Optional[str],
    country: str,
    price_usd_per_kwh: float,
) -> None:
    if auto_latest:
        log_path = latest_log_file()
        if log_path is None:
            st.info(
                f"Waiting for data. Start the tracker in another terminal:\n\n"
                f"`python energy_tracker.py`\n\n"
                f"Each run creates a new file in `{LOGS_DIR}/`."
            )
            return
    else:
        if not selected_path_str:
            st.info("No log file selected.")
            return
        log_path = Path(selected_path_str)

    st.caption(f"Reading: `{log_path}`")
    df = read_log(log_path)
    samples = df[df["row_type"] == "sample"].dropna(subset=["power_w"])
    if samples.empty:
        st.info("This log file has no GPU samples yet.")
        return

    samples = samples.copy()
    samples["elapsed_min"] = samples["elapsed_s"] / 60
    samples["cost_usd_cumulative"] = samples["energy_wh_cumulative"] / 1000 * price_usd_per_kwh

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current power", f"{samples['power_w'].iloc[-1]:.1f} W")
    col2.metric("GPU load", f"{samples['gpu_util_pct'].iloc[-1]:.0f} %")
    col3.metric("Total energy", f"{samples['energy_wh_cumulative'].iloc[-1] / 1000:.4f} kWh")
    col4.metric(f"Total cost ({country})", f"${samples['cost_usd_cumulative'].iloc[-1]:.4f}")

    st.subheader("Power consumption (W) over time")
    st.line_chart(samples.set_index("elapsed_min")["power_w"])

    st.subheader("GPU utilization (%) over time")
    st.line_chart(samples.set_index("elapsed_min")["gpu_util_pct"])

    st.subheader(f"Cumulative cost (USD) — {country} rate ({price_usd_per_kwh:.4f} $/kWh)")
    st.line_chart(samples.set_index("elapsed_min")["cost_usd_cumulative"])

    calls = df[df["row_type"] == "ollama_call"].dropna(subset=["model", "call_start_ts", "call_end_ts"])
    if not calls.empty:
        calls = attribute_calls(samples, calls).sort_values("call_start_ts")
        attributed_energy = calls["energy_wh_call"].dropna().sum()
        unattributed = int(calls["energy_wh_call"].isna().sum())

        st.subheader("🦙 Ollama usage")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Calls", len(calls))
        c2.metric("Total tokens", f"{int(calls['total_tokens'].sum()):,}")
        c3.metric("Avg speed", f"{calls['tps'].mean():.1f} tok/s")
        c4.metric("Energy equivalent", format_rowing_equivalent(attributed_energy))

        if unattributed:
            st.caption(
                f"⚠️ {unattributed} call(s) couldn't be matched to GPU samples "
                f"(the tracker wasn't running for that window)."
            )

        table = calls[[
            "model", "prompt_tokens", "completion_tokens", "total_tokens",
            "tps", "energy_wh_call", "avg_gpu_util_call",
        ]].rename(columns={
            "model": "Model",
            "prompt_tokens": "Prompt tok.",
            "completion_tokens": "Completion tok.",
            "total_tokens": "Total tok.",
            "tps": "Tokens/s",
            "energy_wh_call": "Energy (Wh)",
            "avg_gpu_util_call": "Avg GPU load (%)",
        })
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.subheader("Generation speed (tokens/s) per call")
        st.bar_chart(calls.reset_index(drop=True)["tps"])


render_charts = st.fragment(run_every=refresh_s if live else None)(_render_charts)
render_charts(auto_latest, selected_path_str, country, prices[country])
