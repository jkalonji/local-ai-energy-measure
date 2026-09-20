"""Tests for csv_log.py: schema evolution must never make an existing log unreadable."""

import csv
import tempfile
import unittest
from pathlib import Path

from csv_log import CSV_FIELDS, LEGACY_V2_FIELDS, OLD_SCHEMA_FIELDS, append_row, parse_row


def read_raw(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class ParseRowTest(unittest.TestCase):
    def test_header_lines_are_skipped(self):
        for header in (CSV_FIELDS, LEGACY_V2_FIELDS, OLD_SCHEMA_FIELDS):
            self.assertIsNone(parse_row(list(header)))

    def test_each_known_width_is_mapped_to_its_own_columns(self):
        current = parse_row(["ollama_call"] + [""] * (len(CSV_FIELDS) - 1))
        self.assertEqual(list(current), CSV_FIELDS)
        v2 = parse_row(["sample"] + ["1"] * (len(LEGACY_V2_FIELDS) - 1))
        self.assertEqual(list(v2), LEGACY_V2_FIELDS)
        old = parse_row(["1.0", "2.0", "55.5", "0.01"])
        self.assertEqual(old, {"timestamp": "1.0", "elapsed_s": "2.0", "power_w": "55.5",
                               "energy_wh_cumulative": "0.01", "row_type": "sample"})

    def test_unknown_width_is_ignored(self):
        self.assertIsNone(parse_row(["a", "b", "c"]))


class AppendRowTest(unittest.TestCase):
    def test_new_file_gets_the_current_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "energy_x.csv"
            append_row(path, {"row_type": "ollama_call", "model": "m", "endpoint": "/v1/chat/completions",
                              "tokens_source": "usage"})
            header, row = read_raw(path)
            self.assertEqual(header, CSV_FIELDS)
            parsed = parse_row(row)
            self.assertEqual((parsed["endpoint"], parsed["tokens_source"], parsed["run_id"]),
                             ("/v1/chat/completions", "usage", ""))

    def test_existing_v2_file_keeps_its_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "energy_old.csv"
            path.write_text(",".join(LEGACY_V2_FIELDS) + "\n", encoding="utf-8")
            append_row(path, {"row_type": "ollama_call", "model": "m", "endpoint": "/api/chat"})
            rows = read_raw(path)
            self.assertEqual(len(rows[1]), len(LEGACY_V2_FIELDS))
            self.assertEqual(parse_row(rows[1])["model"], "m")

    def test_existing_oldest_file_gets_full_width_rows_that_still_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "energy_oldest.csv"
            path.write_text(",".join(OLD_SCHEMA_FIELDS) + "\n1.0,2.0,55.5,0.01\n", encoding="utf-8")
            append_row(path, {"row_type": "ollama_call", "model": "m", "endpoint": "/api/chat"})
            parsed = [parse_row(r) for r in read_raw(path)]
            self.assertEqual([p and p["row_type"] for p in parsed], [None, "sample", "ollama_call"])

    def test_lock_file_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "energy_x.csv"
            append_row(path, {"row_type": "sample"})
            append_row(path, {"row_type": "sample"})
            self.assertEqual(list(Path(tmp).glob("*.lock")), [])


if __name__ == "__main__":
    unittest.main()
