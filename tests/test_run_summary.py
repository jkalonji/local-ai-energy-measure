"""Tests for attribution.summarize_run: energy inside model calls vs between them."""

import unittest

import numpy as np
import pandas as pd

from attribution import summarize_run


def constant_power(watts, start_s, end_s):
    ts = np.arange(round(start_s * 1e6), round(end_s * 1e6) + 1, 20_000)
    return pd.DataFrame({"timestamp_us": ts, "power_mw": np.full(len(ts), watts * 1000)})


def calls(*windows, prompt=10, completion=5):
    return pd.DataFrame([
        {"call_start_ts": a, "call_end_ts": b, "prompt_tokens": prompt, "completion_tokens": completion}
        for a, b in windows
    ])


class SummarizeRunTest(unittest.TestCase):
    def test_overlapping_calls_are_merged_so_no_energy_is_counted_twice(self):
        power = constant_power(100, 0, 12)
        s = summarize_run(power, calls((2, 4), (3, 5), (8, 9)), 1, 10)
        self.assertAlmostEqual(s["energy_total_j"], 900.0, places=6)
        self.assertAlmostEqual(s["energy_in_calls_j"], 400.0, places=6)  # [2,5] and [8,9]
        self.assertAlmostEqual(s["energy_between_calls_j"], 500.0, places=6)
        self.assertAlmostEqual(s["in_calls_share"], 400 / 900, places=6)
        self.assertEqual(s["n_calls"], 3)
        self.assertEqual((s["prompt_tokens"], s["completion_tokens"]), (30, 15))

    def test_calls_are_clipped_to_the_run_window(self):
        power = constant_power(50, 0, 12)
        s = summarize_run(power, calls((0.5, 1.5), (9.5, 11)), 1, 10)
        self.assertAlmostEqual(s["energy_in_calls_j"], 50 * (0.5 + 0.5), places=6)
        self.assertEqual(s["n_calls"], 2)

    def test_calls_outside_the_run_are_ignored(self):
        power = constant_power(50, 0, 30)
        s = summarize_run(power, calls((20, 25)), 1, 10)
        self.assertEqual((s["n_calls"], s["energy_in_calls_j"]), (0, 0.0))
        self.assertAlmostEqual(s["energy_between_calls_j"], 450.0, places=6)

    def test_missing_samples_show_up_as_reduced_coverage(self):
        power = pd.concat([constant_power(100, 0, 4), constant_power(100, 6, 12)], ignore_index=True)
        s = summarize_run(power, calls((2, 8)), 1, 10)
        self.assertAlmostEqual(s["run_s"], 9.0)
        self.assertAlmostEqual(s["covered_s"], 7.0, places=6)  # 2 s hole between 4 s and 6 s
        self.assertAlmostEqual(s["energy_total_j"], 700.0, places=6)

    def test_run_without_calls(self):
        s = summarize_run(constant_power(100, 0, 12), calls(), 1, 10)
        self.assertEqual(s["n_calls"], 0)
        self.assertAlmostEqual(s["in_calls_share"], 0.0)


if __name__ == "__main__":
    unittest.main()
