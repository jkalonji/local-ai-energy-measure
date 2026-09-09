import argparse
import csv
import time
from pathlib import Path

from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetPowerUsage, nvmlInit

CSV_FIELDS = ["timestamp", "elapsed_s", "power_w", "energy_wh_cumulative"]


def track(log_path: Path, interval_s: float = 1.0) -> None:
    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)
    energy_wh = 0.0
    t0 = time.time()

    is_new_file = not log_path.exists()
    log_file = log_path.open("a", newline="", encoding="utf-8")
    writer = csv.writer(log_file)
    if is_new_file:
        writer.writerow(CSV_FIELDS)
        log_file.flush()

    try:
        while True:
            p = nvmlDeviceGetPowerUsage(handle) / 1000  # mW -> W
            time.sleep(interval_s)
            energy_wh += p * (interval_s / 3600)
            elapsed = time.time() - t0

            writer.writerow([time.time(), f"{elapsed:.3f}", f"{p:.3f}", f"{energy_wh:.6f}"])
            log_file.flush()

            print(f"\r{p:6.1f} W  |  {energy_wh:8.4f} Wh  |  "
                  f"avg {energy_wh * 3600 / elapsed:6.1f} W  |  "
                  f"{elapsed / 60:5.1f} min", end="")
    except KeyboardInterrupt:
        print(f"\nTotal: {energy_wh / 1000:.4f} kWh")
    finally:
        log_file.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Track GPU power/energy usage and log it to CSV.")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("energy_log.csv"),
        help="Path to the CSV file to append readings to (default: energy_log.csv).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between two readings (default: 1.0).",
    )
    args = parser.parse_args()
    track(args.log_file, args.interval)


if __name__ == "__main__":
    main()
