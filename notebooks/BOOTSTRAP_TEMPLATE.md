# Notebook Bootstrap Standard

Reference for the standard bootstrap pattern used across all `notebooks/*.ipynb`.

## When to run each section

| Section | When |
|---------|------|
| **Setup** (bootstrap cell) | Every time you open the notebook in a new Colab session |
| **Clear cache** | Only after scraper or data pipeline logic changes (new scraper fix, schema change) |
| **Pipeline / Analysis** | After Setup completes successfully |

## Standard cell structure

Every notebook follows this order:

```
[0]  markdown   # Title + objective + run order
[1]  markdown   ## 1. Setup
[2]  code       <STANDARD BOOTSTRAP below>
[3]  markdown   ## 2. Clear cache (optional)
[4]  code       clear_cache()  # or equivalent
[5]  markdown   ## 3. <Main pipeline step>
[6]  code       <pipeline call>
[7+] ...        Analysis, plots, verdict
[N]  markdown   ## VERDICT or NEXT STEPS
```

## Standard bootstrap code (cell [2])

```python
import os, subprocess
from google.colab import userdata
from pathlib import Path

# --- Auth ---
try:
    token = userdata.get("GITHUB_TOKEN")
except Exception:
    raise RuntimeError("GITHUB_TOKEN lipsește din Colab Secrets")

user = "Inocenthhacker"
url = f"https://{user}:{token}@github.com/Inocenthhacker/macro_context_reader.git"

# --- Clone or pull ---
repo = Path("/content/macro_context_reader")
if repo.exists():
    subprocess.run(["git", "-C", str(repo), "pull", "--quiet"], check=True)
    print("✓ Pulled latest")
else:
    subprocess.run(["git", "clone", "--quiet", url, str(repo)], check=True)
    print("✓ Cloned")

# --- Install ---
os.chdir(repo)
subprocess.run(["pip", "install", "-e", ".", "--quiet"], check=True)
print("✓ Package installed (editable)")

# --- Env vars ---
for key in ["FRED_API_KEY", "DEEPINFRA_API_KEY", "HF_TOKEN"]:
    try:
        val = userdata.get(key)
        if val:
            os.environ[key] = val
            print(f"✓ {key} loaded")
    except Exception:
        print(f"⚠ {key} not in Secrets (optional for this notebook)")

print("\n✓ Bootstrap complete")
```

## Important notes

- The bootstrap already does `git pull` — do NOT add separate `git pull` cells.
- The bootstrap already does `os.chdir(repo)` — the working directory is the repo root after setup.
- The bootstrap already does `pip install -e .` — no need for separate install cells.
- Env vars that don't exist in Colab Secrets are silently skipped (warning printed, no error).
- `GITHUB_TOKEN` is the only required secret. All others are optional.
