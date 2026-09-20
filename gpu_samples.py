"""Sub-second GPU power capture, and exact energy over any time window.

Why not `nvmlDeviceGetPowerUsage` (what energy_tracker.py logs at 1 Hz)?
Measured on an RTX 5060 Ti (driver 591.86, NVML 13):
- GetPowerUsage and the "instant"/"average" field values only refresh
  every 500 ms, and GetPowerUsage is a 1-second trailing average: a load
  step takes ~1 s to show up.
- The hardware energy counter (nvmlDeviceGetTotalEnergyConsumption) is
  unusable: it advances ~33.9 J per 100 ms whether the GPU is idle or at
  150 W.
- The driver's own sample buffer (NVML_TOTAL_POWER_SAMPLES) holds one power
  reading every ~20 ms with a driver timestamp (Unix epoch, microseconds)
  and follows a load step within ~45 ms. It holds only the last ~2.4 s, so
  it must be drained faster than that (HiresRecorder drains every 0.5 s).
- NVML_GPU_UTILIZATION_SAMPLES holds one reading per 200 ms; each value is
  the mean utilization over the 200 ms that end at its timestamp. GPU
  utilization therefore cannot be resolved below 200 ms.

The recorder appends every driver sample to a sibling file of the tracker
log, under hires/. Energy over any window is then the integral of those
readings: the values are raw driver samples, and the integration rule
(linear interpolation between neighbouring samples) is fixed and additive,
so the energies of consecutive bins add up to the energy of the whole
window. Absolute accuracy is NVML's, not verified against an external meter.
"""

import csv
import sys
import threading
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Tuple

import numpy as np
import pandas as pd

HIRES_FIELDS = ["kind", "timestamp_us", "value"]
KIND_POWER = "power_mw"
KIND_UTIL = "util_pct"

DRAIN_INTERVAL_S = 0.5  # driver buffer holds ~2.4 s; losses were observed at a 2.6 s interval
MAX_GAP_US = 100_000  # neighbouring power samples further apart than this are not integrated
UTIL_WINDOW_US = 200_000  # each utilization value averages the 200 ms ending at its timestamp
DEFAULT_BIN_US = 100_000

Sample = Tuple[int, int]  # (timestamp_us, value)


def hires_path_for(log_path: Path) -> Path:
    """Path of the hi-res sample file that goes with tracker log `log_path`.

    It lives in a hires/ subfolder so that log_paths.list_log_files(), which
    globs logs/energy_*.csv, never mistakes it for a tracker log.
    """
    return log_path.parent / "hires" / log_path.name


class SampleSource(Protocol):
    """Where HiresRecorder reads driver samples from."""

    def power(self, after_us: int) -> List[Sample]:
        """Power samples (timestamp_us, milliwatts) newer than `after_us`, oldest first."""

    def utilization(self, after_us: int) -> List[Sample]:
        """Utilization samples (timestamp_us, percent) newer than `after_us`, oldest first."""


class NvmlSampler:
    """SampleSource over the NVML sample buffers of one GPU."""

    def __init__(self, handle) -> None:
        import pynvml

        self._nvml = pynvml
        self._handle = handle

    def _fetch(self, kind: int, after_us: int) -> List[Sample]:
        value_type, samples = self._nvml.nvmlDeviceGetSamples(self._handle, kind, after_us)
        is_uint = value_type == self._nvml.NVML_VALUE_TYPE_UNSIGNED_INT
        return [
            (int(s.timeStamp), int(s.sampleValue.uiVal if is_uint else s.sampleValue.ullVal))
            for s in samples
        ]

    def power(self, after_us: int) -> List[Sample]:
        return self._fetch(self._nvml.NVML_TOTAL_POWER_SAMPLES, after_us)

    def utilization(self, after_us: int) -> List[Sample]:
        return self._fetch(self._nvml.NVML_GPU_UTILIZATION_SAMPLES, after_us)


def _append_rows(path: Path, rows: List[Tuple[str, int, int]]) -> None:
    """Append rows to the hi-res file. Single writer only: the recorder thread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(HIRES_FIELDS)
        writer.writerows(rows)


class HiresRecorder:
    """Background thread that drains the driver sample buffers into a CSV file.

    The first drain also returns whatever the driver buffered before the
    recorder started (up to ~2.4 s of power, ~14 s of utilization).
    """

    def __init__(self, source: SampleSource, path: Path, drain_interval_s: float = DRAIN_INTERVAL_S,
                 warn: Callable[[str], None] = lambda m: print(m, file=sys.stderr)) -> None:
        self._source = source
        self._path = path
        self._interval = drain_interval_s
        self._warn = warn
        self._last_ts = {KIND_POWER: 0, KIND_UTIL: 0}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None

    def drain(self) -> int:
        """Write every sample newer than the last drain; returns the number written."""
        rows: List[Tuple[str, int, int]] = []
        for kind, fetch in ((KIND_POWER, self._source.power), (KIND_UTIL, self._source.utilization)):
            samples = fetch(self._last_ts[kind])
            if not samples:
                continue
            first_ts = samples[0][0]
            previous = self._last_ts[kind]
            if kind == KIND_POWER and previous and first_ts - previous > MAX_GAP_US:
                self._warn(f"[hires] lost power samples: {(first_ts - previous) / 1000:.0f} ms gap")
            self._last_ts[kind] = max(previous, samples[-1][0])
            rows.extend((kind, ts, value) for ts, value in samples)
        if rows:
            _append_rows(self._path, rows)
        return len(rows)

    def _drain_reporting_errors(self) -> None:
        try:
            self.drain()
            self._last_error = None
        except Exception as e:  # noqa: BLE001 - keep recording; report each new failure once
            message = f"{type(e).__name__}: {e}"
            if message != self._last_error:
                self._warn(f"[hires] drain failed: {message}")
                self._last_error = message

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(self._interval):
                self._drain_reporting_errors()

        self._thread = threading.Thread(target=loop, name="hires-recorder", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the thread and write the samples buffered since the last drain."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self._drain_reporting_errors()


def read_hires(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load a hi-res file as (power, utilization) frames sorted by timestamp.

    power has columns timestamp_us, power_mw; utilization has timestamp_us,
    util_pct. Duplicate timestamps are dropped.
    """
    if not path.exists():
        raise FileNotFoundError(f"No hi-res sample file at {path} (was the tracker run with hi-res enabled?)")
    df = pd.read_csv(path)

    def part(kind: str, column: str) -> pd.DataFrame:
        sub = df[df["kind"] == kind][["timestamp_us", "value"]].rename(columns={"value": column})
        sub = sub.drop_duplicates("timestamp_us").sort_values("timestamp_us").reset_index(drop=True)
        sub["timestamp_us"] = sub["timestamp_us"].astype("int64")
        return sub

    return part(KIND_POWER, "power_mw"), part(KIND_UTIL, "util_pct")


def energy_between(ts_us: np.ndarray, power_mw: np.ndarray, start_us: int, end_us: int,
                   max_gap_us: int = MAX_GAP_US) -> Tuple[float, float]:
    """Energy (joules) drawn in [start_us, end_us), and the seconds of it that samples cover.

    Power is linearly interpolated between neighbouring samples, so the value
    is additive over adjacent windows. Spans between two samples further apart
    than `max_gap_us` are skipped (lost samples), which shows up as covered
    seconds shorter than the window.
    """
    ts = np.asarray(ts_us, dtype=np.float64)
    watts = np.asarray(power_mw, dtype=np.float64) / 1000.0
    if end_us <= start_us or len(ts) < 2:
        return 0.0, 0.0
    lo = max(int(np.searchsorted(ts, start_us, side="right")) - 1, 0)
    hi = min(int(np.searchsorted(ts, end_us, side="left")), len(ts) - 1)
    if hi <= lo:
        return 0.0, 0.0
    t0, t1 = ts[lo:hi], ts[lo + 1:hi + 1]
    w0, w1 = watts[lo:hi], watts[lo + 1:hi + 1]
    a = np.maximum(t0, start_us)
    b = np.minimum(t1, end_us)
    valid = (b > a) & ((t1 - t0) <= max_gap_us)
    with np.errstate(divide="ignore", invalid="ignore"):  # duplicate timestamps give a 0-length, invalid span
        slope = (w1 - w0) / (t1 - t0)
        pa = w0 + slope * (a - t0)
        pb = w0 + slope * (b - t0)
    seconds = np.where(valid, b - a, 0.0) / 1e6
    joules = np.where(valid, (pa + pb) / 2.0 * (b - a) / 1e6, 0.0)
    return float(joules.sum()), float(seconds.sum())


def bin_energy(power: pd.DataFrame, util: pd.DataFrame, start_us: int, end_us: int,
               bin_us: int = DEFAULT_BIN_US) -> pd.DataFrame:
    """Energy and utilization of every `bin_us` bin between start_us and end_us.

    Columns: t_offset_s (bin start, seconds after start_us), bin_start_us,
    energy_j, avg_power_w (energy over covered time), covered_s, gpu_util_pct.
    gpu_util_pct is the 200 ms utilization reading whose window contains the
    bin centre (NaN if none does): with 100 ms bins, two bins share a reading.
    """
    p_ts = power["timestamp_us"].to_numpy()
    p_mw = power["power_mw"].to_numpy()
    u_ts = util["timestamp_us"].to_numpy()
    u_val = util["util_pct"].to_numpy()
    rows = []
    for a in range(int(start_us), int(end_us), int(bin_us)):
        b = min(a + bin_us, end_us)
        joules, covered = energy_between(p_ts, p_mw, a, b)
        centre = (a + b) / 2
        i = int(np.searchsorted(u_ts, centre, side="left"))
        util_pct = float(u_val[i]) if i < len(u_ts) and u_ts[i] - UTIL_WINDOW_US <= centre else float("nan")
        rows.append({
            "t_offset_s": (a - start_us) / 1e6,
            "bin_start_us": a,
            "energy_j": joules,
            "avg_power_w": joules / covered if covered > 0 else float("nan"),
            "covered_s": covered,
            "gpu_util_pct": util_pct,
        })
    return pd.DataFrame(rows, columns=[
        "t_offset_s", "bin_start_us", "energy_j", "avg_power_w", "covered_s", "gpu_util_pct",
    ])
