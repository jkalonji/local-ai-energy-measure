"""Benchmark "cout de generation de 1M tokens" pour chaque modele Ollama installe.

Cas SANS harnais : appel direct a /api/generate, un seul prompt, pas de boucle d'agent.

Meme methodologie que le test manuel gemma4 :
- warm-up (petite generation) pour charger le modele en VRAM avant la mesure
- vrai appel avec le prompt de benchmark, via le proxy logging (port 11435)
  pour recuperer eval_count / eval_duration / tps depuis la reponse Ollama
- lecture du CSV du tracker GPU (energy_tracker.py) sur la fenetre de temps
  exacte de l'appel pour la puissance moyenne
- extrapolation a 1M tokens generes : temps, energie (kWh), cout (5 pays),
  equivalent rameur (human_analogy.py)
- `ollama stop <model>` apres chaque modele pour liberer la VRAM avant le suivant

Ecrit/actualise results/without_harness/benchmark_1M_tokens.csv et .md apres CHAQUE
modele (progres visible meme si le script est interrompu).

Usage (energy_tracker.py et ollama_proxy.py doivent tourner) :
    python benchmarks/without_harness/benchmark_1M_tokens.py --set round_3_retry
    python benchmarks/without_harness/benchmark_1M_tokens.py --models gemma3:1b,qwen3:4b
    python benchmarks/without_harness/benchmark_1M_tokens.py --all
    python benchmarks/without_harness/benchmark_1M_tokens.py --report-only   # sans GPU

Les modeles et leurs sous-ensembles vivent dans benchmarks/models.yaml, les
commentaires rediges a la main dans results/without_harness/notes.yaml.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from benchmarks import common  # noqa: E402
from human_analogy import rowing_minutes_equivalent  # noqa: E402
from pricing import get_prices_usd_per_kwh  # noqa: E402

PROMPT = "écris moi l'histoire la plus longue possible"
PER_MODEL_TIMEOUT_S = 40 * 60  # garde-fou technique : evite qu'un modele bloque le script des heures
NUM_CTX = 8192  # force le meme contexte pour tous les modeles : comparaison equitable et
# evite le bug "KV-cache alloue pour le contexte max par defaut (128k-262k) -> OOM"
# rencontre sur pres de la moitie des modeles avec le contexte par defaut de chacun.
RESULTS_DIR = REPO_ROOT / "results" / "without_harness"
CSV_OUT = RESULTS_DIR / "benchmark_1M_tokens.csv"
MD_OUT = RESULTS_DIR / "benchmark_1M_tokens.md"
NOTES_FILE = RESULTS_DIR / "notes.yaml"


def load_notes() -> dict:
    """Hand-written commentary from notes.yaml; every key is optional."""
    notes = {}
    if NOTES_FILE.exists():
        with NOTES_FILE.open(encoding="utf-8") as f:
            notes = yaml.safe_load(f) or {}
    return {
        "suspect_notes": notes.get("suspect_notes", {}),
        "anomalies_section": notes.get("anomalies_section", ""),
        "observations_section": notes.get("observations_section", ""),
    }


def run_benchmark_for_model(model: str, prices) -> dict:
    print(f"\n=== {model} ===", flush=True)
    print("  warm-up...", flush=True)
    common.warmup(model, NUM_CTX)
    time.sleep(1.0)

    print("  generation (prompt: 'ecris moi l'histoire la plus longue possible')...", flush=True)
    start_ts = time.time()
    try:
        resp = requests.post(
            f"{common.PROXY_URL}/api/generate",
            json={"model": model, "prompt": PROMPT, "stream": False, "options": {"num_ctx": NUM_CTX}},
            timeout=PER_MODEL_TIMEOUT_S,
        )
        end_ts = time.time()
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        end_ts = time.time()
        print(f"  [ERREUR] {model}: {e}", flush=True)
        common.ollama_stop(model)
        return {"model": model, "error": str(e)}

    eval_count = data.get("eval_count", 0) or 0
    eval_duration_s = (data.get("eval_duration", 0) or 0) / 1e9
    prompt_tokens = data.get("prompt_eval_count", 0) or 0
    tps = eval_count / eval_duration_s if eval_duration_s > 0 else 0.0
    story_chars = len(data.get("response", ""))

    log_path = common.latest_log_file()
    avg_power, n_samples = common.avg_power_in_window(log_path, start_ts, end_ts)

    print(
        f"  -> {eval_count} tokens generes en {eval_duration_s:.1f}s "
        f"({tps:.1f} tok/s), puissance moy {avg_power} W ({n_samples} echantillons)",
        flush=True,
    )

    common.ollama_stop(model)

    result = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": eval_count,
        "story_chars": story_chars,
        "eval_duration_s": eval_duration_s,
        "tps": tps,
        "avg_power_w": avg_power,
        "n_power_samples": n_samples,
    }

    if tps > 0 and avg_power is not None:
        time_for_1m_s = 1_000_000 / tps
        energy_kwh_1m = avg_power * time_for_1m_s / 3600 / 1000
        result["time_for_1m_tokens_h"] = time_for_1m_s / 3600
        result["energy_kwh_1m_tokens"] = energy_kwh_1m
        result["rowing_min_1m_tokens"] = rowing_minutes_equivalent(energy_kwh_1m * 1000)
        for country, price in prices.items():
            result[f"cost_usd_1m_{country}"] = energy_kwh_1m * price
    else:
        result["error"] = "tps ou puissance indisponible (0 tokens generes ou pas d'echantillon GPU dans la fenetre)"

    return result


NUMERIC_FIELDS = [
    "prompt_tokens", "completion_tokens", "story_chars", "eval_duration_s",
    "tps", "avg_power_w", "n_power_samples", "time_for_1m_tokens_h",
    "energy_kwh_1m_tokens", "rowing_min_1m_tokens",
]
INT_FIELDS = {"prompt_tokens", "completion_tokens", "n_power_samples", "story_chars"}


def load_existing_results(prices) -> list:
    """Reload results/without_harness/benchmark_1M_tokens.csv (if present) as result dicts,
    so a new run can be merged with previous rounds instead of overwriting them."""
    if not CSV_OUT.exists():
        return []
    countries = list(prices.keys())
    numeric_fields = NUMERIC_FIELDS + [f"cost_usd_1m_{c}" for c in countries]
    results = []
    with CSV_OUT.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            r = {"model": row["model"]}
            if row.get("error"):
                r["error"] = row["error"]
            for field in numeric_fields:
                val = row.get(field, "")
                if val not in ("", None):
                    r[field] = int(float(val)) if field in INT_FIELDS else float(val)
            results.append(r)
    return results


def write_outputs(results: list, prices, notes: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    countries = list(prices.keys())

    # CSV : donnees completes, une ligne par modele
    fieldnames = [
        "model", "prompt_tokens", "completion_tokens", "story_chars",
        "eval_duration_s", "tps", "avg_power_w", "n_power_samples",
        "time_for_1m_tokens_h", "energy_kwh_1m_tokens", "rowing_min_1m_tokens",
    ] + [f"cost_usd_1m_{c}" for c in countries] + ["error"]
    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    # Markdown : tableau lisible, prix mis en avant = France
    lines = [
        "# Benchmark cout / energie - 1M tokens generes par modele",
        "",
        f"Prompt utilise pour tous les modeles : `{PROMPT}`",
        "",
        f"Methodologie : warm-up puis generation reelle, `num_ctx={NUM_CTX}` force pour "
        "TOUS les modeles (comparaison equitable, evite le bug d'OOM au chargement quand "
        "un modele part sur son contexte max par defaut - voir "
        "`benchmark_1M_tokens_unbounded_context.md` pour le run precedent sans cette limite). "
        "Puissance GPU moyenne mesuree pendant l'appel (NVML, RTX 5060 Ti), extrapolee a 1M "
        "tokens generes. Cout = electricite seule (hors amortissement materiel). 1 seul run par modele.",
        "",
        "| Modele | Tokens generes | Vitesse (tok/s) | Puissance moy. (W) | "
        "Energie / 1M tokens (kWh) | Cout / 1M tokens (France, $) | Equiv. rameur | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    has_anomalies = False
    for r in results:
        if not r.get("energy_kwh_1m_tokens"):
            lines.append(
                f"| {r['model']} | - | - | - | - | - | - | ERREUR: {r.get('error', 'inconnue')} |"
            )
            has_anomalies = True
            continue
        rowing_min = r["rowing_min_1m_tokens"]
        rowing_str = f"{rowing_min:.0f} min" if rowing_min < 60 else f"{rowing_min / 60:.1f} h"
        note = notes["suspect_notes"].get(r["model"])
        if note:
            note = f"⚠️ {note}"
            has_anomalies = True
        else:
            note = f"{r['story_chars']} caracteres generes"
        lines.append(
            f"| {r['model']} | {r['completion_tokens']} | {r['tps']:.1f} | "
            f"{r['avg_power_w']:.1f} | {r['energy_kwh_1m_tokens']:.4f} | "
            f"{r['cost_usd_1m_France']:.4f} | {rowing_str} | {note} |"
        )

    if has_anomalies and notes["anomalies_section"]:
        lines += ["", notes["anomalies_section"]]

    if notes["observations_section"]:
        lines += ["", notes["observations_section"]]

    lines += ["", "## Cout par pays (USD / 1M tokens generes)", "",
              "| Modele | " + " | ".join(countries) + " |", "|---|" + "---|" * len(countries)]
    for r in results:
        if not r.get("energy_kwh_1m_tokens"):
            continue
        vals = " | ".join(f"{r[f'cost_usd_1m_{c}']:.4f}" for c in countries)
        lines.append(f"| {r['model']} | {vals} |")

    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(models_config: dict) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cost/energy per 1M generated tokens, per Ollama model (no harness).")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--set", dest="set_name", choices=list(models_config["sets"]),
                           help="run a named set from benchmarks/models.yaml")
    selection.add_argument("--models", help="comma-separated model names to run")
    selection.add_argument("--all", action="store_true", help="run every model in benchmarks/models.yaml")
    selection.add_argument("--report-only", action="store_true",
                           help="rewrite the .csv/.md from the existing .csv without running anything")
    args = parser.parse_args()
    if not (args.set_name or args.models or args.all or args.report_only):
        parser.error("choose what to run: --set, --models, --all or --report-only")
    return args


def main() -> None:
    models_config = common.load_models_file()
    args = parse_args(models_config)

    prices = get_prices_usd_per_kwh()
    print("Prix electricite (USD/kWh):", prices, flush=True)
    notes = load_notes()
    results = load_existing_results(prices)

    if args.report_only:
        write_outputs(results, prices, notes)
        print(f"Rapport regenere depuis {CSV_OUT}", flush=True)
        return

    if args.set_name:
        models = common.model_set(models_config, args.set_name)
    elif args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = common.all_model_names(models_config)

    # Les modeles cibles de ce run sont retestes meme s'ils ont deja un resultat
    # (ex. relance suite a une mesure trop fragile) : on jette leur ancienne ligne.
    results = [r for r in results if r["model"] not in models]
    tested_already = {r["model"] for r in results}
    print(f"Resultats existants rechauffes pour {len(results)} modele(s): {sorted(tested_already)}", flush=True)

    for model in models:
        if model in tested_already:
            print(f"\n=== {model} deja teste, on saute ===", flush=True)
            continue
        r = run_benchmark_for_model(model, prices)
        results.append(r)
        write_outputs(results, prices, notes)  # sauvegarde incrementale apres chaque modele

    print(f"\nTermine. Resultats dans {CSV_OUT} et {MD_OUT}", flush=True)


if __name__ == "__main__":
    main()
