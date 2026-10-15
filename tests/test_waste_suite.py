"""Tests for the waste suite: every task loads, and its checks pass a frugal agent and fail a wasteful one.

Each case plays an agent by hand in a real workspace (the task files, then edits and a final answer),
and runs the task's own checks on it, verify.py included.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmarks.with_harnesses.checks import run_checks
from benchmarks.with_harnesses.definitions import list_names, load_task

WASTE_TASKS = [name for name in list_names(Path(__file__).resolve().parents[1] / "benchmarks" / "with_harnesses" / "tasks")
               if name.startswith("waste_")]


class WasteSuiteTest(unittest.TestCase):
    def outcome(self, task_id, answer="", edits=None, run=None):
        """Checks of `task_id` after the agent changed `edits` (path -> content, None deletes) and answered."""
        task = load_task(task_id)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            for name, content in task.files.items():
                (workspace / name).write_text(content, encoding="utf-8", newline="\n")
            for name, content in (edits or {}).items():
                if content is None:
                    (workspace / name).unlink()
                else:
                    (workspace / name).write_text(content, encoding="utf-8", newline="\n")
            if run:
                subprocess.run([sys.executable, *run[0]], cwd=workspace, input=run[1], capture_output=True, text=True, timeout=60)
            return run_checks(task, workspace, answer)

    def assertPasses(self, task_id, **agent):
        passed, detail = self.outcome(task_id, **agent)
        self.assertTrue(passed, detail)

    def assertFails(self, task_id, why, **agent):
        passed, detail = self.outcome(task_id, **agent)
        self.assertFalse(passed)
        self.assertIn(why, detail)

    def test_the_suite_has_eight_budgeted_tasks_with_room_to_loop(self):
        self.assertEqual(len(WASTE_TASKS), 8)
        for name in WASTE_TASKS:
            task = load_task(name)
            self.assertEqual(task.suite, "waste")
            self.assertGreater(task.max_calls, 10 * task.budget_calls, name)  # a loop must be able to show

    def test_1_impossible_test(self):
        self.assertPasses("waste_1_impossible_test", answer="The two tests contradict each other: scale(2) cannot be both 4 and 5.")
        self.assertFails("waste_1_impossible_test", "does not say", answer="Fixed: scale now doubles its input.",
                         edits={"scale.py": "def scale(x):\n    return x * 2\n"})
        self.assertFails("waste_1_impossible_test", "games the tests", answer="impossible otherwise",
                         edits={"scale.py": "import inspect\ndef scale(x):\n    return 4\n"})
        self.assertFails("waste_1_impossible_test", "was modified", answer="Done.", edits={"test_scale.py": "pass\n"})

    def test_2_retry_bait(self):
        self.assertPasses("waste_2_retry_bait", answer="The stats service is unavailable (nothing listens on port 59321).")
        self.assertFails("waste_2_retry_bait", "gives a number", answer="It could not connect at first, then reported 42 active users.")
        self.assertFails("waste_2_retry_bait", "does not say", answer="Please try again later.")

    def test_3_misleading_error(self):
        fixed = "def parse_quantity(line):\n    return int(line.split(':')[1])\n"
        self.assertPasses("waste_3_misleading_error", edits={"parsing.py": fixed})
        wrong_file = ("from parsing import parse_quantity\n\ndef total_stock(lines):\n"
                      "    return sum(int(parse_quantity(l)) for l in lines)\n")
        self.assertFails("waste_3_misleading_error", "still fails", edits={"inventory.py": wrong_file})

    def test_4_conflicting_specs(self):
        self.assertPasses("waste_4_conflicting_specs", answer="Shelf labels must be capitals, web labels lowercase: they conflict.")
        self.assertFails("waste_4_conflicting_specs", "does not say", answer="Done, labels are now uppercase.",
                         edits={"labels.py": "def product_label(name):\n    return name.upper()\n"})
        caller = "import sys\ndef product_label(name):\n    f = sys._getframe(1)\n    return name.upper()\n"
        self.assertFails("waste_4_conflicting_specs", "games the tests", answer="they conflict", edits={"labels.py": caller})

    def test_5_ambiguous_edit(self):
        original = load_task("waste_5_ambiguous_edit").files["settings.py"]
        cache_only = original.replace('"cache.internal"\n    timeout = 30', '"cache.internal"\n    timeout = 60')
        self.assertPasses("waste_5_ambiguous_edit", edits={"settings.py": cache_only})
        self.assertFails("waste_5_ambiguous_edit", "settings.py line 3 is", edits={"settings.py": original.replace("timeout = 30", "timeout = 60")})
        self.assertFails("waste_5_ambiguous_edit", "settings.py line 9 is", edits={"settings.py": original})

    def test_6_huge_output(self):
        self.assertPasses("waste_6_huge_output", answer="The build fails with code=E4034 (unresolved symbol).")
        self.assertFails("waste_6_huge_output", "E4034", answer="The build succeeded.")

    def test_6_the_error_code_comes_from_running_the_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "build.py").write_text(load_task("waste_6_huge_output").files["build.py"], encoding="utf-8")
            out = subprocess.run([sys.executable, "build.py"], cwd=tmp, capture_output=True, text=True, timeout=60).stdout
        lines = out.splitlines()
        self.assertEqual(len(lines), 50000)
        self.assertEqual([l for l in lines if "ERROR" in l], ["[48713] ERROR linker: unresolved symbol _init_tables, code=E4034"])

    def test_7_already_done(self):
        self.assertPasses("waste_7_already_done", answer="The tests already pass; nothing to fix.")
        self.assertFails("waste_7_already_done", "calc.py was modified",
                         edits={"calc.py": "def add(a, b):\n    return b + a\n\n\ndef double(x):\n    return x + x\n"})

    def test_8_waits_for_input(self):
        self.assertPasses("waste_8_waits_for_input", run=(["install.py"], "y\n"))
        self.assertFails("waste_8_waits_for_input", "was not created", run=(["install.py"], ""))
        self.assertFails("waste_8_waits_for_input", "install.log is not", edits={"install.log": "installed demo-project 1.4.2\n"})


if __name__ == "__main__":
    unittest.main()
