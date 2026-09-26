"""Create or reuse the local virtual environment for robo-email development."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
POETRY_VERSION = "2.5.1"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _is_target_venv_active() -> bool:
    """Return True when this script is running from the target .venv."""
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def _run(*args: str) -> None:
    command = list(args)
    print("> " + subprocess.list2cmdline(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if _is_target_venv_active():
        print(f"Reusing active virtual environment: {VENV}")
    else:
        if VENV.exists():
            print(f"Removing existing virtual environment: {VENV}")
            shutil.rmtree(VENV)
        print(f"Creating virtual environment: {VENV}")
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV)

    python = _venv_python()
    _run(str(python), "-m", "pip", "install", "--upgrade", "pip")
    _run(str(python), "-m", "pip", "install", f"poetry=={POETRY_VERSION}")
    _run(str(python), "-m", "pip", "install", "-e", str(ROOT))
    print(f"robo-email virtual environment is ready: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
