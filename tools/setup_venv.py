"""Create and configure the robo-email local Python virtual environment."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"
POETRY_VERSION = "2.5.1"


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    """Run a setup command from the robo-email project root."""
    print("> " + " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


def _venv_python() -> Path:
    """Return the platform-specific Python executable in the local environment."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _activation_hint() -> str:
    """Return the command used to activate the local environment."""
    if os.name == "nt":
        return r".\.venv\Scripts\Activate.ps1"
    return "source ./.venv/bin/activate"


def main() -> int:
    """Create .venv and install robo-email development dependencies with Poetry."""
    if sys.version_info[:2] < (3, 12) or sys.version_info[:2] >= (3, 13):
        raise RuntimeError(
            "robo-email requires Python >=3.12,<3.13. "
            f"Current interpreter is {sys.version.split()[0]}."
        )

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Bootstrap Python: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")

    target_active = False
    try:
        target_active = Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        target_active = False

    if target_active:
        print(f"Reusing active virtual environment: {VENV_DIR}")
    else:
        if VENV_DIR.exists():
            print(f"Removing existing virtual environment: {VENV_DIR}")
            shutil.rmtree(VENV_DIR)
        print(f"Creating virtual environment: {VENV_DIR}")
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV_DIR)

    python = _venv_python()
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(python), "-m", "pip", "install", f"poetry=={POETRY_VERSION}"])

    env = os.environ.copy()
    env["POETRY_VIRTUALENVS_CREATE"] = "false"

    # Clear cached PyPI metadata before dependency resolution so newly published
    # package versions are visible to Poetry.
    _run(
        [str(python), "-m", "poetry", "cache", "clear", "PyPI", "--all", "-n"], env=env
    )

    # Keep poetry.lock synchronized with pyproject.toml, then install this project
    # and its dependencies into the local .venv.
    _run([str(python), "-m", "poetry", "lock"], env=env)
    _run([str(python), "-m", "poetry", "install"], env=env)
    _run([str(python), "-m", "poetry", "--version"])

    print("\nrobo-email virtual environment is ready.")
    print(f"Python: {python}")
    print(f"Activate: {_activation_hint()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
