"""Electricity price table per country, converted to USD/kWh.

Local-currency prices are curated in config/electricity_prices.json.
Exchange rates to USD are fetched once (live) from frankfurter.app
(ECB reference rates, free, no API key). If the request fails (e.g. no
network), a fallback fixed rate table is used so the dashboard still works.
"""

import json
from pathlib import Path
from typing import Dict

import requests

CONFIG_PATH = Path(__file__).parent / "config" / "electricity_prices.json"
FX_API_URL = "https://api.frankfurter.app/latest"

# Fallback rates (units of local currency per 1 USD), used only if the live
# exchange-rate API call fails. Approximate, updated ~2024-2025.
FALLBACK_RATES_PER_USD = {
    "USD": 1.0,
    "EUR": 0.92,
    "CNY": 7.20,
    "BRL": 5.40,
}


def load_price_table() -> Dict[str, dict]:
    """Load the curated local-currency price table (excludes the _comment key)."""
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return {country: info for country, info in data.items() if not country.startswith("_")}


def fetch_usd_rates(currencies: list[str]) -> Dict[str, float]:
    """Fetch 'units of currency per 1 USD' for each currency, once, live.

    Falls back to a fixed table on any network/API error.
    """
    needed = sorted(c for c in set(currencies) if c != "USD")
    if not needed:
        return {"USD": 1.0}

    try:
        response = requests.get(
            FX_API_URL,
            params={"from": "USD", "to": ",".join(needed)},
            timeout=5,
        )
        response.raise_for_status()
        rates = response.json()["rates"]
        rates["USD"] = 1.0
        return rates
    except (requests.RequestException, KeyError, ValueError):
        return {c: FALLBACK_RATES_PER_USD.get(c, 1.0) for c in needed + ["USD"]}


def get_prices_usd_per_kwh() -> Dict[str, float]:
    """Return {country: price_usd_per_kwh} for every country in the config."""
    table = load_price_table()
    currencies = [info["currency"] for info in table.values()]
    rates_per_usd = fetch_usd_rates(currencies)

    prices_usd = {}
    for country, info in table.items():
        rate = rates_per_usd.get(info["currency"], FALLBACK_RATES_PER_USD.get(info["currency"], 1.0))
        prices_usd[country] = info["price_per_kwh"] / rate
    return prices_usd


if __name__ == "__main__":
    for country, price in get_prices_usd_per_kwh().items():
        print(f"{country:12s} {price:.4f} USD/kWh")
