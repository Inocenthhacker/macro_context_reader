"""Bootstrap helper for notebooks — idempotent Colab/local setup.

Detects environment (Google Colab vs local), clones/pulls the repo if
running on Colab, installs the package editable, and loads secrets
(FRED_API_KEY, GITHUB_TOKEN) from Colab Secrets or .env.

Usage from any notebook:
    sys.path.insert(0, str(nb_dir))
    from _bootstrap import bootstrap
    bootstrap()

Refs: INFRA/NOTEBOOK-BOOTSTRAP, DEC-011
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_NAME = "macro_context_reader"
REPO_URL_BASE = "github.com/Inocenthhacker/macro_context_reader.git"
REQUIRED_ENV_VARS = ["FRED_API_KEY"]


def is_colab() -> bool:
    """Detect Google Colab environment."""
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def bootstrap_colab() -> None:
    """Clone repo, install editable, load secrets. Idempotent."""
    from google.colab import userdata

    repo_path = Path(f"/content/{REPO_NAME}")

    # Clone or pull
    if repo_path.exists():
        print(f"  Repo exists at {repo_path}, pulling latest...")
        subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--quiet"], check=True
        )
    else:
        print(f"  Cloning {REPO_NAME}...")
        try:
            gh_token = userdata.get("GITHUB_TOKEN")
            gh_user = userdata.get("GITHUB_USER") or "Inocenthhacker"
            url = f"https://{gh_user}:{gh_token}@{REPO_URL_BASE}"
        except Exception:
            raise RuntimeError(
                "GITHUB_TOKEN not found in Colab Secrets. "
                "Add it via sidebar (key icon) -> Add new secret -> GITHUB_TOKEN"
            )
        subprocess.run(
            ["git", "clone", "--quiet", url, str(repo_path)], check=True
        )
        print(f"  Cloned to {repo_path}")

    # Install editable (idempotent — pip detects already installed)
    os.chdir(repo_path)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("pip install failed")
    print(f"  Package installed (editable) at {repo_path}")

    # Load secrets into env
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            try:
                val = userdata.get(var)
                if val:
                    os.environ[var] = val
                    print(f"  {var} loaded from Colab Secrets")
                else:
                    print(f"  WARNING: {var} not set in Colab Secrets")
            except Exception:
                print(f"  WARNING: {var} not accessible — add to Colab Secrets")

    # Ensure src/ is importable
    src_path = str(repo_path / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    _verify_import()


def bootstrap_local() -> None:
    """Verify local install + env vars."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Ensure src/ is importable if running from repo root
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        src = candidate / "src"
        if src.exists() and (src / "macro_context_reader").exists():
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            break

    _verify_import()

    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            print(f"  WARNING: {var} not set — check .env file in repo root")


def _verify_import() -> None:
    """Verify macro_context_reader is importable."""
    try:
        import macro_context_reader
        pkg_path = getattr(macro_context_reader, "__file__", None)
        if pkg_path is None:
            raise ImportError("Namespace package detected — install incomplete")
        print(f"  Import verified: {pkg_path}")
    except ImportError as e:
        raise RuntimeError(
            f"Package import failed after setup: {e}\n"
            "Run `pip install -e .` from repo root."
        )


def bootstrap() -> None:
    """Entry point — detect environment and route setup."""
    if is_colab():
        print("Environment: Google Colab")
        bootstrap_colab()
    else:
        print("Environment: Local")
        bootstrap_local()
    print("-" * 50)
    print("Bootstrap complete. Proceed with imports.")
