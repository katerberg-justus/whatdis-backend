import os
import subprocess
import sys


def _enabled(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _run_static_sync() -> None:
    command = [sys.executable, "scripts/sync_static_content.py"]
    if _enabled("STATIC_CONTENT_SYNC_PRUNE", default=False):
        command.append("--prune")

    print("Running static content sync...", flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    if _enabled("STATIC_CONTENT_SYNC_ON_START", default=True):
        _run_static_sync()

    os.execvp(sys.argv[1], sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
