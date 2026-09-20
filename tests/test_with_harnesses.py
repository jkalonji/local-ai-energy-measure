"""Tests for benchmarks/with_harnesses: definitions, checks, a measured run, and the matrix."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from benchmarks.with_harnesses import definitions, execute, matrix, run_harness_benchmark as cli
from benchmarks.with_harnesses.checks import run_checks
from benchmarks.with_harnesses.definitions import Harness, Task, render

REPO_ROOT = Path(__file__).resolve().parents[1]


def task(**overrides) -> Task:
    values = dict(id="t", description="d", prompt="p", checks=[{"stdout_contains": "x"}])
    values.update(overrides)
    return Task(**values)


class DefinitionsTest(unittest.TestCase):
    def test_render_replaces_known_names_in_a_single_pass(self):
        self.assertEqual(render("{a} {b} {c}", {"a": "{b}", "b": "B"}), "{b} B {c}")

    def test_shipped_harnesses_and_tasks_load(self):
        harnesses = definitions.list_names(definitions.HARNESSES_DIR)
        tasks = definitions.list_names(definitions.TASKS_DIR)
        self.assertIn("dsh", harnesses)
        self.assertIn("ollama-agent-harness", harnesses)
        self.assertTrue(tasks)
        for name in harnesses:
            self.assertIn("{task}", "\0".join(definitions.load_harness(name).command))
        for name in tasks:
            self.assertTrue(definitions.load_task(name).checks)

    def _write(self, text: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "x.yaml").write_text(text, encoding="utf-8")
        return Path(tmp.name)

    def test_unknown_placeholder_is_rejected(self):
        directory = self._write("description: d\ndir: .\ncommand: [run, '{task}', '{modle}']\n")
        with self.assertRaisesRegex(ValueError, "modle"):
            definitions.load_harness("x", directory)

    def test_harness_that_never_receives_the_prompt_is_rejected(self):
        directory = self._write("description: d\ndir: .\ncommand: [run]\n")
        with self.assertRaisesRegex(ValueError, "task"):
            definitions.load_harness("x", directory)

    def test_task_needs_exactly_one_kind_per_check(self):
        directory = self._write("description: d\nprompt: p\nchecks: [{stdout_contains: a, file_equals: b}]\n")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            definitions.load_task("x", directory)

    def test_file_unchanged_must_name_a_task_file(self):
        directory = self._write("description: d\nprompt: p\nchecks: [{file_unchanged: nope.py}]\n")
        with self.assertRaisesRegex(ValueError, "nope.py"):
            definitions.load_task("x", directory)


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)

    def test_stdout_contains_ignores_case(self):
        self.assertTrue(run_checks(task(checks=[{"stdout_contains": "Pong"}]), self.ws, "well, PONG!")[0])
        self.assertFalse(run_checks(task(checks=[{"stdout_contains": "pong"}]), self.ws, "ping")[0])

    def test_file_equals_ignores_surrounding_whitespace_only(self):
        checks = task(checks=[{"file_equals": "a.txt", "content": "hi"}])
        self.assertEqual(run_checks(checks, self.ws, "")[1], "a.txt was not created")
        (self.ws / "a.txt").write_text("hi\n", encoding="utf-8")
        self.assertTrue(run_checks(checks, self.ws, "")[0])
        (self.ws / "a.txt").write_text("hi there", encoding="utf-8")
        self.assertFalse(run_checks(checks, self.ws, "")[0])

    def test_file_contains(self):
        (self.ws / "a.txt").write_text("hello world", encoding="utf-8")
        self.assertTrue(run_checks(task(checks=[{"file_contains": "a.txt", "content": "lo wo"}]), self.ws, "")[0])
        self.assertFalse(run_checks(task(checks=[{"file_contains": "a.txt", "content": "bye"}]), self.ws, "")[0])

    def test_file_unchanged_detects_edits_and_deletion(self):
        checks = task(files={"t.py": "original"}, checks=[{"file_unchanged": "t.py"}])
        (self.ws / "t.py").write_text("original", encoding="utf-8")
        self.assertTrue(run_checks(checks, self.ws, "")[0])
        (self.ws / "t.py").write_text("edited", encoding="utf-8")
        self.assertFalse(run_checks(checks, self.ws, "")[0])
        (self.ws / "t.py").unlink()
        self.assertFalse(run_checks(checks, self.ws, "")[0])

    def test_command_uses_the_exit_code(self):
        ok = task(checks=[{"command": ["{python}", "-c", "raise SystemExit(0)"]}])
        bad = task(checks=[{"command": ["{python}", "-c", "raise SystemExit(3)"]}])
        self.assertTrue(run_checks(ok, self.ws, "")[0])
        self.assertIn("exited 3", run_checks(bad, self.ws, "")[1])

    def test_every_check_must_pass_and_the_first_failure_is_reported(self):
        both = task(checks=[{"stdout_contains": "a"}, {"stdout_contains": "b"}])
        self.assertEqual(run_checks(both, self.ws, "a")[1], "stdout lacks 'b'")

    def test_paths_cannot_escape_the_workspace(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            run_checks(task(checks=[{"file_equals": "../secret", "content": "x"}]), self.ws, "")


FAKE_HARNESS = r"""
import os, sys, time
from pathlib import Path
from csv_log import append_row
from gpu_samples import hires_path_for

t = time.time()
log = Path(os.environ["TEST_LOG"])
Path("hello.txt").write_text(os.environ.get("TEST_CONTENT", "Bonjour"), encoding="utf-8")
append_row(log, {"row_type": "ollama_call", "call_start_ts": t + 0.05, "call_end_ts": t + 0.15, "model": "m",
                 "prompt_tokens": 5, "completion_tokens": 7, "tokens_source": "usage", "endpoint": "/v1/chat/completions"})
time.sleep(float(os.environ.get("TEST_SLEEP", "0.3")))
hires = hires_path_for(log)
hires.parent.mkdir(exist_ok=True)
lines = [f"power_mw,{int((t - 2 + i * 0.02) * 1e6)},100000" for i in range(400)]
hires.write_text("kind,timestamp_us,value\n" + "\n".join(lines) + "\n")
print("prompt was:", sys.argv[1])
raise SystemExit(int(os.environ.get("TEST_EXIT", "0")))
"""


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "logs" / "energy_x.csv"
        self.session = execute.Session(log_path=self.log, batch_id="b1", settle_s=0,
                                       transcripts_dir=Path(self.tmp.name) / "transcripts")
        self.harness = Harness(name="fake", description="d", dir=Path(self.tmp.name),
                               command=[sys.executable, "-c", FAKE_HARNESS, "{task}"], timeout_s=30)
        self.task = task(checks=[{"file_equals": "hello.txt", "content": "Bonjour"}], prompt="say {model}")
        env = mock.patch.dict(os.environ, {"TEST_LOG": str(self.log), "PYTHONPATH": str(REPO_ROOT)})
        env.start()
        self.addCleanup(env.stop)
        ctx = mock.patch.object(execute, "observed_context", return_value=32768)
        ctx.start()
        self.addCleanup(ctx.stop)

    def run_fake(self, **env):
        with mock.patch.dict(os.environ, env):
            return execute.run_once(self.harness, "m", self.task, 1, self.session, sleep=lambda s: None)

    def test_passing_run_is_measured_from_the_power_samples(self):
        row = self.run_fake()
        self.assertEqual((row["status"], row["exit_code"], row["n_calls"]), ("pass", 0, 1))
        self.assertAlmostEqual(row["energy_j"], 100 * row["duration_s"], places=3)  # 100 W over the run window
        self.assertAlmostEqual(row["energy_in_calls_j"], 10.0, places=3)             # one 0.1 s request
        self.assertAlmostEqual(row["coverage"], 1.0, places=4)
        self.assertEqual((row["prompt_tokens"], row["completion_tokens"], row["tokens_source"]), (5, 7, "usage"))
        self.assertEqual(row["num_ctx_observed"], 32768)
        self.assertEqual(row["notes"], "")

    def test_prompt_placeholders_are_not_expanded_inside_the_task_text(self):
        self.run_fake()
        (transcript,) = (Path(self.tmp.name) / "transcripts").glob("*.txt")
        self.assertIn("prompt was: say {model}", transcript.read_text(encoding="utf-8"))

    def test_run_row_is_written_to_the_tracker_log(self):
        row = self.run_fake()
        runs = [r for r in cli_rows(self.log) if r["row_type"] == "run"]
        self.assertEqual([(r["harness"], r["task_id"], r["model"], r["run_id"]) for r in runs],
                         [("fake", "t", "m", row["run_id"])])

    def test_wrong_result_is_a_fail_and_a_crash_is_an_error(self):
        self.assertEqual(self.run_fake(TEST_CONTENT="nope")["status"], "fail")
        self.assertEqual(self.run_fake(TEST_CONTENT="nope", TEST_EXIT="1")["status"], "error")

    def test_a_correct_result_with_a_nonzero_exit_still_passes(self):
        row = self.run_fake(TEST_EXIT="2")
        self.assertEqual((row["status"], row["exit_code"]), ("pass", 2))

    def test_timeout_kills_the_harness(self):
        self.harness.timeout_s = 1
        row = self.run_fake(TEST_SLEEP="30")
        self.assertEqual((row["status"], row["exit_code"]), ("timeout", None))
        self.assertLess(row["duration_s"], 15)

    def test_a_harness_that_bypasses_the_proxy_is_flagged(self):
        self.harness.command = [sys.executable, "-c", "print('{task}')".replace("{task}", "hi"), "{task}"]
        row = self.run_fake()
        self.assertEqual(row["n_calls"], 0)
        self.assertIn("bypassed", row["notes"])

    def test_workspace_is_removed_unless_kept(self):
        before = set(Path(tempfile.gettempdir()).glob("harness_run_*"))
        self.run_fake()
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("harness_run_*")), before)

    def test_harness_files_are_generated_with_placeholders_filled(self):
        self.harness.files = {"settings.yaml": "url: {v1_url}\nmodel: {model}\nctx: {num_ctx}\n"}
        self.harness.command = [sys.executable, "-c",
                                "import os, sys; sys.stdout.write(open(os.path.join(os.environ['HOME_DIR'], 'settings.yaml')).read())", "{task}"]
        self.harness.env = {"HOME_DIR": "{home}"}
        self.task = task(checks=[{"stdout_contains": "url: http://localhost:11435/v1"}, {"stdout_contains": "model: m"},
                                 {"stdout_contains": "ctx: 32768"}])
        self.assertEqual(self.run_fake()["status"], "pass")


def cli_rows(log_path: Path):
    import csv
    from csv_log import parse_row
    with log_path.open(newline="", encoding="utf-8") as f:
        return [r for r in (parse_row(fields) for fields in csv.reader(f)) if r]


def result(harness="h", model="m", task_id="t", status="pass", batch="b1", repeat=1, energy=0.1, **extra):
    row = {"run_id": f"{harness}-{model}-{task_id}-{repeat}-{batch}", "batch_id": batch, "started_at": "2026-01-01T00:00:00",
           "harness": harness, "model": model, "task_id": task_id, "repeat": repeat, "status": status, "exit_code": 0,
           "duration_s": 10.0, "num_ctx_expected": 32768, "num_ctx_observed": 32768, "n_calls": 2,
           "energy_wh": energy, "in_calls_share": 0.8, "notes": ""}
    row.update(extra)
    return row


class MatrixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "runs.csv"

    def add(self, *rows):
        for row in rows:
            matrix.append_run(row, self.path)
        return matrix.read_runs(self.path)

    def test_header_is_written_once_and_values_round_trip(self):
        runs = self.add(result(), result(repeat=2, energy=0.25))
        self.assertEqual(self.path.read_text(encoding="utf-8").count("run_id,batch_id"), 1)
        self.assertEqual(list(runs["energy_wh"]), [0.1, 0.25])

    def test_a_file_with_another_layout_is_not_appended_to(self):
        self.path.write_text("old,layout\n1,2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "column layout"):
            matrix.append_run(result(), self.path)

    def test_a_newer_batch_replaces_an_older_one_per_task(self):
        runs = self.add(result(batch="b1", status="fail"), result(batch="b2", status="pass"),
                        result(task_id="other", batch="b1", status="fail"))
        current = matrix.current_runs(runs)
        self.assertEqual(sorted(zip(current["task_id"], current["batch_id"], current["status"])),
                         [("other", "b1", "fail"), ("t", "b2", "pass")])

    def test_cell_counts_only_runs_that_executed(self):
        runs = self.add(result(task_id="a", energy=0.10), result(task_id="b", status="fail", energy=0.30),
                        result(task_id="c", status="skipped_no_tools", energy=float("nan")))
        (row,) = matrix.build_matrix(runs).to_dict("records")
        self.assertEqual((row["runs"], row["passed"]), (2, 1))
        self.assertAlmostEqual(row["median_energy_wh"], 0.20)
        self.assertEqual(row["not_run"], "skipped_no_tools")

    def test_markdown_shows_pairs_not_run_and_pairs_never_tested(self):
        runs = self.add(result(harness="dsh", model="a", energy=0.5), result(harness="dsh", model="b", status="skipped_no_tools"),
                        result(harness="oah", model="a", status="fail", energy=0.001))
        text = matrix.render_markdown(runs)
        self.assertIn("| a | 1/1 · 0.50 Wh | 0/1 · 0.0010 Wh |", text)
        self.assertIn("| b | n/a (no tool support) | not tested |", text)

    def test_markdown_warns_when_the_harness_changed_the_context(self):
        runs = self.add(result(num_ctx_observed=4096), result(task_id="u", notes="no model request went through the proxy"))
        text = matrix.render_markdown(runs)
        self.assertIn("context 4096 observed, 32768 expected", text)
        self.assertIn("went through the proxy", text)

    def test_empty_history_renders(self):
        self.assertIn("No run recorded yet", matrix.render_markdown(matrix.read_runs(self.path)))

    def test_write_reports_creates_both_files(self):
        self.add(result())
        csv_out, md_out = Path(self.tmp.name) / "m.csv", Path(self.tmp.name) / "m.md"
        matrix.write_reports(self.path, csv_out, md_out)
        self.assertIn("model,harness,runs,passed", csv_out.read_text(encoding="utf-8"))
        self.assertIn("Model x harness", md_out.read_text(encoding="utf-8"))


class CliTest(unittest.TestCase):
    def parse(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()):
            return cli.parse_args(list(argv))

    def test_nothing_runs_without_an_explicit_model_selection(self):
        with self.assertRaises(SystemExit):
            self.parse("--harness", "dsh")

    def test_models_set_and_all_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            self.parse("--harness", "dsh", "--models", "a", "--set", "round_1")

    def test_report_only_needs_nothing_else(self):
        self.assertTrue(self.parse("--report-only").report_only)

    def test_resolve_models_from_a_named_set(self):
        args = self.parse("--harness", "dsh", "--set", "round_1")
        self.assertIn("qwen3:4b", cli.resolve_models(args))

    def test_dry_run_prints_the_plan_and_touches_nothing(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cli, "load_harness", return_value=Harness(
                name="fake", description="d", dir=Path(tmp), command=["x", "{task}"])), \
                mock.patch.object(cli, "preflight", side_effect=AssertionError("must not check services")), \
                contextlib.redirect_stdout(out):
            cli.main(["--harness", "fake", "--models", "a,b", "--tasks", "write_file", "--repeat", "2", "--dry-run"])
        self.assertIn("1 harness(es) x 2 model(s) x 1 task(s) x 2 = 4 runs", out.getvalue())
        self.assertIn("fake / b: write_file", out.getvalue())


if __name__ == "__main__":
    unittest.main()
