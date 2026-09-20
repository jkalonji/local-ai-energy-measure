"""Tests for gpu_samples.py: exact windowed energy, bins, and the recorder."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import gpu_samples as gs
import log_paths

NO_UTIL = pd.DataFrame(columns=["timestamp_us", "util_pct"])


def series(power_w, seconds, step_ms=20, t0_us=1_000_000):
    """Timestamps (us) and power (mW) of a constant-power series."""
    ts = np.arange(t0_us, t0_us + int(seconds * 1e6) + 1, step_ms * 1000)
    return ts, np.full(len(ts), power_w * 1000)


class EnergyBetweenTest(unittest.TestCase):
    def test_constant_power_gives_power_times_time(self):
        ts, mw = series(100, 1.0)
        joules, covered = gs.energy_between(ts, mw, ts[0] + 200_000, ts[0] + 700_000)
        self.assertAlmostEqual(joules, 50.0, places=9)
        self.assertAlmostEqual(covered, 0.5, places=9)

    def test_linear_ramp_is_integrated_exactly(self):
        ts = np.arange(0, 1_000_001, 20_000)
        mw = ts // 5  # 0 W -> 200 W over one second
        self.assertAlmostEqual(gs.energy_between(ts, mw, 0, 1_000_000)[0], 100.0, places=9)
        self.assertAlmostEqual(gs.energy_between(ts, mw, 250_000, 750_000)[0], 50.0, places=9)  # edges fall between samples

    def test_window_edges_between_samples_are_interpolated(self):
        ts = np.array([0, 100_000])
        mw = np.array([100_000, 300_000])  # 100 W -> 300 W
        joules, _ = gs.energy_between(ts, mw, 50_000, 100_000)  # 200 W..300 W over 0.05 s
        self.assertAlmostEqual(joules, 12.5, places=9)

    def test_bins_add_up_to_the_whole_window(self):
        rng = np.random.default_rng(0)
        ts = np.cumsum(rng.integers(15_000, 25_000, 400)) + 5_000_000
        mw = rng.integers(10_000, 160_000, 400)
        start, end = int(ts[3]) + 777, int(ts[-4]) - 555
        whole = gs.energy_between(ts, mw, start, end)[0]
        edges = np.linspace(start, end, 37).astype(int)
        parts = sum(gs.energy_between(ts, mw, a, b)[0] for a, b in zip(edges, edges[1:]))
        self.assertAlmostEqual(whole, parts, places=9)

    def test_lost_samples_are_not_integrated_and_show_as_missing_coverage(self):
        ts = np.array([0, 20_000, 500_000, 520_000])
        mw = np.full(4, 100_000)
        joules, covered = gs.energy_between(ts, mw, 0, 520_000)
        self.assertAlmostEqual(covered, 0.04, places=9)  # 0-20 ms and 500-520 ms only
        self.assertAlmostEqual(joules, 4.0, places=9)

    def test_nothing_to_integrate(self):
        ts, mw = series(100, 1.0)
        self.assertEqual(gs.energy_between(ts, mw, ts[-1] + 10, ts[-1] + 500), (0.0, 0.0))
        self.assertEqual(gs.energy_between(ts[:1], mw[:1], 0, 10**9), (0.0, 0.0))
        self.assertEqual(gs.energy_between(ts, mw, 500, 500), (0.0, 0.0))

    def test_duplicate_timestamps_do_not_poison_the_result(self):
        ts = np.array([0, 20_000, 20_000, 40_000])
        mw = np.full(4, 100_000)
        joules, covered = gs.energy_between(ts, mw, 0, 40_000)
        self.assertAlmostEqual(joules, 4.0, places=9)
        self.assertAlmostEqual(covered, 0.04, places=9)


class BinEnergyTest(unittest.TestCase):
    def test_hundred_ms_bins_of_a_step(self):
        # 20 W for 1 s, then 120 W from 1 s on (one sample per 20 ms; the ramp spans one sample step)
        ts = np.arange(0, 2_000_001, 20_000)
        mw = np.where(ts < 1_000_000, 20_000, 120_000)
        power = pd.DataFrame({"timestamp_us": ts, "power_mw": mw})
        bins = gs.bin_energy(power, NO_UTIL, 500_000, 1_500_000)
        self.assertEqual(len(bins), 10)
        self.assertAlmostEqual(bins["energy_j"].iloc[0], 2.0, places=6)    # 20 W * 0.1 s
        self.assertAlmostEqual(bins["energy_j"].iloc[-1], 12.0, places=6)  # 120 W * 0.1 s
        # 20 W until 1 s, 120 W after, plus the linear ramp over the one 20 ms step between the samples: (20+120)/2*0.02 - 20*0.02 = 1 J
        self.assertAlmostEqual(bins["energy_j"].sum(), 20 * 0.5 + 120 * 0.5 + (120 - 20) * 0.02 / 2, places=6)
        self.assertTrue(bins["gpu_util_pct"].isna().all())

    def test_utilization_reading_is_the_200ms_window_containing_the_bin_centre(self):
        ts = np.arange(0, 1_000_001, 20_000)
        power = pd.DataFrame({"timestamp_us": ts, "power_mw": np.full(len(ts), 50_000)})
        util = pd.DataFrame({"timestamp_us": [400_000, 600_000], "util_pct": [10, 90]})
        bins = gs.bin_energy(power, util, 0, 700_000)
        by_start = dict(zip(bins["bin_start_us"], bins["gpu_util_pct"]))
        self.assertTrue(np.isnan(by_start[0]))          # centre 50 ms: before the first window (200-400 ms)
        self.assertEqual(by_start[200_000], 10)          # centre 250 ms in (200, 400]
        self.assertEqual(by_start[300_000], 10)          # centre 350 ms, same reading shared
        self.assertEqual(by_start[500_000], 90)          # centre 550 ms in (400, 600]
        self.assertTrue(np.isnan(by_start[600_000]))     # centre 650 ms: no reading yet

    def test_last_bin_is_truncated_to_the_window(self):
        ts, mw = series(100, 1.0, t0_us=0)
        power = pd.DataFrame({"timestamp_us": ts, "power_mw": mw})
        bins = gs.bin_energy(power, NO_UTIL, 0, 250_000)
        self.assertEqual(len(bins), 3)
        self.assertAlmostEqual(bins["energy_j"].iloc[-1], 5.0, places=9)  # 100 W * 0.05 s


class FakeSource:
    """A driver buffer: returns the samples newer than `after_us`."""

    def __init__(self):
        self.power_samples, self.util_samples, self.fail = [], [], None

    def power(self, after_us):
        if self.fail:
            raise self.fail
        return [s for s in self.power_samples if s[0] > after_us]

    def utilization(self, after_us):
        return [s for s in self.util_samples if s[0] > after_us]


class HiresRecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hires" / "energy_x.csv"
        self.source = FakeSource()
        self.warnings = []
        self.recorder = gs.HiresRecorder(self.source, self.path, drain_interval_s=0.01, warn=self.warnings.append)

    def test_repeated_drains_write_each_sample_once(self):
        self.source.power_samples = [(1_000_000 + i * 20_000, 50_000 + i) for i in range(5)]
        self.source.util_samples = [(1_100_000, 40)]
        self.assertEqual(self.recorder.drain(), 6)
        self.assertEqual(self.recorder.drain(), 0)
        self.source.power_samples += [(1_100_000 + i * 20_000, 60_000) for i in range(1, 4)]
        self.assertEqual(self.recorder.drain(), 3)
        power, util = gs.read_hires(self.path)
        self.assertEqual(len(power), 8)
        self.assertEqual(list(util["util_pct"]), [40])
        self.assertEqual(self.path.read_text().splitlines()[0], "kind,timestamp_us,value")

    def test_a_gap_larger_than_the_integration_limit_is_reported(self):
        self.source.power_samples = [(1_000_000, 50_000)]
        self.recorder.drain()
        self.source.power_samples.append((1_000_000 + 260_000, 50_000))
        self.recorder.drain()
        self.assertEqual(len(self.warnings), 1)
        self.assertIn("260 ms", self.warnings[0])

    def test_a_failing_drain_is_reported_once_and_recording_resumes(self):
        self.source.fail = RuntimeError("driver hiccup")
        self.recorder._drain_reporting_errors()
        self.recorder._drain_reporting_errors()
        self.assertEqual(len(self.warnings), 1)
        self.source.fail = None
        self.source.power_samples = [(1_000_000, 50_000)]
        self.recorder._drain_reporting_errors()
        self.assertEqual(len(gs.read_hires(self.path)[0]), 1)

    def test_thread_records_and_stop_flushes_the_last_samples(self):
        self.recorder.start()
        self.source.power_samples = [(1_000_000, 50_000), (1_020_000, 51_000)]
        self.recorder.stop()
        self.assertEqual(len(gs.read_hires(self.path)[0]), 2)


class ReadHiresTest(unittest.TestCase):
    def test_sorted_deduplicated_integer_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "energy_x.csv"
            path.write_text("kind,timestamp_us,value\npower_mw,300,3\npower_mw,100,1\npower_mw,100,1\nutil_pct,200,50\n")
            power, util = gs.read_hires(path)
            self.assertEqual(list(power["timestamp_us"]), [100, 300])
            self.assertEqual(str(power["timestamp_us"].dtype), "int64")
            self.assertEqual(list(util["util_pct"]), [50])

    def test_missing_file_explains_itself(self):
        with self.assertRaisesRegex(FileNotFoundError, "hi-res"):
            gs.read_hires(Path("does/not/exist.csv"))


class HiresPathTest(unittest.TestCase):
    def test_hires_files_are_never_listed_as_tracker_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "energy_20260101_000000.csv"
            log.write_text("x\n")
            hires = gs.hires_path_for(log)
            hires.parent.mkdir()
            hires.write_text("x\n")
            self.assertEqual(hires.name, log.name)
            self.assertEqual(log_paths.list_log_files(Path(tmp)), [log])


if __name__ == "__main__":
    unittest.main()
