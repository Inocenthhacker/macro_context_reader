"""Rewrite notebooks/05_economic_sentiment_validation.ipynb for PRD-102/CC-2.

Cleveland Fed indices loader replaces local scraper+FinBERT pipeline.
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

NB_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "05_economic_sentiment_validation.ipynb"

BOOTSTRAP = '''# CELL-01
# Idempotent environment bootstrap - self-sufficient for Colab + local

import os
import sys
import subprocess
from pathlib import Path

REPO_NAME = "macro_context_reader"
REPO_URL = "https://github.com/Inocenthhacker/macro_context_reader.git"

def _is_colab() -> bool:
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False

def _run(cmd, check=True, capture=True):
    result = subprocess.run(cmd, capture_output=capture, text=True, shell=isinstance(cmd, str))
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\\nSTDERR: {result.stderr[-500:]}")
    return result

if _is_colab():
    repo_path = Path("/content") / REPO_NAME
    if not repo_path.exists():
        print(f"Cloning {REPO_URL} ...")
        try:
            from google.colab import userdata
            token = userdata.get("GITHUB_TOKEN")
            auth_url = REPO_URL.replace("https://", f"https://{token}@") if token else REPO_URL
        except Exception:
            auth_url = REPO_URL
        _run(["git", "clone", auth_url, str(repo_path)])
    else:
        print(f"Repo exists at {repo_path}, pulling latest ...")
        _run(["git", "-C", str(repo_path), "pull", "--quiet"])
else:
    nb_dir = Path.cwd()
    candidate = nb_dir
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / REPO_NAME).exists():
            repo_path = candidate
            break
        candidate = candidate.parent
    else:
        raise RuntimeError(f"Cannot locate repo root from {nb_dir}")

print(f"Repo path: {repo_path}")

print("Installing package (editable) ...")
_run([sys.executable, "-m", "pip", "install", "-e", str(repo_path), "--quiet"])

src_path = str(repo_path / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
    print(f"Injected into sys.path: {src_path}")

stale = [m for m in sys.modules if m.startswith("macro_context_reader")]
for m in stale:
    del sys.modules[m]
if stale:
    print(f"Cleared {len(stale)} stale cached modules")

REQUIRED_SECRETS = ["FRED_API_KEY"]
OPTIONAL_SECRETS = ["HF_TOKEN", "GITHUB_TOKEN"]

def _load_secret(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    if _is_colab():
        try:
            from google.colab import userdata
            val = userdata.get(name)
            if val:
                os.environ[name] = val
                return val
        except Exception:
            pass
    env_file = repo_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                val = line.split("=", 1)[1].strip().strip("\'\\"")
                os.environ[name] = val
                return val
    return None

for secret in REQUIRED_SECRETS + OPTIONAL_SECRETS:
    val = _load_secret(secret)
    status = "OK" if val else ("MISSING" if secret in REQUIRED_SECRETS else "not set (optional)")
    print(f"  {secret}: {status}")

try:
    import macro_context_reader
    print(f"\\nBootstrap complete. Package imported from: {macro_context_reader.__file__}")
except ImportError as e:
    raise RuntimeError(f"Bootstrap failed: {e}")
'''

CELL_02_LOAD = '''# CELL-02
print("[CELL-02]")

import pandas as pd
from macro_context_reader.economic_sentiment import load_cleveland_fed_indices, DISTRICT_NAMES

df = load_cleveland_fed_indices()
print(f"Publications: {len(df)}")
print(f"Date range: {df['publication_date'].min().date()} -> {df['publication_date'].max().date()}")
print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
df.head()
'''

CELL_03_DIST = '''# CELL-03
print("[CELL-03]")

import matplotlib.pyplot as plt

district_cols = [f"{d.replace(' ', '_').replace('.', '')}_score" for d in DISTRICT_NAMES]
stats = df[["national_score", "consensus_score"] + district_cols].describe().T
print(stats[["mean", "std", "min", "max"]].round(3))

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
df["national_score"].hist(bins=40, ax=axes[0], color="steelblue", edgecolor="black")
axes[0].set_title("National sentiment distribution")
axes[0].set_xlabel("score"); axes[0].axvline(0, color="red", linestyle="--", lw=1)

df["consensus_score"].hist(bins=40, ax=axes[1], color="seagreen", edgecolor="black")
axes[1].set_title("Consensus (district avg) distribution")
axes[1].set_xlabel("score"); axes[1].axvline(0, color="red", linestyle="--", lw=1)
plt.tight_layout(); plt.show()
'''

CELL_04_TS = '''# CELL-04
print("[CELL-04]")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

NBER_RECESSIONS = [
    ("1973-11", "1975-03"), ("1980-01", "1980-07"), ("1981-07", "1982-11"),
    ("1990-07", "1991-03"), ("2001-03", "2001-11"), ("2007-12", "2009-06"),
    ("2020-02", "2020-04"),
]

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(df["publication_date"], df["national_score"], label="National", lw=1.2, color="steelblue")
ax.plot(df["publication_date"], df["consensus_score"], label="Consensus (districts)", lw=1.2, color="seagreen")
ax.axhline(0, color="gray", lw=0.8, linestyle="--")

for start, end in NBER_RECESSIONS:
    ax.axvspan(pd.to_datetime(start), pd.to_datetime(end), alpha=0.2, color="red")

ax.set_title("Beige Book sentiment - National vs Consensus (shaded = NBER recession)")
ax.set_ylabel("Sentiment score"); ax.legend(loc="lower left")
ax.xaxis.set_major_locator(mdates.YearLocator(5))
plt.tight_layout(); plt.show()
'''

CELL_05_HEAT = '''# CELL-05
print("[CELL-05]")

import numpy as np
import matplotlib.pyplot as plt

recent = df[df["publication_date"] >= "2015-01-01"].copy()
recent["year"] = recent["publication_date"].dt.year
district_cols = [f"{d.replace(' ', '_').replace('.', '')}_score" for d in DISTRICT_NAMES]
annual = recent.groupby("year")[district_cols].mean()
annual.columns = DISTRICT_NAMES

fig, ax = plt.subplots(figsize=(12, 6))
im = ax.imshow(annual.T.values, aspect="auto", cmap="RdYlGn", vmin=-0.6, vmax=0.6)
ax.set_yticks(range(len(DISTRICT_NAMES))); ax.set_yticklabels(DISTRICT_NAMES)
ax.set_xticks(range(len(annual.index))); ax.set_xticklabels(annual.index, rotation=45)
ax.set_title("Annual mean sentiment by district (2015+)")
plt.colorbar(im, ax=ax, label="score"); plt.tight_layout(); plt.show()

vol = df[district_cols].std().sort_values(ascending=False)
vol.index = [c.replace("_score", "").replace("_", " ") for c in vol.index]
print("\\nCross-district volatility (std dev, full history):")
print(vol.round(3))
'''

CELL_06_DIVERGE = '''# CELL-06
print("[CELL-06]")

import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(df["publication_date"], df["national_consensus_divergence"], color="darkorange", lw=1)
ax.axhline(0, color="gray", lw=0.8, linestyle="--")
ax.set_title("National - Consensus divergence (positive = national more optimistic than districts)")
ax.set_ylabel("divergence"); plt.tight_layout(); plt.show()

print(f"\\nDivergence stats:")
print(f"  mean: {df['national_consensus_divergence'].mean():+.4f}")
print(f"  std:  {df['national_consensus_divergence'].std():.4f}")
print(f"  |div| > 0.1 in {100 * (df['national_consensus_divergence'].abs() > 0.1).mean():.1f}% of publications")
'''

CELL_07_XLAYER = '''# CELL-07
print("[CELL-07]")

# Optional cross-layer check: correlate consensus sentiment vs real rate differential (Layer 3).
# Non-blocking: if divergence module / FRED access is not wired, we skip cleanly.

try:
    from macro_context_reader.divergence.real_rate_differential import load_real_rate_differential
    rrd = load_real_rate_differential()
    merged = pd.merge_asof(
        df.sort_values("publication_date"),
        rrd.sort_values("date"),
        left_on="publication_date", right_on="date",
        direction="backward", tolerance=pd.Timedelta("45D"),
    ).dropna(subset=["real_rate_differential"])
    corr = merged[["consensus_score", "real_rate_differential"]].corr().iloc[0, 1]
    print(f"Consensus score vs real_rate_differential correlation: {corr:+.3f}")
    print(f"Overlapping observations: {len(merged)}")
except Exception as e:
    print(f"Cross-layer check skipped: {type(e).__name__}: {e}")
'''

CELL_08_VERDICT = '''<!-- CELL-08 -->
## Verdict criteria

- **COVID 2020-Q2** must show consensus_score < -0.3 (tested in `test_loader.py::test_covid_recession_shows_negative_sentiment`).
- **2008-2009 GFC** should show sustained consensus_score < 0.
- **2015-2019 expansion** should show mostly positive consensus_score.
- **National-consensus divergence** is a useful secondary signal when |div| > 0.15.

If all four pass visual inspection in cells above, the dataset is validated for use in the divergence/regime pipeline.
'''

CELL_00_MD = '''<!-- CELL-00 -->
# PRD-102: Economic Sentiment Validation (Cleveland Fed Beige Book Indices)

**Source:** Filippou, Garciga, Mitchell, Nguyen (2024). Federal Reserve Bank of Cleveland.
**ICPSR:** DOI 10.3886/E205881 (V13, 2025-11-28). License: CC BY-NC 4.0.
**Method:** FinBERT over Beige Book sentences, tone = (n_pos - n_neg) / (n_pos + n_neg).

**Objective:** Empirical exploration of pre-computed sentiment scores on Beige Book.

**Key questions:**
1. Do recessions (2008, 2020) show clear drops in sentiment?
2. National vs. consensus divergence - is the Fed narrative aligned with district reports?
3. Cross-district heterogeneity - which districts are most volatile?
4. Does sentiment correlate with real rate differential per regime?
'''

SETUP_MD = '''<!-- CELL-SETUP -->
## 1. Setup
'''


def md(src: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(src)


def code(src: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(src)


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb.cells = [
        md(CELL_00_MD),
        md(SETUP_MD),
        code(BOOTSTRAP),
        code(CELL_02_LOAD),
        code(CELL_03_DIST),
        code(CELL_04_TS),
        code(CELL_05_HEAT),
        code(CELL_06_DIVERGE),
        code(CELL_07_XLAYER),
        md(CELL_08_VERDICT),
    ]
    nbf.write(nb, NB_PATH)
    print(f"Wrote {NB_PATH}")


if __name__ == "__main__":
    main()
