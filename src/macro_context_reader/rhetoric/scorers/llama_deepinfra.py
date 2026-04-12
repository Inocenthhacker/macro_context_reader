"""Llama 3.3 70B scorer via DeepInfra — PRD-101 CC-1.

Uses OpenAI-compatible API with DeepInfra backend.
JSON mode for structured output. Budget tracking to prevent overspend.
Response caching to avoid redundant API calls.

Pricing (DeepInfra Turbo FP8): $0.23/1M input, $0.40/1M output tokens.

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from macro_context_reader.rhetoric.schemas import DocumentScore, SentenceScore

logger = logging.getLogger(__name__)

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
CACHE_DIR = Path("data/rhetoric/llama_cache")
INPUT_PRICE_PER_M = 0.23
OUTPUT_PRICE_PER_M = 0.40
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "You are a Federal Reserve policy expert. Classify the following sentence "
    "from FOMC communication as HAWKISH, DOVISH, or NEUTRAL regarding monetary "
    "policy stance.\n\n"
    "HAWKISH = signals tightening, inflation concern, rate hikes, reducing accommodation\n"
    "DOVISH = signals easing, growth/employment concern, rate cuts, increasing accommodation\n"
    "NEUTRAL = no clear policy signal, descriptive/factual statements\n\n"
    "Respond with JSON only: "
    '{\"label\": \"HAWKISH|DOVISH|NEUTRAL\", \"confidence\": 0.0-1.0}'
)


class BudgetExceededError(RuntimeError):
    """Raised when DeepInfra budget limit is exceeded."""


class BudgetTracker:
    """Track API spending against a hard limit."""

    def __init__(self, max_usd: float = 5.0) -> None:
        self.max_usd = max_usd
        self.spent_usd = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def can_proceed(self, estimated_input_tokens: int) -> bool:
        estimated_cost = (
            estimated_input_tokens * INPUT_PRICE_PER_M / 1_000_000
            + estimated_input_tokens * 0.1 * OUTPUT_PRICE_PER_M / 1_000_000
        )
        return (self.spent_usd + estimated_cost) < (self.max_usd * 0.8)

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.spent_usd = (
            self.total_input_tokens * INPUT_PRICE_PER_M / 1_000_000
            + self.total_output_tokens * OUTPUT_PRICE_PER_M / 1_000_000
        )
        if self.spent_usd >= self.max_usd:
            raise BudgetExceededError(
                f"Budget exceeded: ${self.spent_usd:.4f} >= ${self.max_usd}"
            )


class LlamaDeepInfraScorer:
    """Llama 3.3 70B scorer via DeepInfra API."""

    name: str = "llama_deepinfra"

    def __init__(self, max_budget_usd: float = 5.0) -> None:
        self.budget = BudgetTracker(max_usd=max_budget_usd)
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = os.environ.get("DEEPINFRA_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "DEEPINFRA_API_KEY not set. Get one at https://deepinfra.com/dash/api_keys"
            )
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://api.deepinfra.com/v1/openai",
            api_key=api_key,
        )
        return self._client

    def _cache_key(self, sentence: str) -> Path:
        h = hashlib.md5(sentence.encode()).hexdigest()[:16]
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"{h}.json"

    def _classify_single(self, sentence: str) -> dict:
        """Classify one sentence, using cache if available."""
        cache = self._cache_key(sentence)
        if cache.exists():
            return json.loads(cache.read_text())

        estimated_tokens = len(sentence.split()) * 2 + 200
        if not self.budget.can_proceed(estimated_tokens):
            raise BudgetExceededError(
                f"Budget safety stop: ${self.budget.spent_usd:.4f} spent, "
                f"limit ${self.budget.max_usd}"
            )

        client = self._get_client()
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f'Sentence: "{sentence}"'},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=100,
                )
                usage = response.usage
                if usage:
                    self.budget.record(
                        usage.prompt_tokens, usage.completion_tokens
                    )
                content = response.choices[0].message.content
                result = json.loads(content)
                # Normalize label
                result["label"] = result.get("label", "NEUTRAL").upper()
                if result["label"] not in ("HAWKISH", "DOVISH", "NEUTRAL"):
                    result["label"] = "NEUTRAL"
                result["confidence"] = float(result.get("confidence", 0.5))
                cache.write_text(json.dumps(result))
                return result
            except Exception as e:
                wait = 2 ** (attempt + 1)
                logger.warning("DeepInfra API error (%s), retry in %ds", e, wait)
                time.sleep(wait)

        return {"label": "NEUTRAL", "confidence": 0.0}

    def score_sentences(self, sentences: list[str]) -> list[SentenceScore]:
        results: list[SentenceScore] = []
        for idx, sent in enumerate(sentences):
            r = self._classify_single(sent)
            label = r["label"].lower()
            conf = r.get("confidence", 0.5)
            results.append(SentenceScore(
                sentence=sent,
                sentence_idx=idx,
                score_hawkish=conf if label == "hawkish" else (1 - conf) / 2,
                score_dovish=conf if label == "dovish" else (1 - conf) / 2,
                score_neutral=conf if label == "neutral" else (1 - conf) / 2,
                label=label,
                confidence=conf,
            ))
        return results

    def score_document_sentences(
        self, sentences: list[str], doc_date: datetime, doc_type: str
    ) -> DocumentScore:
        scores = self.score_sentences(sentences)
        n_h = sum(1 for s in scores if s.label == "hawkish")
        n_d = sum(1 for s in scores if s.label == "dovish")
        n_n = sum(1 for s in scores if s.label == "neutral")
        n_total = len(scores)
        return DocumentScore(
            doc_date=doc_date,
            doc_type=doc_type,
            scorer_name=self.name,
            n_sentences=n_total,
            n_hawkish=n_h,
            n_dovish=n_d,
            n_neutral=n_n,
            net_score=(n_h - n_d) / n_total if n_total > 0 else 0.0,
            mean_confidence=sum(s.confidence for s in scores) / n_total if n_total else 0.0,
        )
