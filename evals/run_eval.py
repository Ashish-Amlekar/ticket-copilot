"""Evaluation harness with a pass/fail gate.

Retrieval eval (default): deterministic, no LLM, free. Answers "does the right
documentation come back for this ticket?" with hit rate and MRR.
    python -m evals.run_eval

End-to-end eval (--llm): runs the full pipeline with the configured model and
checks structure and grounding: valid JSON schema, citations point at retrieved
chunks, docs_gap detected on out-of-scope tickets, category matches.
    python -m evals.run_eval --llm --prompt v1

Every run appends a row to evals/history.csv (trend over time) and exits with
code 1 if a metric is below evals/thresholds.yaml. That exit code is the CI gate.
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from app import config
from app.pipeline import TriageError, TriagePipeline
from app.prompts import load_prompt
from app.retrieval import build_retriever, load_chunks
from app.schemas import Ticket

EVALS = Path(__file__).parent
GOLDEN = EVALS / "golden.jsonl"
THRESHOLDS = EVALS / "thresholds.yaml"
HISTORY = EVALS / "history.csv"


def load_golden() -> list[dict]:
    return [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]


def retrieval_eval(retriever, k: int) -> dict:
    """hit_rate@k and MRR over tickets that have a known answer chunk."""
    hits, rr, n = 0, 0.0, 0
    for case in load_golden():
        expected = set(case["expected_chunks"])
        if not expected:  # docs-gap cases have no right chunk to find
            continue
        n += 1
        results = retriever.search(f"{case['subject']}\n{case['body']}", k=k)
        ranked = [c.chunk_id for c, _ in results]
        first = next((i for i, cid in enumerate(ranked) if cid in expected), None)
        if first is not None:
            hits += 1
            rr += 1.0 / (first + 1)
    return {"hit_rate_at_k": hits / n, "mrr": rr / n, "cases": n}


def end_to_end_eval(pipeline: TriagePipeline) -> dict:
    cases = load_golden()
    valid = cites_ok = cites_total = gap_ok = cat_ok = 0
    failures = []
    for case in cases:
        try:
            resp = pipeline.run(Ticket(subject=case["subject"], body=case["body"], ticket_id=case["id"]))
        except TriageError as exc:
            failures.append((case["id"], str(exc)))
            continue
        valid += 1
        cites_total += len(resp.analysis.citations) + len(resp.meta.dropped_citations)
        cites_ok += len(resp.analysis.citations)
        gap_ok += resp.analysis.docs_gap == case["docs_gap"]
        cat_ok += resp.analysis.category.value == case["category"]
    n = len(cases)
    return {
        "schema_valid_rate": valid / n,
        "citation_valid_rate": (cites_ok / cites_total) if cites_total else 1.0,
        "docs_gap_accuracy": gap_ok / n,
        "category_accuracy": cat_ok / n,
        "cases": n,
        "failures": failures,
    }


def check_gate(scores: dict, section: str) -> list[str]:
    limits = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))[section]
    return [
        f"{name}: {scores[name]:.2f} < {minimum:.2f}"
        for name, minimum in limits.items()
        if scores[name] < minimum
    ]


HISTORY_COLUMNS = [
    "timestamp", "kind", "label", "cases",
    "hit_rate_at_k", "mrr",
    "schema_valid_rate", "citation_valid_rate", "docs_gap_accuracy", "category_accuracy",
]


def append_history(kind: str, label: str, scores: dict) -> None:
    """One row per run. Fixed columns, so retrieval and end-to-end rows share one file."""
    row = {column: "" for column in HISTORY_COLUMNS}
    row.update({"timestamp": datetime.now().isoformat(timespec="seconds"), "kind": kind, "label": label})
    for name, value in scores.items():
        if name in row:
            row[name] = round(value, 3) if isinstance(value, float) else value
    is_new = not HISTORY.exists() or HISTORY.stat().st_size == 0
    with open(HISTORY, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run the end-to-end eval (needs a model)")
    ap.add_argument("--prompt", default=config.PROMPT_VERSION)
    ap.add_argument("--no-history", action="store_true")
    args = ap.parse_args()

    retriever = build_retriever(load_chunks(config.KB_PATH), config.RETRIEVER, config.EMBEDDING_MODEL)
    label = f"{config.RETRIEVER}|k={config.TOP_K}"
    failed: list[str] = []

    scores = retrieval_eval(retriever, config.TOP_K)
    print(f"Retrieval ({label}, {scores['cases']} cases): "
          f"hit_rate@{config.TOP_K}={scores['hit_rate_at_k']:.2f}  MRR={scores['mrr']:.2f}")
    failed += check_gate(scores, "retrieval")
    if not args.no_history:
        append_history("retrieval", label, scores)

    if args.llm:
        from app.llm import LiteLLMClient

        pipeline = TriagePipeline(
            retriever,
            LiteLLMClient(config.LLM_MODEL, config.LLM_TEMPERATURE),
            load_prompt(version=args.prompt),
            top_k=config.TOP_K,
        )
        e2e = end_to_end_eval(pipeline)
        print(f"End-to-end ({config.LLM_MODEL}, prompt {args.prompt}): "
              + "  ".join(f"{k}={v:.2f}" for k, v in e2e.items() if isinstance(v, float)))
        for case_id, err in e2e["failures"]:
            print(f"  FAILED {case_id}: {err}")
        failed += check_gate(e2e, "end_to_end")
        if not args.no_history:
            append_history("end_to_end", f"{config.LLM_MODEL}|{args.prompt}", e2e)

    if failed:
        print("\nEVAL GATE FAILED:\n  " + "\n  ".join(failed))
        return 1
    print("\nEval gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())