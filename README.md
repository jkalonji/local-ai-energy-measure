# Local AI Energy Measure

Tracks the real GPU power draw and energy cost of running local LLMs (Ollama) on
an NVIDIA GPU, and shows it in a live Streamlit dashboard: power over time,
cumulative electricity cost (5 countries), and per-Ollama-call token/TPS/energy
stats with a rowing-machine energy analogy.

## Requirements

- NVIDIA GPU + driver with `nvidia-smi` working
- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally, if you want the
  token/TPS tracking (the GPU power tracker alone works without it)

## Install

```bash
git clone https://github.com/jkalonji/local-ai-energy-measure.git
cd local-ai-energy-measure
pip install -r requirements.txt
```

## Usage

Three independent pieces, plus benchmark scripts. Run what you need.

### 1. GPU power/energy tracker

```bash
python energy_tracker.py
```

Samples GPU power draw and utilization every second (NVML) and writes them to
a new timestamped CSV under `logs/` (one file per run — nothing is
overwritten or appended across runs). `Ctrl+C` to stop.

### 2. Ollama proxy (optional, for token/TPS/energy-per-call stats)

```bash
python ollama_proxy.py
```

Transparent reverse proxy in front of Ollama (default: listens on `:11435`,
forwards to `:11434`). Point any Ollama client at it instead of talking to
Ollama directly:

```bash
OLLAMA_HOST=http://localhost:11435 ollama run llama3.1
```

It passes every request through unchanged, and for `/api/generate` /
`/api/chat` it also extracts token counts and tokens/sec and appends an
`ollama_call` row to the currently active tracker log, so the dashboard can
attribute GPU energy/load to that specific call.

### 3. Dashboard

```bash
streamlit run dashboard.py
```

Opens in your browser. Follows the most recent log file automatically (or
pick one manually from the sidebar). Shows power/utilization curves,
cumulative cost in a country of your choice (France, USA, China, DR Congo,
Brazil — toggle in the sidebar), and, if the proxy was used, per-call
token/TPS/energy stats.

### 4. Benchmarks

Scripts under `benchmarks/` measure energy per model. They need the tracker and the proxy
running (see above).

```
benchmarks/
  models.yaml              # model list + named sets, shared by every benchmark
  common.py                # shared helpers (power window, warm-up, Ollama capabilities...)
  without_harness/         # direct /api/generate calls, no agent loop
results/
  without_harness/         # CSV/Markdown/plots + notes.yaml (hand-written commentary)
```

**Without a harness** — cost of generating 1M tokens, per model:

```bash
python benchmarks/without_harness/benchmark_1M_tokens.py --set round_3_retry
python benchmarks/without_harness/benchmark_1M_tokens.py --models gemma3:1b,qwen3:4b
python benchmarks/without_harness/benchmark_1M_tokens.py --all           # slow: every model
python benchmarks/without_harness/benchmark_1M_tokens.py --report-only   # rebuild .md/.csv, no GPU
```

A run re-measures the selected models (their previous row is replaced) and merges the rest
into `results/without_harness/benchmark_1M_tokens.{csv,md}`. Nothing runs by default: pick
a selection explicitly. Model lists live in `benchmarks/models.yaml`; commentary rendered
into the report lives in `results/without_harness/notes.yaml`.

Tool/thinking/vision support of a model is read from Ollama, not stored in the repo:

```python
from benchmarks import common
common.model_capabilities("qwen3:4b")   # ['completion', 'tools', 'thinking']
```

Unit tests: `python -m unittest discover -s tests -t .`

### Windows: one-click launcher

`start_monitoring.bat` opens all of the above in 4 separate terminal windows
(tracker, proxy, dashboard, plus a terminal pre-configured with
`OLLAMA_HOST` pointed at the proxy so you can just type `ollama run ...`).
Double-click it, or run it from a terminal.

## How it works

- `energy_tracker.py` reads `nvmlDeviceGetPowerUsage` / `nvmlDeviceGetUtilizationRates`
  on GPU index 0 once a second and integrates power into Wh.
- `ollama_proxy.py` and `energy_tracker.py` write to the same CSV
  (process-safe append via a simple lock file) using a shared sparse schema
  (`row_type`: `sample` or `ollama_call`), so the dashboard can correlate an
  Ollama call's timestamps with the GPU samples around it.
- Electricity prices are a curated table (`config/electricity_prices.json`)
  converted to USD live via the free [frankfurter.app](https://frankfurter.app)
  (ECB) exchange rates, fetched once per dashboard session.

## Known limits

- **Single GPU, index 0 only.** No multi-GPU support.
- **NVML power reading, not wall-socket power.** It's `nvidia-smi`-level GPU
  package power, not total system draw (CPU, RAM, PSU losses aren't
  included).
- **Electricity prices are static estimates, not live tariffs.** Curated
  once from public 2024 sources (EDF, EIA, ANEEL, etc.), not fetched
  live — only the currency conversion to USD is live. DR Congo is priced
  directly in USD (its currency isn't tracked by the exchange-rate API), so
  it doesn't benefit from the live conversion and its number is the
  least reliable of the five.
- **The rowing-machine energy equivalent is illustrative, not rigorous** —
  a rough calorie-to-Wh conversion, not a scientific benchmark.
- **VRAM is shared with whatever else Ollama has loaded.** Ollama keeps a
  model resident in VRAM for ~5 minutes after last use (`keep_alive`). We
  hit a real `cudaMalloc failed: out of memory` trying to load an 8B model
  while a previously-used 3B model was still resident — not because of its
  size, but because of its default 32K context length (large KV-cache). The
  proxy and tracker themselves use no GPU memory (verified via
  `nvidia-smi --query-compute-apps`); if you hit this, run `ollama ps` /
  `curl localhost:11434/api/ps` to see what's loaded and `ollama stop
  <model>` to free it before loading another.
- **`start_monitoring.bat` is Windows-only.** On Linux/macOS, run the three
  `python`/`streamlit` commands manually in separate terminals.
- **Log file locking is a simple retry loop** (`os.O_CREAT | os.O_EXCL`),
  not a production-grade lock — fine for the tracker + one proxy writing to
  the same file, stress-tested to 200 concurrent writes, but not designed
  for many more concurrent writers.
