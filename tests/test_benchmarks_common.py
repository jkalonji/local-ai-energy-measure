"""Tests for benchmarks/common.py and the benchmark data files.

Run from the repository root: python -m unittest discover -s tests -t .
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from benchmarks import common

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADER = "row_type,timestamp,power_w\n"


class ModelsFileTest(unittest.TestCase):
    def test_shipped_models_file_is_consistent(self):
        config = common.load_models_file()
        names = common.all_model_names(config)
        self.assertEqual(len(names), len(set(names)), "duplicate model names")
        for set_name in config["sets"]:
            self.assertTrue(set(common.model_set(config, set_name)) <= set(names))

    def test_shipped_notes_only_mention_declared_models(self):
        declared = set(common.all_model_names(common.load_models_file()))
        notes_path = REPO_ROOT / "results" / "without_harness" / "notes.yaml"
        notes = yaml.safe_load(notes_path.read_text(encoding="utf-8"))
        self.assertTrue(set(notes["suspect_notes"]) <= declared)

    def test_set_with_undeclared_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.yaml"
            path.write_text("models:\n  - name: a\nsets:\n  s: [a, ghost]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ghost"):
                common.load_models_file(path)

    def test_unknown_set_lists_valid_choices(self):
        config = {"sets": {"one": ["a"], "two": ["b"]}}
        with self.assertRaisesRegex(KeyError, "one, two"):
            common.model_set(config, "three")


class AvgPowerInWindowTest(unittest.TestCase):
    def _log(self, tmp, body):
        path = Path(tmp) / "energy_20260101_000000.csv"
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def test_averages_samples_inside_window_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log(tmp, "sample,1,10\nsample,2,100\nsample,3,200\nsample,4,1000\n")
            self.assertEqual(common.avg_power_in_window(path, 2, 3), (150.0, 2))

    def test_ignores_ollama_call_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log(tmp, "sample,2,100\nollama_call,2,\n")
            self.assertEqual(common.avg_power_in_window(path, 0, 10), (100.0, 1))

    def test_empty_window_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log(tmp, "sample,1,10\n")
            self.assertEqual(common.avg_power_in_window(path, 5, 6), (None, 0))


class LatestLogFileTest(unittest.TestCase):
    def test_raises_when_no_log_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "energy_tracker.py"):
                common.latest_log_file(Path(tmp))

    def test_picks_newest_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("energy_20260101_000000.csv", "energy_20260301_000000.csv", "energy_20260201_000000.csv"):
                (Path(tmp) / name).write_text(HEADER, encoding="utf-8")
            self.assertEqual(common.latest_log_file(Path(tmp)).name, "energy_20260301_000000.csv")


class ModelCapabilitiesTest(unittest.TestCase):
    def _response(self, payload):
        response = mock.Mock()
        response.json.return_value = payload
        return response

    def test_returns_reported_capabilities(self):
        with mock.patch.object(common.requests, "post", return_value=self._response({"capabilities": ["completion", "tools"]})) as post:
            self.assertEqual(common.model_capabilities("m", "http://x"), ["completion", "tools"])
        post.assert_called_once_with("http://x/api/show", json={"model": "m"}, timeout=30)

    def test_missing_field_means_no_capabilities(self):
        with mock.patch.object(common.requests, "post", return_value=self._response({})):
            self.assertEqual(common.model_capabilities("m"), [])


if __name__ == "__main__":
    unittest.main()
