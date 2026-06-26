"""Profile-aware SQLFluff command wrappers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


KTUFT_RULES = ",".join(
    [
        "AL01",
        "ST05",
        "LT12",
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
)

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
    profile_args = (
        _profile_args(selected_profile)
        if command_name in PROFILED_SQLFLUFF_COMMANDS
        else []
    )
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


def _usage() -> str:
    return """Usage:
  sqlfluff-profile init [--force]
  sqlfluff-profile list
  sqlfluff-profile current
  sqlfluff-profile use PROFILE
  sqlfluff-profile next
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
