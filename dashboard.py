"""Streamlit dashboard for the GPU energy tracker.

Reads the CSV log(s) written by energy_tracker.py (and, if used,
ollama_proxy.py) and displays:
- a power-over-time and GPU-utilization-over-time curve (live if the
  tracker is currently running)
- a cumulative cost curve (USD), based on a selectable country's
  electricity price (see pricing.py / config/electricity_prices.json)

Each run of energy_tracker.py writes its own timestamped file under
logs/ (see log_paths.py). By default this dashboard always follows the
most recent one, so restarting the tracker automatically switches the
dashboard to the new run without any manual action.

Run with:
    streamlit run dashboard.py
"""

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from csv_log import CSV_FIELDS
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


def read_log(path: Path) -> pd.DataFrame:
    """Read a log file and normalize it to the current CSV_FIELDS schema.

    Older logs (written before row_type/gpu_util_pct/Ollama columns
    existed) only have timestamp/elapsed_s/power_w/energy_wh_cumulative;
    those are treated as all-"sample" rows with the newer columns empty.
    """
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=CSV_FIELDS)
    df = pd.read_csv(path, on_bad_lines="skip", engine="python")
    df = df.reindex(columns=CSV_FIELDS)
    if "row_type" in df.columns:
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


render_charts = st.fragment(run_every=refresh_s if live else None)(_render_charts)
render_charts(auto_latest, selected_path_str, country, prices[country])
