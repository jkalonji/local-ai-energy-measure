"""Shared helpers for naming and finding energy tracker CSV log files.

Every run of energy_tracker.py writes to its own timestamped file under
logs/, so restarting the tracker never overwrites or appends to a
previous run's data. dashboard.py uses the same helpers to find and
follow the most recent file.
"""

import time
from pathlib import Path
from typing import Optional

LOGS_DIR = Path("logs")
FILENAME_PREFIX = "energy_"


def new_log_path(base_dir: Path = LOGS_DIR) -> Path:
    """Build a fresh, timestamped log file path for a new tracker run."""
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{FILENAME_PREFIX}{time.strftime('%Y%m%d_%H%M%S')}.csv"


def list_log_files(base_dir: Path = LOGS_DIR) -> list[Path]:
    """List existing log files, most recent first.

    Sorted by filename (which embeds a YYYYMMDD_HHMMSS timestamp) rather
    than mtime: mtime keeps changing while a tracker run is being written
    to, and can tie between files created in the same second, which is
    less reliable than the name itself for ordering runs.
    """
    if not base_dir.exists():
        return []
    return sorted(base_dir.glob(f"{FILENAME_PREFIX}*.csv"), reverse=True)


def latest_log_file(base_dir: Path = LOGS_DIR) -> Optional[Path]:
    """Return the most recently modified log file, or None if there is none."""
    files = list_log_files(base_dir)
    return files[0] if files else None
