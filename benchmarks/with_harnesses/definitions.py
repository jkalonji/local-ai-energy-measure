"""Harness and task definitions of the with_harnesses benchmark.

A harness is described by harnesses/<name>.yaml: how to start it headless on one task, and which
files to generate for it. A task is described by tasks/<id>.yaml: the prompt, the files present in
the workspace, and the objective checks that decide whether the agent did what was asked.

Strings in a harness file may use {placeholders}, replaced in a single pass (so a task prompt that
happens to contain "{model}" is left alone). `render` lists the known names.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
HARNESSES_DIR = HERE / "harnesses"
TASKS_DIR = HERE / "tasks"

PLACEHOLDERS = {"task", "model", "proxy_url", "v1_url", "num_ctx", "workspace", "home", "harness_dir", "python"}
CHECK_TYPES = {"stdout_contains", "file_equals", "file_contains", "file_unchanged", "command"}
DEFAULT_TIMEOUT_S = 600

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(text: str, values: Mapping[str, object]) -> str:
    """Replace {name} by values[name] in one pass; unknown names are left as they are."""
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def _unknown_placeholders(text: str) -> List[str]:
    return sorted(set(_PLACEHOLDER.findall(text)) - PLACEHOLDERS)


@dataclass
class Harness:
    name: str
    description: str
    dir: Path                      # where the harness is installed (the {harness_dir} placeholder)
    command: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    files: Dict[str, str] = field(default_factory=dict)   # path under {home} -> content
    timeout_s: int = DEFAULT_TIMEOUT_S


@dataclass
class Task:
    id: str
    description: str
    prompt: str
    checks: List[dict]
    needs_tools: bool = False
    files: Dict[str, str] = field(default_factory=dict)   # path under the workspace -> content
    timeout_s: int = 0             # 0: use the harness timeout


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a mapping at the top level")
    return data


def load_harness(name: str, directory: Path = HARNESSES_DIR) -> Harness:
    path = directory / f"{name}.yaml"
    data = _read_yaml(path)
    for key in ("description", "dir", "command"):
        if key not in data:
            raise ValueError(f"{path.name}: missing '{key}'")
    command = [str(part) for part in data["command"]]
    env = {str(k): str(v) for k, v in (data.get("env") or {}).items()}
    files = {str(k): str(v) for k, v in (data.get("files") or {}).items()}
    for text in [*command, *env.values(), *files.values(), *files.keys()]:
        bad = _unknown_placeholders(text)
        if bad:
            raise ValueError(f"{path.name}: unknown placeholder(s) {bad}; known: {sorted(PLACEHOLDERS)}")
    if "{task}" not in "\0".join(command):
        raise ValueError(f"{path.name}: 'command' never uses {{task}}, the harness would not receive the prompt")
    return Harness(
        name=name,
        description=str(data["description"]),
        dir=(REPO_ROOT / str(data["dir"])).resolve(),
        command=command,
        env=env,
        files=files,
        timeout_s=int(data.get("timeout_s", DEFAULT_TIMEOUT_S)),
    )


def load_task(task_id: str, directory: Path = TASKS_DIR) -> Task:
    path = directory / f"{task_id}.yaml"
    data = _read_yaml(path)
    for key in ("description", "prompt", "checks"):
        if key not in data:
            raise ValueError(f"{path.name}: missing '{key}'")
    checks = list(data["checks"])
    if not checks:
        raise ValueError(f"{path.name}: a task needs at least one check")
    for check in checks:
        kinds = set(check) & CHECK_TYPES
        if len(kinds) != 1:
            raise ValueError(f"{path.name}: each check needs exactly one of {sorted(CHECK_TYPES)}, got {check}")
    files = {str(k): str(v) for k, v in (data.get("files") or {}).items()}
    for check in checks:
        if "file_unchanged" in check and check["file_unchanged"] not in files:
            raise ValueError(f"{path.name}: file_unchanged '{check['file_unchanged']}' is not one of the task files")
    return Task(
        id=task_id,
        description=str(data["description"]),
        prompt=str(data["prompt"]).strip(),
        checks=checks,
        needs_tools=bool(data.get("needs_tools", False)),
        files=files,
        timeout_s=int(data.get("timeout_s", 0)),
    )


def list_names(directory: Path) -> List[str]:
    """Names of the definition files in `directory`, sorted."""
    return sorted(p.stem for p in directory.glob("*.yaml"))
