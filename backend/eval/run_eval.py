"""
AIDA Evaluation Runner — powered by RAGAS
==========================================
Runs the eval dataset against the live RAG pipeline (real Pinecone + OpenRouter).
Scores each case with RAGAS metrics: faithfulness, answer_relevancy, context_recall.
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
    --skip-llm-metrics  skip faithfulness + answer_relevancy (no extra LLM calls for scoring)
    --verbose           print per-case details during the run

Exit codes:
    0   all cases passed (avg faithfulness and answer_relevancy >= 0.7)
    1   one or more metrics below threshold, or cases errored
    2   configuration or service error
"""

import argparse
import json
import logging
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Path setup — make backend/app/ importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # backend/eval/
_APP = _HERE.parent / "app"                      # backend/app/
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

# Suppress RAGAS/LangChain deprecation noise
warnings.filterwarnings("ignore", category=DeprecationWarning)

from services.ai_service import (  # noqa: E402
    answer_question,
    retrieve_chunks,
    embed_question,
    CHAT_MODEL,
)
from eval.dataset import DATASET, EvalCase  # noqa: E402
from eval.metrics import get_metrics  # noqa: E402

from ragas.dataset_schema import SingleTurnSample, EvaluationDataset  # noqa: E402
from ragas import evaluate  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("aida.eval")

# Quiet noisy third-party loggers
for _noisy in ("httpx", "openai", "langchain", "ragas"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
PASS_THRESHOLD_FAITHFULNESS = 0.7
PASS_THRESHOLD_RELEVANCY = 0.7


# ---------------------------------------------------------------------------
# Per-case RAG execution
# ---------------------------------------------------------------------------

def run_rag(case: EvalCase, user_id: str) -> dict:
    """
    Run the full RAG pipeline for one EvalCase.
    Returns a dict with answer, sources, chunks, latency_ms, and error.
    """
    result = {
        "answer": None,
        "sources": [],
        "chunks": [],
        "latency_ms": None,
        "error": None,
    }
    t0 = time.monotonic()
    try:
        embedding = embed_question(case.question)
        chunks, sources = retrieve_chunks(embedding, user_id)
        response = answer_question(case.question, user_id)
        result["answer"] = response["answer"]
        result["sources"] = response["sources"]
        result["chunks"] = chunks
    except Exception as e:
        result["error"] = str(e)
        logger.error("rag_failed question=%r error=%s", case.question[:60], e)
    finally:
        result["latency_ms"] = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIDA RAG evaluation runner (RAGAS)")
    parser.add_argument("--user_id", required=True)
    parser.add_argument("--tags", default="", help="comma-separated tags to filter dataset")
    parser.add_argument("--output", default="", help="path to write JSON results")
    parser.add_argument(
        "--skip-llm-metrics", action="store_true",
        help="skip RAGAS faithfulness + answer_relevancy scoring",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # --- Filter dataset ---
    tag_filter = {t.strip() for t in args.tags.split(",") if t.strip()}
    cases: List[EvalCase] = (
        [c for c in DATASET if tag_filter.intersection(c.tags)]
        if tag_filter else list(DATASET)
    )
    if not cases:
        logger.error("No eval cases match tags: %s", tag_filter)
        return 2

    logger.info("eval_start cases=%d user_id=%s model=%s", len(cases), args.user_id, CHAT_MODEL)

    # --- Step 1: run RAG for all cases ---
    rag_results = []
    for i, case in enumerate(cases, 1):
        logger.info("running case %d/%d: %s", i, len(cases), case.question[:60])
        rag_results.append(run_rag(case, args.user_id))

    # --- Step 2: score with RAGAS ---
    ragas_scores: List[dict] = [{} for _ in cases]
    failed_cases = [r for r in rag_results if r["error"]]

    if not args.skip_llm_metrics:
        # Build RAGAS EvaluationDataset — only include non-errored cases
        valid_indices = [i for i, r in enumerate(rag_results) if not r["error"]]
        samples = []
        for i in valid_indices:
            case = cases[i]
            r = rag_results[i]
            samples.append(SingleTurnSample(
                user_input=case.question,
                response=r["answer"],
                retrieved_contexts=r["chunks"] or [""],
                reference=case.ground_truth,
            ))

        if samples:
            logger.info("scoring %d samples with RAGAS...", len(samples))
            faithfulness_m, relevancy_m, recall_m = get_metrics()
            ragas_dataset = EvaluationDataset(samples=samples)
            ragas_result = evaluate(
                ragas_dataset,
                metrics=[faithfulness_m, relevancy_m, recall_m],
                show_progress=True,
            )
            df = ragas_result.to_pandas()
            for j, idx in enumerate(valid_indices):
                ragas_scores[idx] = {
                    "faithfulness": round(float(df.iloc[j]["faithfulness"]), 4)
                        if "faithfulness" in df.columns else None,
                    "answer_relevancy": round(float(df.iloc[j]["answer_relevancy"]), 4)
                        if "answer_relevancy" in df.columns else None,
                    "context_recall": round(float(df.iloc[j]["context_recall"]), 4)
                        if "context_recall" in df.columns else None,
                }

    # --- Step 3: assemble final results ---
    all_results = []
    for i, case in enumerate(cases):
        r = rag_results[i]
        s = ragas_scores[i]
        entry = {
            "question": case.question,
            "ground_truth": case.ground_truth,
            "tags": case.tags,
            "answer": r["answer"],
            "sources": r["sources"],
            "chunks_retrieved": len(r["chunks"]),
            "latency_ms": r["latency_ms"],
            "error": r["error"],
            "faithfulness": s.get("faithfulness"),
            "answer_relevancy": s.get("answer_relevancy"),
            "context_recall": s.get("context_recall"),
        }
        all_results.append(entry)
        if args.verbose:
            _print_case(entry)

    # --- Step 4: summary ---
    def _avg(key):
        vals = [r[key] for r in all_results if r[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    summary = {
        "total_cases": len(cases),
        "errors": len(failed_cases),
        "avg_faithfulness": _avg("faithfulness"),
        "avg_answer_relevancy": _avg("answer_relevancy"),
        "avg_context_recall": _avg("context_recall"),
        "avg_latency_ms": _avg("latency_ms"),
    }

    # --- Step 5: write output ---
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
        "ragas_version": _ragas_version(),
        "skip_llm_metrics": args.skip_llm_metrics,
        "summary": summary,
        "cases": all_results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("eval_done output=%s", output_path)

    # --- Step 6: print summary ---
    print("\n" + "=" * 60)
    print("EVAL SUMMARY  (RAGAS)")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<30} {v}")
    print(f"\n  Results written to: {output_path}")
    print("=" * 60)

    # --- Step 7: pass/fail ---
    if not args.skip_llm_metrics:
        faith = summary.get("avg_faithfulness") or 0.0
        rel = summary.get("avg_answer_relevancy") or 0.0
        if faith < PASS_THRESHOLD_FAITHFULNESS or rel < PASS_THRESHOLD_RELEVANCY:
            logger.warning(
                "eval_below_threshold faithfulness=%.2f answer_relevancy=%.2f",
                faith, rel,
            )
            return 1

    return 1 if failed_cases else 0


def _print_case(r: dict) -> None:
    print(f"\n  Q: {r['question']}")
    a = r['answer'] or ""
    print(f"  A: {a[:200]}{'...' if len(a) > 200 else ''}")
    print(f"  sources:          {r['sources']}")
    print(f"  chunks_retrieved: {r['chunks_retrieved']}")
    print(f"  faithfulness:     {r['faithfulness']}")
    print(f"  answer_relevancy: {r['answer_relevancy']}")
    print(f"  context_recall:   {r['context_recall']}")
    print(f"  latency_ms:       {r['latency_ms']}")
    if r["error"]:
        print(f"  ERROR: {r['error']}")


def _ragas_version() -> str:
    try:
        import ragas
        return ragas.__version__
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
