"""Profile-aware SQLFluff command wrappers."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


KTUFT_CORE_RULES = [
    "AL01",
    "ST05",
    "LT12",
]

KTUFT_CUSTOM_RULES = [
    "Ktuft_KL01",
    "Ktuft_KL02",
    "Ktuft_KL03",
    "Ktuft_KL04",
    "Ktuft_KL05",
    "Ktuft_KL06",
    "Ktuft_KL07",
    "Ktuft_KL08",
    "Ktuft_KL09",
    "Ktuft_KL10",
    "Ktuft_KL11",
    "Ktuft_KL12",
    "Ktuft_KL13",
    "Ktuft_KL14",
    "Ktuft_KL15",
    "Ktuft_KL16",
    "Ktuft_KL17",
    "Ktuft_KL18",
    "Ktuft_KL19",
]

KTUFT_RULES = ",".join([*KTUFT_CORE_RULES, *KTUFT_CUSTOM_RULES])
KTUFT_CUSTOM_RULES_ARGUMENT = ",".join(KTUFT_CUSTOM_RULES)

DEFAULT_PROFILES = {
    "repo": {
        "description": "Use the repo/environment SQLFluff configuration unchanged.",
        "args": [],
    },
    "ktuft": {
        "description": "Use the KTuft personal drafting formatter profile.",
        "args": ["--rules", KTUFT_RULES],
    },
}

SQLFLUFF_COMMANDS = {
    "dialects",
    "fix",
    "format",
    "lint",
    "parse",
    "render",
    "rules",
    "version",
}
PROFILED_SQLFLUFF_COMMANDS = {
    "fix",
    "lint",
}


def _config_dir() -> Path:
    configured = os.environ.get("SQLFLUFF_KTUFT_HOME")
    if configured:
        return Path(configured).expanduser()

    return Path.home() / ".config" / "sqlfluff-ktuft"


def _profiles_path() -> Path:
    return _config_dir() / "profiles.json"


def _active_profile_path() -> Path:
    return _config_dir() / "active-profile"


def _ensure_config_dir() -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    raw_text = path.read_text()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        data = json.loads(_jsonc_to_json(raw_text))

    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object in {path}")

    return data


def _jsonc_to_json(text: str) -> str:
    result = []
    i = 0
    in_string = False
    escaped = False

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == "/" and next_char == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        if char == "/" and next_char == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        result.append(char)
        i += 1

    without_comments = "".join(result)
    return re.sub(r",\s*([}\]])", r"\1", without_comments)


def _load_profiles() -> dict:
    path = _profiles_path()
    if not path.exists():
        return DEFAULT_PROFILES.copy()

    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"Expected object in {path}")

    profiles = DEFAULT_PROFILES.copy()
    profiles.update(data)
    return profiles


def _init_profiles(overwrite: bool = False) -> None:
    _ensure_config_dir()
    path = _profiles_path()
    if path.exists() and not overwrite:
        return

    _write_json(path, DEFAULT_PROFILES)


def _current_profile_name() -> str:
    path = _active_profile_path()
    if not path.exists():
        return "repo"

    return path.read_text().strip() or "repo"


def _set_current_profile(name: str) -> None:
    profiles = _load_profiles()
    if name not in profiles:
        raise SystemExit(f"Unknown SQLFluff profile: {name}")

    _ensure_config_dir()
    _active_profile_path().write_text(name + "\n")


def _profile_args(name: str) -> list[str]:
    profiles = _load_profiles()
    if name not in profiles:
        raise SystemExit(f"Unknown SQLFluff profile: {name}")

    args = profiles[name].get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise SystemExit(f"Profile {name!r} must define args as a list of strings")

    return args


def _run_sqlfluff(sqlfluff_args: list[str], profile_name: str | None = None) -> int:
    selected_profile = profile_name or _current_profile_name()
    command_name = next((arg for arg in sqlfluff_args if not arg.startswith("-")), "")
    profile_args = []
    if command_name in PROFILED_SQLFLUFF_COMMANDS:
        profile_args = _profile_args(selected_profile)
        if selected_profile == "repo":
            profile_args = [
                *profile_args,
                "--exclude-rules",
                KTUFT_CUSTOM_RULES_ARGUMENT,
            ]

    command = [
        sys.executable,
        "-m",
        "sqlfluff",
        *sqlfluff_args,
        *profile_args,
    ]
    return subprocess.call(command)


def _list_profiles() -> int:
    profiles = _load_profiles()
    current = _current_profile_name()

    for name in profiles:
        marker = "*" if name == current else " "
        description = profiles[name].get("description", "")
        print(f"{marker} {name}: {description}")

    return 0


def _next_profile() -> int:
    profiles = list(_load_profiles())
    current = _current_profile_name()
    try:
        current_index = profiles.index(current)
    except ValueError:
        current_index = -1

    next_name = profiles[(current_index + 1) % len(profiles)]
    _set_current_profile(next_name)
    print(next_name)
    return 0


def _sqlfluff_profile_executable() -> str:
    return shutil.which("sqlfluff-profile") or sys.argv[0]


def _vscode_settings(executable: str) -> dict[str, Any]:
    return {
        "sqlfluff.executablePath": executable,
        "sqlfluff.format.enabled": True,
        "sqlfluff.format.languages": [
            "sql",
            "jinja-sql",
            "snowflake-sql",
        ],
        "[sql]": {
            "editor.defaultFormatter": "sqlfluff.vscode-sqlfluff",
        },
        "[jinja-sql]": {
            "editor.defaultFormatter": "sqlfluff.vscode-sqlfluff",
        },
        "[snowflake-sql]": {
            "editor.defaultFormatter": "sqlfluff.vscode-sqlfluff",
        },
    }


def _task_presentation() -> dict[str, Any]:
    return {
        "reveal": "always",
        "panel": "dedicated",
        "clear": True,
    }


def _vscode_tasks(executable: str) -> list[dict[str, Any]]:
    executable = shlex.quote(executable)

    return [
        {
            "label": "SQLFluff Profile: Current",
            "type": "shell",
            "command": (
                "echo 'Current SQLFluff profile:' && "
                f"{executable} current"
            ),
            "problemMatcher": [],
            "presentation": _task_presentation(),
        },
        {
            "label": "SQLFluff Profile: Next",
            "type": "shell",
            "command": (
                "echo 'Switching SQLFluff profile...' && "
                f"{executable} next"
            ),
            "problemMatcher": [],
            "presentation": _task_presentation(),
        },
        {
            "label": "SQLFluff Profile: Debug",
            "type": "shell",
            "command": (
                'echo "PWD: $PWD" && '
                'echo "File: ${file}" && '
                f'echo "Profile: $({executable} current)" && '
                f"command -v {executable} && "
                f"{executable} --help | sed -n '1,8p'"
            ),
            "problemMatcher": [],
            "presentation": _task_presentation(),
        },
        {
            "label": "SQLFluff Profile: Fix Current File Including Ignored",
            "type": "shell",
            "command": (
                f'echo "SQLFluff profile: $({executable} current)" && '
                'echo "Fixing: ${file}" && '
                f'{executable} fix "${{file}}" --disregard-sqlfluffignores -n'
            ),
            "problemMatcher": [],
            "presentation": _task_presentation(),
        },
    ]


def _vscode_keybindings() -> list[dict[str, str]]:
    return [
        {
            "key": "ctrl+alt+s",
            "command": "workbench.action.tasks.runTask",
            "args": "SQLFluff Profile: Next",
        },
        {
            "key": "ctrl+alt+shift+s",
            "command": "workbench.action.tasks.runTask",
            "args": "SQLFluff Profile: Current",
        },
        {
            "key": "ctrl+alt+shift+d",
            "command": "workbench.action.tasks.runTask",
            "args": "SQLFluff Profile: Debug",
        },
        {
            "key": "ctrl+alt+shift+f",
            "command": "workbench.action.tasks.runTask",
            "args": "SQLFluff Profile: Fix Current File Including Ignored",
        },
    ]


def _merge_vscode_tasks(path: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    data = _read_json_object(path)
    existing_tasks = data.get("tasks", [])
    if not isinstance(existing_tasks, list):
        raise SystemExit(f"Expected `tasks` array in {path}")

    replacement_labels = {task["label"] for task in tasks}
    kept_tasks = [
        task
        for task in existing_tasks
        if not (
            isinstance(task, dict)
            and task.get("label") in replacement_labels
        )
    ]

    data["version"] = data.get("version", "2.0.0")
    data["tasks"] = [*kept_tasks, *tasks]
    return data


def _install_vscode(args: list[str]) -> int:
    workspace = Path.cwd()
    executable = _sqlfluff_profile_executable()
    print_keybindings = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-w", "--workspace"}:
            i += 1
            if i >= len(args):
                raise SystemExit("Expected path after --workspace")
            workspace = Path(args[i]).expanduser()
        elif arg == "--executable":
            i += 1
            if i >= len(args):
                raise SystemExit("Expected path after --executable")
            executable = args[i]
        elif arg == "--print-keybindings":
            print_keybindings = True
        else:
            raise SystemExit(f"Unknown install-vscode argument: {arg}")
        i += 1

    vscode_dir = workspace / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    settings_path = vscode_dir / "settings.json"
    settings = _read_json_object(settings_path)
    settings.update(_vscode_settings(executable))
    _write_json(settings_path, settings)

    tasks_path = vscode_dir / "tasks.json"
    _write_json(tasks_path, _merge_vscode_tasks(tasks_path, _vscode_tasks(executable)))

    print(f"Wrote {settings_path}")
    print(f"Wrote {tasks_path}")
    print()
    print("Use VS Code's normal Format Document command, e.g. Shift+Alt+F.")
    print("Use `SQLFluff Profile: Next` to toggle profiles.")

    if print_keybindings:
        print()
        print("Optional user keybindings:")
        print(json.dumps(_vscode_keybindings(), indent=2))

    return 0


def _usage() -> str:
    return """Usage:
  sqlfluff-profile init [--force]
  sqlfluff-profile list
  sqlfluff-profile current
  sqlfluff-profile use PROFILE
  sqlfluff-profile next
  sqlfluff-profile install-vscode [--workspace PATH] [--executable PATH] [--print-keybindings]
  sqlfluff-profile run SQLFLUFF_ARGS...
  sqlfluff-profile SQLFLUFF_ARGS...

Profiles are stored at:
  ~/.config/sqlfluff-ktuft/profiles.json

The active profile is stored at:
  ~/.config/sqlfluff-ktuft/active-profile
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0

    command = args.pop(0)

    if command == "init":
        _init_profiles(overwrite="--force" in args)
        print(_profiles_path())
        return 0

    if command == "list":
        return _list_profiles()

    if command == "current":
        print(_current_profile_name())
        return 0

    if command == "use":
        if not args:
            raise SystemExit("Expected profile name")
        _set_current_profile(args[0])
        print(args[0])
        return 0

    if command == "next":
        return _next_profile()

    if command == "install-vscode":
        return _install_vscode(args)

    if command == "run":
        if not args:
            raise SystemExit("Expected SQLFluff arguments after `run`")
        return _run_sqlfluff(args)

    if command in SQLFLUFF_COMMANDS or command.startswith("-"):
        return _run_sqlfluff([command, *args])

    raise SystemExit(f"Unknown command: {command}\n\n{_usage()}")


def ktuft_main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print("Usage: sqlfluff-ktuft SQLFLUFF_ARGS...")
        return 0

    return _run_sqlfluff(args, profile_name="ktuft")


if __name__ == "__main__":
    raise SystemExit(main())
