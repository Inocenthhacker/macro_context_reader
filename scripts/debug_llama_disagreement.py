"""Debug script: side-by-side 3-scorer comparison on known FOMC sentences.

Diagnoses Llama DeepInfra disagreement with FOMC-RoBERTa and FinBERT-FOMC.
Uses 5 hand-picked FOMC sentences with known expert labels to measure
accuracy of each scorer independently.

Designed for Google Colab with HF_TOKEN and DEEPINFRA_API_KEY in Secrets.
Falls back to env vars on local machines.

Usage (Colab):
    !python scripts/debug_llama_disagreement.py

Usage (local):
    HF_TOKEN=... DEEPINFRA_API_KEY=... python scripts/debug_llama_disagreement.py

Requires: all 3 scorer models available (HuggingFace cache or download).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Colab Secrets loader — must run before any HuggingFace / OpenAI import
# ---------------------------------------------------------------------------

def _load_secrets_colab() -> None:
    """Load secrets from Colab userdata if running in Colab."""
    try:
        from google.colab import userdata
        for key in ["HF_TOKEN", "DEEPINFRA_API_KEY"]:
            if not os.environ.get(key):
                try:
                    val = userdata.get(key)
                    if val:
                        os.environ[key] = val
                        print(f"  Loaded {key} from Colab Secrets")
                except Exception:
                    pass
    except ImportError:
        pass  # Not running in Colab

_load_secrets_colab()

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from macro_context_reader.rhetoric.scorers.fomc_roberta import FOMCRobertaScorer
from macro_context_reader.rhetoric.scorers.finbert_fomc import FinBERTFOMCScorer
from macro_context_reader.rhetoric.scorers.llama_deepinfra import (
    LlamaDeepInfraScorer,
    SYSTEM_PROMPT as LLAMA_SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# Test corpus — 5 FOMC sentences with expert ground-truth labels
# ---------------------------------------------------------------------------

TEST_CASES: list[tuple[str, str]] = [
    # (sentence, expert_label)
    # 1. Clearly hawkish — rate hikes to fight inflation
    (
        "The Committee will continue to raise rates to combat inflation.",
        "hawkish",
    ),
    # 2. Clearly dovish — rate cuts to support employment
    (
        "The Committee will cut rates to support employment.",
        "dovish",
    ),
    # 3. Ambiguous — easing language but inflation still high (net: hawkish)
    (
        "Inflation has eased over the past year but remains elevated.",
        "hawkish",
    ),
    # 4. Forward guidance hawkish — ongoing increases
    (
        "The Committee anticipates that ongoing increases in the target range will be appropriate.",
        "hawkish",
    ),
    # 5. Forward guidance dovish — downside risks rising
    (
        "The Committee judges that downside risks to employment have increased.",
        "dovish",
    ),
]


def main() -> None:
    lines: list[str] = []

    def out(line: str = "") -> None:
        lines.append(line)
        print(line)

    out("=" * 80)
    out("LLAMA DISAGREEMENT DEBUG REPORT  (3-scorer, 5 known sentences)")
    out(f"Generated: {datetime.now().isoformat()}")
    out("=" * 80)

    # ---- Check required secrets ----
    out("\n[0] CHECKING CREDENTIALS...")
    hf_token = os.environ.get("HF_TOKEN", "")
    di_key = os.environ.get("DEEPINFRA_API_KEY", "")

    if hf_token:
        out(f"  HF_TOKEN:          set ({len(hf_token)} chars)")
    else:
        out("  HF_TOKEN:          MISSING")
        out("  -> FOMC-RoBERTa needs HF auth (gated repo).")
        out("  -> Set HF_TOKEN in Colab Secrets or environment.")
        out("  ABORTING.")
        sys.exit(1)

    if di_key:
        out(f"  DEEPINFRA_API_KEY: set ({len(di_key)} chars)")
    else:
        out("  DEEPINFRA_API_KEY: MISSING")
        out("  -> Llama scorer needs DeepInfra API key.")
        out("  -> Set DEEPINFRA_API_KEY in Colab Secrets or environment.")
        out("  ABORTING.")
        sys.exit(1)

    # ---- Load all 3 scorers ----
    out("\n[1] LOADING SCORERS...")

    roberta = FOMCRobertaScorer()
    # Force model load now so errors surface early
    roberta._load_model()
    out("  FOMC-RoBERTa:  loaded")

    finbert = FinBERTFOMCScorer()
    finbert._load_model()
    out("  FinBERT-FOMC:  loaded")

    llama = LlamaDeepInfraScorer(max_budget_usd=1.0)
    out("  Llama-70B:     ready (API)")

    # ---- Score all sentences ----
    out("\n[2] SCORING 5 SENTENCES WITH ALL 3 SCORERS...")

    sentences = [t[0] for t in TEST_CASES]
    expert_labels = [t[1] for t in TEST_CASES]

    roberta_scores = roberta.score_sentences(sentences)
    out("  FOMC-RoBERTa:  done")

    finbert_scores = finbert.score_sentences(sentences)
    out("  FinBERT-FOMC:  done")

    llama_scores = llama.score_sentences(sentences)
    out("  Llama-70B:     done")

    # ---- Print Llama prompt for reference ----
    out("\n" + "=" * 80)
    out("LLAMA SYSTEM PROMPT (from scorers/llama_deepinfra.py):")
    out("-" * 80)
    out(LLAMA_SYSTEM_PROMPT)
    out("-" * 80)
    out('User message template: Sentence: "{sentence}"')
    out("=" * 80)

    # ---- Side-by-side comparison ----
    out("\n" + "=" * 80)
    out("SIDE-BY-SIDE SENTENCE COMPARISON")
    out("=" * 80)

    # Track per-scorer correctness
    correct = {"fomc_roberta": 0, "finbert_fomc": 0, "llama_deepinfra": 0}
    n_disagree = 0

    for i, (sent, expert) in enumerate(TEST_CASES):
        r = roberta_scores[i]
        f = finbert_scores[i]
        ll = llama_scores[i]

        out(f"\n{'-' * 80}")
        out(f"SENTENCE {i + 1}:")
        for line in textwrap.wrap(sent, width=76, initial_indent="  ", subsequent_indent="  "):
            out(line)

        out(f"\n  EXPERT JUDGMENT:   {expert.upper()}")
        out("")
        out(f"  FOMC-RoBERTa:      label={r.label:<10} conf={r.confidence:.3f}  "
            f"h={r.score_hawkish:.3f} d={r.score_dovish:.3f} n={r.score_neutral:.3f}"
            f"  {'OK' if r.label == expert else 'WRONG'}")
        out(f"  FinBERT-FOMC:      label={f.label:<10} conf={f.confidence:.3f}  "
            f"h={f.score_hawkish:.3f} d={f.score_dovish:.3f} n={f.score_neutral:.3f}"
            f"  {'OK' if f.label == expert else 'WRONG'}")

        # Llama — also show raw cached response
        llama_extra = ""
        cache_path = (
            ROOT / "data" / "rhetoric" / "llama_cache"
            / f"{hashlib.md5(sent.encode()).hexdigest()[:16]}.json"
        )
        if cache_path.exists():
            raw = json.loads(cache_path.read_text())
            llama_extra = f"  raw={json.dumps(raw)}"

        out(f"  Llama-70B:         label={ll.label:<10} conf={ll.confidence:.3f}  "
            f"h={ll.score_hawkish:.3f} d={ll.score_dovish:.3f} n={ll.score_neutral:.3f}"
            f"  {'OK' if ll.label == expert else 'WRONG'}")
        if llama_extra:
            out(f"  Llama raw resp:   {llama_extra}")

        # Correctness
        if r.label == expert:
            correct["fomc_roberta"] += 1
        if f.label == expert:
            correct["finbert_fomc"] += 1
        if ll.label == expert:
            correct["llama_deepinfra"] += 1

        # Disagreements
        all_labels = [r.label, f.label, ll.label]
        if len(set(all_labels)) > 1:
            n_disagree += 1
            pairs = []
            if r.label != f.label:
                pairs.append(f"RoBERTa({r.label}) vs FinBERT({f.label})")
            if r.label != ll.label:
                pairs.append(f"RoBERTa({r.label}) vs Llama({ll.label})")
            if f.label != ll.label:
                pairs.append(f"FinBERT({f.label}) vs Llama({ll.label})")
            out(f"  >>> DISAGREEMENT:  {'; '.join(pairs)}")
        else:
            out(f"  >>> AGREEMENT:     all={all_labels[0]}")

    # ---- Accuracy table ----
    n = len(TEST_CASES)
    out(f"\n{'=' * 80}")
    out("ACCURACY SUMMARY")
    out(f"{'=' * 80}")
    out(f"{'Model':<20} | {'Correct / Total':>15} | {'Accuracy':>8}")
    out(f"{'-' * 20}-+-{'-' * 15}-+-{'-' * 8}")
    for key, display in [
        ("fomc_roberta", "FOMC-RoBERTa"),
        ("finbert_fomc", "FinBERT-FOMC"),
        ("llama_deepinfra", "Llama-70B"),
    ]:
        c = correct[key]
        out(f"{display:<20} | {c:>7} / {n:<5}   | {100 * c / n:>6.0f}%")

    out(f"\nSentences with disagreement: {n_disagree}/{n}")

    # ---- Known issues ----
    out(f"\n{'=' * 80}")
    out("POTENTIAL ISSUES IDENTIFIED")
    out(f"{'=' * 80}")
    out("  1. LLAMA SYNTHETIC PROBABILITIES (llama_deepinfra.py:159-165):")
    out("     score_X = confidence if label==X else (1-confidence)/2")
    out("     This fabricates a distribution from one scalar. FOMC-RoBERTa and")
    out("     FinBERT output real softmax probs. Ensemble weighting is distorted.")
    out("")
    out("  2. FINBERT SENTIMENT != POLICY STANCE (finbert_fomc.py:36-40):")
    out("     Positive->hawkish / Negative->dovish works for economic conditions")
    out("     but inverts on sentences describing policy CHANGES or mixed signals")
    out("     (e.g., 'inflation has eased' = Negative sentiment = dovish,")
    out("     but sentence means inflation is STILL HIGH = hawkish intent).")
    out("")
    out("  3. LLAMA PROMPT AMBIGUITY (llama_deepinfra.py:32-41):")
    out("     'inflation concern' in HAWKISH def is vague. Fed acknowledging")
    out("     inflation is easing still mentions 'inflation' -> could be hawkish.")
    out("     'growth/employment concern' in DOVISH def: 'strong employment'")
    out("     mentions employment but is hawkish, not dovish.")
    out("")
    out("  4. FOMC-ROBERTA AS GROUND TRUTH:")
    out("     Purpose-trained on FOMC text (Shah et al. ACL 2023). Should be")
    out("     treated as most reliable for FOMC statements specifically.")

    # ---- Write report ----
    report_path = Path(tempfile.gettempdir()) / "llama_debug_report.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    out(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
