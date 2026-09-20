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

It also records every power sample the NVIDIA driver buffers (~50 per second,
one per 20 ms) in `logs/hires/<same file name>`, about 5 MB per hour. That file
is what [`hires_report.py`](#4-energy-of-every-tenth-of-a-second) reads.
`--no-hires` turns it off. Stop it with `Ctrl+C` so the last half second of
samples is flushed.

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

It passes every request through unchanged, and for the generation endpoints it
also extracts token counts and appends an `ollama_call` row to the currently
active tracker log, so GPU energy/load can be attributed to that specific call:

| Endpoint | Tokens | Speed (tok/s) |
|---|---|---|
| `/api/generate`, `/api/chat` (Ollama native) | reported by Ollama | logged |
| `/v1/chat/completions`, `/v1/completions` (OpenAI-compatible) | `usage` field | not logged (the API reports no generation time) |

A streaming OpenAI-compatible client only receives `usage` if it sends
`stream_options.include_usage`. The proxy never edits requests, so without it the
completion count is the number of streamed content chunks (`tokens_source` =
`chunk_count` in the CSV, prompt tokens unknown). Agent harnesses use the
OpenAI-compatible API: point their base URL at `http://localhost:11435/v1`.

### 3. Dashboard

```bash
streamlit run dashboard.py
```

Opens in your browser. Follows the most recent log file automatically (or
pick one manually from the sidebar). Shows power/utilization curves,
cumulative cost in a country of your choice (France, USA, China, DR Congo,
Brazil — toggle in the sidebar), and, if the proxy was used, per-call
token/TPS/energy stats.

### 4. Energy of every tenth of a second

```bash
python hires_report.py --call -1            # last logged Ollama call
python hires_report.py --last 30            # the last 30 seconds
python hires_report.py --start 1789910044.2 --end 1789910047.0   # epoch seconds
python hires_report.py --run-id my-run      # a "run" row written by a benchmark runner
python hires_report.py --call 2 --bin-ms 100 --out bins.csv      # save every bin
```

Prints the window's total energy, then one row per 100 ms bin (change with
`--bin-ms`): `energy_j`, `avg_power_w`, `covered_s` (how much of the bin has power
samples) and `gpu_util_pct`. For a `--run-id` it also splits the energy into time
*inside* model calls and time *between* them (GPU waiting on tools: the harness
overhead), with the token counts.

- **Energy** is the integral of the driver's raw ~20 ms power samples, linearly
  interpolated, so the energies of consecutive bins add up exactly to the energy of
  the whole window. Samples lost by the driver are never integrated across: they
  show up as `covered_s` below the bin length, and the report warns.
- **GPU utilization cannot be resolved to 100 ms.** The driver reports one value
  per 200 ms (the mean over the 200 ms ending at its timestamp), so two bins share
  each value.
- Absolute accuracy is NVML's; it was **not** checked against an external power
  meter.

A "run" row is a normal log row with `row_type=run`, the run window in
`call_start_ts`/`call_end_ts`, and `harness`, `run_id`, `task_id`, `model` set;
write it with `csv_log.append_row`. Calls belong to a run by time overlap.

### 5. Benchmarks

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

**Context window.** `without_harness` forces `num_ctx=8192` on every call. Runs *with* a
harness use a fixed **32768** (`common.HARNESS_NUM_CTX`) so results are comparable across
harnesses and long agent prompts are not silently truncated (Ollama drops what exceeds
`num_ctx`). Harnesses call the OpenAI-compatible `/v1` API, which cannot carry `num_ctx`,
and a model loaded with another context is reloaded at the server default. That default
can be a model's full window: `qwen3:4b` tries to allocate ~150 GB of KV cache and fails.
So the value is imposed on the server, and checked before a run:

```powershell
$env:OLLAMA_CONTEXT_LENGTH = 32768; ollama serve     # quit the Ollama app first
```

```python
common.require_context("qwen3:4b")   # raises with the fix if the model does not run at 32768
```

Explicit `num_ctx` on native `/api/*` calls (the `without_harness` benchmark) still wins over
the server setting, so the two sections can share one Ollama.

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
  (`row_type`: `sample`, `ollama_call` or `run`), so the dashboard can correlate an
  Ollama call's timestamps with the GPU samples around it. Older logs (4 or 13
  columns) stay readable: rows are parsed by width, and appends to an old file keep
  its width.
- `gpu_samples.py` drains the driver's own power-sample buffer (20 ms samples with
  driver timestamps, ~2.4 s deep) every 0.5 s in a background thread of the tracker.
  Energy over any window is the integral of those samples.
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
- **The 1 Hz `power_w` / `energy_wh_cumulative` columns are a coarse signal.** On
  the RTX 5060 Ti (Blackwell), `nvmlDeviceGetPowerUsage` is a 1 s trailing average
  refreshed twice a second, so it smears short events: the per-call energy the
  dashboard derives from it is heavily underestimated for calls of a second or
  less. Use `hires_report.py` for exact short windows. The effect on the published
  `without_harness` benchmark (mean power over 1 Hz samples) has not been
  quantified.
- **The hardware energy counter is unusable on this GPU.**
  `nvmlDeviceGetTotalEnergyConsumption` returned a near-constant ~340 W
  regardless of load, so energy is always integrated from power samples.
- **Utilization has 200 ms resolution**, not 100 ms (see section 4).
- **The hi-res file grows ~5 MB per hour** of tracking. A hard kill of the
  tracker (not `Ctrl+C`) can lose the last ≤0.5 s of samples. If the tracker is
  stalled for more than ~2 s the driver buffer overflows; the gap is reported and
  excluded from the integral.
- **Absolute accuracy is NVML's**, not checked against an external wattmeter.
- **Measuring an agent harness through the proxy** requires pointing the
  harness's OpenAI-compatible base URL at `http://localhost:11435/v1`, and
  ideally enabling usage reporting in streaming mode (`include_usage`), otherwise
  token counts are chunk-count estimates.
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
