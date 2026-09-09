import argparse
import time
from pathlib import Path

from pynvml import (
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetPowerUsage,
    nvmlDeviceGetUtilizationRates,
    nvmlInit,
)

from csv_log import append_row
from log_paths import new_log_path


def track(log_path: Path, interval_s: float = 1.0) -> None:
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)
    energy_wh = 0.0
    t0 = time.time()

    print(f"Logging to {log_path}")

    try:
        while True:
            p = nvmlDeviceGetPowerUsage(handle) / 1000  # mW -> W
            util = nvmlDeviceGetUtilizationRates(handle).gpu  # %
            time.sleep(interval_s)
            energy_wh += p * (interval_s / 3600)
            elapsed = time.time() - t0

            append_row(log_path, {
                "row_type": "sample",
                "timestamp": f"{time.time():.3f}",
                "elapsed_s": f"{elapsed:.3f}",
                "power_w": f"{p:.3f}",
                "gpu_util_pct": util,
                "energy_wh_cumulative": f"{energy_wh:.6f}",
            })

            print(f"\r{p:6.1f} W  |  {util:3.0f}%  |  {energy_wh:8.4f} Wh  |  "
                  f"avg {energy_wh * 3600 / elapsed:6.1f} W  |  "
                  f"{elapsed / 60:5.1f} min", end="")
    except KeyboardInterrupt:
        print(f"\nTotal: {energy_wh / 1000:.4f} kWh")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track GPU power/energy usage and log it to CSV.")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to the CSV file to write readings to. Defaults to a new "
             "timestamped file under logs/ (e.g. logs/energy_20250909_143000.csv), "
             "so every run gets its own file instead of reusing the previous one.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between two readings (default: 1.0).",
    )
    args = parser.parse_args()
    log_path = args.log_file if args.log_file is not None else new_log_path()
    track(log_path, args.interval)


if __name__ == "__main__":
    main()
