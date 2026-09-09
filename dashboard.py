"""Streamlit dashboard for the GPU energy tracker.

Reads the CSV log written by energy_tracker.py and displays:
- a power-over-time curve (live if the tracker is currently running)
- a cumulative cost curve (USD), based on a selectable country's
  electricity price (see pricing.py / config/electricity_prices.json)

Run with:
    streamlit run dashboard.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from pricing import get_prices_usd_per_kwh

st.set_page_config(page_title="GPU Energy Dashboard", page_icon="⚡", layout="wide")
st.title("⚡ Suivi de consommation énergétique GPU")

with st.sidebar:
    st.header("Réglages")
    log_path_str = st.text_input("Fichier de log CSV", value="energy_log.csv")
    live = st.checkbox("Rafraîchissement live", value=True)
    refresh_s = st.slider("Intervalle de rafraîchissement (s)", 1, 30, 3, disabled=not live)


@st.cache_resource
def load_prices() -> dict[str, float]:
    """Fetch USD/kWh per country once per dashboard session."""
    return get_prices_usd_per_kwh()


prices = load_prices()

with st.sidebar:
    country = st.selectbox("Pays (tarif électricité)", options=list(prices.keys()), index=0)
    st.caption(f"Tarif retenu : {prices[country]:.4f} $/kWh")
    with st.expander("Tous les tarifs (USD/kWh)"):
        for c, p in prices.items():
            st.write(f"{c} : {p:.4f} $/kWh")


def read_log(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["timestamp", "elapsed_s", "power_w", "energy_wh_cumulative"])
    return pd.read_csv(path, on_bad_lines="skip", engine="python")


def _render_charts(log_path_str: str, country: str, price_usd_per_kwh: float) -> None:
    df = read_log(Path(log_path_str))
    if df.empty:
        st.info(
            f"En attente de données. Lance le tracker dans un autre terminal :\n\n"
            f"`python energy_tracker.py --log-file {log_path_str}`"
        )
        return

    df["elapsed_min"] = df["elapsed_s"] / 60
    df["cost_usd_cumulative"] = df["energy_wh_cumulative"] / 1000 * price_usd_per_kwh

    col1, col2, col3 = st.columns(3)
    col1.metric("Puissance actuelle", f"{df['power_w'].iloc[-1]:.1f} W")
    col2.metric("Énergie totale", f"{df['energy_wh_cumulative'].iloc[-1] / 1000:.4f} kWh")
    col3.metric(f"Coût total ({country})", f"${df['cost_usd_cumulative'].iloc[-1]:.4f}")

    st.subheader("Consommation électrique (W) au cours du temps")
    st.line_chart(df.set_index("elapsed_min")["power_w"])

    st.subheader(f"Coût cumulé (USD) — tarif {country} ({price_usd_per_kwh:.4f} $/kWh)")
    st.line_chart(df.set_index("elapsed_min")["cost_usd_cumulative"])


render_charts = st.fragment(run_every=refresh_s if live else None)(_render_charts)
render_charts(log_path_str, country, prices[country])
