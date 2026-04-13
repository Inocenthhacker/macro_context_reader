"""Shared notebook bootstrap — Colab clone/install + local detection.

Centralizes the environment setup that every notebook needs:
  1. Clone/pull repo on Colab, detect repo root locally
  2. pip install -e . (editable)
  3. Load secrets from Colab userdata
  4. Force sys.path injection for Python 3.12+ (.pth not processed)
  5. Clear stale macro_context_reader module cache

Usage (first code cell of any notebook):
    # Idempotent environment bootstrap
    import importlib, sys
    from pathlib import Path
    _nb_dir = Path.cwd() if Path("_bootstrap.py").exists() else Path.cwd() / "notebooks"
    sys.path.insert(0, str(_nb_dir))
    from _bootstrap import bootstrap
    bootstrap()
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_COLAB = "google.colab" in sys.modules or Path("/content").exists()
_GITHUB_USER = "Inocenthhacker"
_REPO_NAME = "macro_context_reader"
_SECRET_KEYS = ("FRED_API_KEY", "DEEPINFRA_API_KEY", "HF_TOKEN")


def bootstrap() -> Path:
    """Set up notebook environment. Returns repo root Path.

    Idempotent — safe to call multiple times.
    """
    if _COLAB:
        repo_path = _bootstrap_colab()
    else:
        repo_path = _bootstrap_local()

    # Force sys.path extension — .pth files not processed by Python 3.12 Colab kernel
    src_path = str(repo_path / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        logger.info(f"Injected into sys.path: {src_path}")

    # Clear any stale cached imports of the package (in case of re-install)
    for mod_name in list(sys.modules.keys()):
        if "macro_context_reader" in mod_name:
            del sys.modules[mod_name]

    print("\n\u2713 Bootstrap complete")
    return repo_path


def _bootstrap_colab() -> Path:
    """Clone/pull repo, install package, load secrets on Colab."""
    from google.colab import userdata  # type: ignore[import-untyped]

    token = userdata.get("GITHUB_TOKEN")
    url = f"https://{_GITHUB_USER}:{token}@github.com/{_GITHUB_USER}/{_REPO_NAME}.git"
    repo_path = Path(f"/content/{_REPO_NAME}")

    if repo_path.exists():
        subprocess.run(["git", "-C", str(repo_path), "pull", "--quiet"], check=True)
        print("\u2713 Pulled latest")
    else:
        subprocess.run(["git", "clone", "--quiet", url, str(repo_path)], check=True)
        print("\u2713 Cloned")

    os.chdir(repo_path)
    subprocess.run(["pip", "install", "-e", ".", "--quiet"], check=True)
    print("\u2713 Package installed (editable)")

    for key in _SECRET_KEYS:
        try:
            val = userdata.get(key)
            if val:
                os.environ[key] = val
                print(f"\u2713 {key} loaded")
        except Exception:
            print(f"\u26a0 {key} not in Secrets (optional)")

    return repo_path


def _bootstrap_local() -> Path:
    """Detect repo root when running locally."""
    repo_path = Path.cwd()
    if repo_path.name == "notebooks":
        repo_path = repo_path.parent
        os.chdir(repo_path)
    print(f"\u2713 Local mode: {repo_path}")
    return repo_path
