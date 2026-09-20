"""Objective checks deciding whether an agent did what its task asked.

Each check is one mapping, e.g. {"file_equals": "hello.txt", "content": "Bonjour"}.
`run_checks` returns (passed, detail): every check must pass, and `detail` says why the first
failing one failed, so a failed run can be understood without reading the transcript.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Mapping, Tuple

from .definitions import Task, render

COMMAND_TIMEOUT_S = 120


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _inside(workspace: Path, relative: str) -> Path:
    """`relative` resolved under the workspace; refuses paths that escape it."""
    path = (workspace / relative).resolve()
    if workspace.resolve() not in (path, *path.parents):
        raise ValueError(f"check path '{relative}' is outside the workspace")
    return path


def _check(check: Mapping, task: Task, workspace: Path, stdout: str) -> Tuple[bool, str]:
    if "stdout_contains" in check:
        needle = str(check["stdout_contains"])
        return needle.lower() in stdout.lower(), f"stdout {'contains' if needle.lower() in stdout.lower() else 'lacks'} '{needle}'"

    if "file_equals" in check:
        path = _inside(workspace, check["file_equals"])
        if not path.is_file():
            return False, f"{check['file_equals']} was not created"
        actual = _read(path).strip()
        expected = str(check["content"]).strip()
        return actual == expected, f"{check['file_equals']} is {actual[:80]!r}, expected {expected[:80]!r}"

    if "file_contains" in check:
        path = _inside(workspace, check["file_contains"])
        if not path.is_file():
            return False, f"{check['file_contains']} was not created"
        needle = str(check["content"])
        found = needle in _read(path)
        return found, f"{check['file_contains']} {'contains' if found else 'lacks'} '{needle}'"

    if "file_unchanged" in check:
        name = check["file_unchanged"]
        path = _inside(workspace, name)
        unchanged = path.is_file() and _read(path) == task.files[name]
        return unchanged, f"{name} {'is unchanged' if unchanged else 'was modified or deleted'}"

    argv = [render(str(part), {"python": sys.executable}) for part in check["command"]]
    try:
        done = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=int(check.get("timeout_s", COMMAND_TIMEOUT_S)))
    except subprocess.TimeoutExpired:
        return False, f"`{' '.join(argv[1:])}` timed out"
    tail = (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
    return done.returncode == 0, f"`{' '.join(argv[1:])}` exited {done.returncode}: {tail[0][:120]}"


def run_checks(task: Task, workspace: Path, stdout: str) -> Tuple[bool, str]:
    details: List[str] = []
    for check in task.checks:
        passed, detail = _check(check, task, workspace, stdout)
        if not passed:
            return False, detail
        details.append(detail)
    return True, "; ".join(details)
