"""
AIDA Evaluation Runner
======================
Runs the eval dataset against the live RAG pipeline (real Pinecone + OpenRouter).
Documents must already be indexed in Pinecone before running.

Usage (from backend/):
    uv run python -m eval.run_eval --user_id <your_eval_user_id>
    uv run python -m eval.run_eval --user_id eval_user --tags factual
    uv run python -m eval.run_eval --user_id eval_user --output results/my_run.json
    uv run python -m eval.run_eval --user_id eval_user --skip-llm-metrics

Options:
    --user_id           (required) user_id whose indexed documents to query
    --tags              comma-separated tags to filter dataset cases (default: all)
    --output            path to write JSON results (default: results/run_<timestamp>.json)
    --skip-llm-metrics  run only context_recall (no OpenRouter calls for scoring)
    --verbose           print per-case details during the run

Exit codes:
    0   all cases passed (avg faithfulness and answer_relevance >= 0.7)
    1   one or more cases below threshold
    2   run failed due to a configuration or service error
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Path setup — make backend/app/ importable (mirrors conftest.py approach)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # backend/eval/
_APP = _HERE.parent / "app"                      # backend/app/
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

# Now we can import app modules
from core.config import settings  # noqa: E402
from services.ai_service import (  # noqa: E402
    answer_question,
    retrieve_chunks,
    embed_question,
    CHAT_MODEL,
)
from eval.dataset import DATASET, EvalCase  # noqa: E402
from eval.metrics import (  # noqa: E402
    context_recall,
    faithfulness,
    answer_relevance,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("aida.eval")

# ---------------------------------------------------------------------------
# Thresholds (fail the run if averages fall below these)
# ---------------------------------------------------------------------------
PASS_THRESHOLD_FAITHFULNESS = 0.7
PASS_THRESHOLD_RELEVANCE = 0.7


# ---------------------------------------------------------------------------
# Per-case runner
# ---------------------------------------------------------------------------

def run_case(
    case: EvalCase,
    user_id: str,
    skip_llm_metrics: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run a single EvalCase and return a result dict.

    Steps:
    1. Embed the question.
    2. Retrieve chunks from Pinecone.
    3. Build an answer via answer_question().
    4. Score with the three metrics.
    """
    result: dict = {
        "question": case.question,
        "ground_truth": case.ground_truth,
        "key_facts": case.key_facts,
        "expected_sources": case.expected_sources,
        "tags": case.tags,
        "answer": None,
        "sources": [],
        "chunks": [],
        "context_recall": None,
        "faithfulness": None,
        "answer_relevance": None,
        "error": None,
        "latency_ms": None,
    }

    t0 = time.monotonic()
    try:
        # --- Retrieve (separately so we can expose chunks for scoring) ---
        embedding = embed_question(case.question)
        chunks, sources = retrieve_chunks(embedding, user_id)

        # --- Generate answer ---
        response = answer_question(case.question, user_id)
        answer = response["answer"]
        answer_sources = response["sources"]

        latency_ms = int((time.monotonic() - t0) * 1000)

        result["answer"] = answer
        result["sources"] = answer_sources
        result["chunks"] = chunks
        result["latency_ms"] = latency_ms

        # --- Score ---
        result["context_recall"] = context_recall(case.key_facts, chunks)

        if not skip_llm_metrics:
            result["faithfulness"] = faithfulness(answer, chunks)
            result["answer_relevance"] = answer_relevance(case.question, answer)

        if verbose:
            _print_case(result)

    except Exception as e:
        result["error"] = str(e)
        result["latency_ms"] = int((time.monotonic() - t0) * 1000)
        logger.error("case_failed question=%r error=%s", case.question[:60], e)

    return result


def _print_case(r: dict) -> None:
    print(f"\n  Q: {r['question']}")
    print(f"  A: {r['answer'][:200]}{'...' if r['answer'] and len(r['answer']) > 200 else ''}")
    print(f"  sources: {r['sources']}")
    print(f"  context_recall:   {r['context_recall']}")
    print(f"  faithfulness:     {r['faithfulness']}")
    print(f"  answer_relevance: {r['answer_relevance']}")
    print(f"  latency_ms:       {r['latency_ms']}")
    if r["error"]:
        print(f"  ERROR: {r['error']}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _avg(values: List[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    return round(sum(nums) / len(nums), 4) if nums else None


def build_summary(cases: List[dict]) -> dict:
    return {
        "total_cases": len(cases),
        "errors": sum(1 for c in cases if c["error"]),
        "avg_context_recall": _avg([c["context_recall"] for c in cases]),
        "avg_faithfulness": _avg([c["faithfulness"] for c in cases]),
        "avg_answer_relevance": _avg([c["answer_relevance"] for c in cases]),
        "avg_latency_ms": _avg([c["latency_ms"] for c in cases]),
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIDA RAG evaluation runner")
    parser.add_argument("--user_id", required=True, help="user_id whose Pinecone docs to query")
    parser.add_argument(
        "--tags",
        default="",
        help="comma-separated tags to filter dataset (default: run all cases)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="path to write JSON results (default: eval/results/run_<timestamp>.json)",
    )
    parser.add_argument(
        "--skip-llm-metrics",
        action="store_true",
        help="skip faithfulness and answer_relevance (faster, no extra LLM calls)",
    )
    parser.add_argument("--verbose", action="store_true", help="print per-case output")
    args = parser.parse_args()

    # --- Filter dataset ---
    tag_filter = {t.strip() for t in args.tags.split(",") if t.strip()}
    cases: List[EvalCase] = (
        [c for c in DATASET if tag_filter.intersection(c.tags)]
        if tag_filter
        else list(DATASET)
    )

    if not cases:
        logger.error("No eval cases match the given tags: %s", tag_filter)
        return 2

    logger.info("eval_start cases=%d user_id=%s model=%s", len(cases), args.user_id, CHAT_MODEL)

    # --- Run ---
    results = []
    for i, case in enumerate(cases, 1):
        logger.info("case %d/%d: %s", i, len(cases), case.question[:60])
        result = run_case(
            case,
            user_id=args.user_id,
            skip_llm_metrics=args.skip_llm_metrics,
            verbose=args.verbose,
        )
        results.append(result)

    summary = build_summary(results)

    # --- Output ---
    output_path = args.output
    if not output_path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = _HERE / "results"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / f"run_{ts}.json")

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "user_id": args.user_id,
        "model": CHAT_MODEL,
        "skip_llm_metrics": args.skip_llm_metrics,
        "summary": summary,
        "cases": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("eval_done output=%s", output_path)

    # --- Print summary ---
    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<30} {v}")
    print(f"\n  Results written to: {output_path}")
    print("=" * 60)

    # --- Pass/fail ---
    if not args.skip_llm_metrics:
        faith = summary.get("avg_faithfulness") or 0.0
        rel = summary.get("avg_answer_relevance") or 0.0
        if faith < PASS_THRESHOLD_FAITHFULNESS or rel < PASS_THRESHOLD_RELEVANCE:
            logger.warning(
                "eval_below_threshold faithfulness=%.2f relevance=%.2f thresholds=%.2f/%.2f",
                faith, rel, PASS_THRESHOLD_FAITHFULNESS, PASS_THRESHOLD_RELEVANCE,
            )
            return 1

    if summary["errors"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
