from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"


def _venv_python() -> Path:
    venv_root = PROJECT_ROOT / ".venv"
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def activate_virtual_environment() -> None:
    """Run this publisher with the library's own .venv interpreter."""
    target_python = _venv_python()
    if not target_python.is_file():
        raise RuntimeError(
            f"Virtual environment not found: {target_python}\n"
            f"Run {PROJECT_ROOT / 'tools' / 'setup_venv.py'} first."
        )

    try:
        current_python = Path(sys.executable).resolve()
        expected_python = target_python.resolve()
    except OSError:
        current_python = Path(sys.executable)
        expected_python = target_python

    if current_python == expected_python:
        print(f"Virtual environment active: {target_python}")
        return

    venv_root = target_python.parent.parent
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_root)
    env["PATH"] = str(target_python.parent) + os.pathsep + env.get("PATH", "")

    command = [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]]
    print(f"Activating virtual environment: {venv_root}")
    print("> " + subprocess.list2cmdline(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    raise SystemExit(completed.returncode)


def _make_writable(path: str | os.PathLike[str]) -> None:
    target = Path(path)
    try:
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
    except (FileNotFoundError, OSError):
        pass


def _remove_readonly(function, path, exc_info) -> None:  # type: ignore[no-untyped-def]
    _make_writable(path)
    function(path)


def remove_dist_folder() -> None:
    """Delete the complete dist folder before versioning/building."""
    if DIST_DIR.exists():
        print(f"Removing dist folder: {DIST_DIR}")
        try:
            shutil.rmtree(DIST_DIR, onexc=_remove_readonly)
        except TypeError:
            # Python < 3.12 compatibility for onerror name.
            shutil.rmtree(DIST_DIR, onerror=_remove_readonly)
    else:
        print(f"dist folder does not exist: {DIST_DIR}")


def _poetry_executable() -> str:
    candidates = []
    if os.name == "nt":
        candidates.append(PROJECT_ROOT / ".venv" / "Scripts" / "poetry.exe")
    else:
        candidates.append(PROJECT_ROOT / ".venv" / "bin" / "poetry")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    poetry = shutil.which("poetry")
    if poetry:
        return poetry
    raise RuntimeError(
        "Poetry was not found in the library virtual environment. "
        f"Run {PROJECT_ROOT / 'tools' / 'setup_venv.py'} first."
    )


def run_poetry(*args: str, env: dict[str, str] | None = None, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = [_poetry_executable(), *args]
    print("> " + subprocess.list2cmdline(command))
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def increment_version() -> tuple[str, str]:
    """Increment the package patch version and return (old_version, new_version)."""
    old_version = run_poetry("version", "-s", capture_output=True).stdout.strip()
    run_poetry("version", "patch")
    new_version = run_poetry("version", "-s", capture_output=True).stdout.strip()
    print(f"Version incremented: {old_version} -> {new_version}")
    return old_version, new_version


def restore_version(version: str) -> None:
    """Restore pyproject.toml to the pre-release version after a failed release."""
    try:
        run_poetry("version", version)
    except Exception as restore_error:
        print(
            f"WARNING: release failed and automatic version rollback also failed: {restore_error}",
            file=sys.stderr,
        )
        return
    print(f"Version restored after failed release: {version}")


def build_package() -> None:
    """Build wheel and source distribution into a fresh dist folder."""
    run_poetry("build")
    if not DIST_DIR.is_dir() or not any(DIST_DIR.iterdir()):
        raise RuntimeError(f"Build completed without artifacts in {DIST_DIR}")
    print(f"Build completed: {DIST_DIR}")


def publish_package(version: str) -> None:
    """Publish the built artifacts using a PyPI token from the environment."""
    token = None
    token_source = None
    for variable in ("POETRY_PYPI_TOKEN_PYPI", "PYPI_TOKEN", "PYPI_API_TOKEN"):
        value = os.environ.get(variable)
        if value:
            token = value
            token_source = variable
            break

    if not token:
        raise RuntimeError(
            "PyPI token not found. Set POETRY_PYPI_TOKEN_PYPI, PYPI_TOKEN, "
            "or PYPI_API_TOKEN in the environment before publishing."
        )

    publish_env = os.environ.copy()
    publish_env["POETRY_PYPI_TOKEN_PYPI"] = token
    print(f"Publishing version {version} using token from environment variable: {token_source}")
    run_poetry("publish", env=publish_env)
    print(f"Published successfully: {version}")


def main() -> int:
    # Required release order:
    # 1. activate virtual environment
    # 2. remove dist folder
    # 3. increment version
    # 4. build
    # 5. publish using token from environment
    activate_virtual_environment()
    remove_dist_folder()
    old_version, version = increment_version()
    try:
        build_package()
        publish_package(version)
    except Exception:
        restore_version(old_version)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
