"""Reproducible dense-only versus hybrid+RRF evaluation.

The two configurations share the same corpus, final top-k, generator prompt,
generator model, and evaluator. Raw per-case evidence is persisted so the
aggregate numbers in RESULT.md remain auditable.
"""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import src.task10_generation as generation_module
from src.task5_semantic_search import semantic_search
from src.task6_lexical_search import lexical_search
from src.task7_reranking import rerank_rrf
from src.task10_generation import (
    SYSTEM_PROMPT,
    call_llm,
    format_context,
    reorder_for_llm,
)


ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = EVALUATION_DIR / "golden_dataset.json"
OUTPUT_PATH = EVALUATION_DIR / "evaluation_results.json"
TOP_K = 5
CANDIDATE_K = 10
RRF_K = 60
GENERATOR_MODEL = os.getenv("EVALUATION_GENERATOR_MODEL", "gemini-3.1-flash-lite")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gemini-3.5-flash-lite")

JUDGE_PROMPT = """Bạn là evaluator nghiêm ngặt cho hệ thống RAG tiếng Việt.
Chấm bốn metric trong khoảng 0.0 đến 1.0, không ưu ái cách diễn đạt giống đáp án:
- faithfulness: mọi khẳng định trong câu trả lời có được retrieved context hỗ trợ không.
- answer_relevance: câu trả lời có trực tiếp và đầy đủ giải quyết câu hỏi không.
- context_recall: retrieved context có chứa đủ bằng chứng trong expected answer/context không.
- context_precision: các chunk retrieved có tập trung vào câu hỏi hay chứa nhiều nhiễu.

Failure stage là "data", "retrieval", "generation" hoặc "none". Data chỉ dùng khi
golden/reference có vấn đề; retrieval khi thiếu hoặc nhiễu evidence; generation khi
context đúng nhưng câu trả lời sai/thiếu/bịa. Chỉ trả về một JSON object hợp lệ với
các key: faithfulness, answer_relevance, context_recall, context_precision,
failure_stage, rationale. Rationale ngắn, nêu bằng chứng cụ thể."""


def retrieve_for_config(question: str, config: str) -> list[dict]:
    if config == "A":
        return semantic_search(question, top_k=TOP_K)
    if config == "B":
        dense = semantic_search(question, top_k=CANDIDATE_K)
        lexical = lexical_search(question, top_k=CANDIDATE_K)
        return rerank_rrf([dense, lexical], top_k=TOP_K, k=RRF_K)
    raise ValueError(f"Unknown config: {config}")


def generate(question: str, sources: list[dict]) -> str:
    citation_indexes = {
        source["id"]: index for index, source in enumerate(sources, 1)
    }
    reordered = reorder_for_llm(deepcopy(sources))
    context_chunks = [
        {**chunk, "_citation_index": citation_indexes[chunk["id"]]}
        for chunk in reordered
    ]
    context = format_context(context_chunks)
    return call_llm(
        SYSTEM_PROMPT,
        f"Context:\n{context}\n\nQuestion: {question.strip()}",
    )


def _judge_client():
    from google import genai

    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=key)


def judge(client, case: dict, answer: str, sources: list[dict]) -> dict:
    from google.genai import types

    evidence = [
        {
            "rank": rank,
            "id": source["id"],
            "title": source["metadata"]["title"],
            "content": source["content"],
        }
        for rank, source in enumerate(sources, 1)
    ]
    payload = {
        "question": case["question"],
        "expected_answer": case["expected_answer"],
        "expected_context": case["expected_context"],
        "generated_answer": answer,
        "retrieved_contexts": evidence,
    }
    response = client.models.generate_content(
        model=EVALUATOR_MODEL,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_PROMPT,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    result = json.loads(response.text)
    for metric in (
        "faithfulness",
        "answer_relevance",
        "context_recall",
        "context_precision",
    ):
        result[metric] = min(1.0, max(0.0, float(result[metric])))
    if result.get("failure_stage") not in {
        "data", "retrieval", "generation", "none"
    }:
        result["failure_stage"] = "retrieval"
    return result


def _load_output() -> dict:
    if OUTPUT_PATH.exists():
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return {"run": {}, "results": []}


def _save(output: dict) -> None:
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    load_dotenv(ROOT / ".env")
    # Evaluation can use a quota-available model without changing the app's .env.
    # The override is process-local and identical for configurations A and B.
    generation_module.LLM_MODEL = GENERATOR_MODEL
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if len(cases) < 15:
        raise ValueError("Golden dataset must contain at least 15 cases")

    output = _load_output()
    output["run"] = {
        "evaluation_date": datetime.now(timezone.utc).astimezone().isoformat(),
        "framework": "custom Gemini rubric judge aligned with RAGAS definitions",
        "evaluator_model": EVALUATOR_MODEL,
        "generator_model": GENERATOR_MODEL,
        "embedding_model": "keepitreal/vietnamese-sbert",
        "corpus_commit": os.popen("git rev-parse HEAD").read().strip(),
        "golden_dataset_size": len(cases),
        "top_k": TOP_K,
        "candidate_k_for_rrf": CANDIDATE_K,
        "rrf_k": RRF_K,
        "fallback_threshold": 0.45,
    }
    completed = {
        (item["case_index"], item["config"]) for item in output["results"]
    }
    client = _judge_client()

    for case_index, case in enumerate(cases, 1):
        for config in ("A", "B"):
            if (case_index, config) in completed:
                continue
            print(f"Evaluating case {case_index:02d}/{len(cases)} config {config}")
            retrieval_started = time.perf_counter()
            sources = retrieve_for_config(case["question"], config)
            retrieval_seconds = time.perf_counter() - retrieval_started

            generation_started = time.perf_counter()
            for attempt in range(5):
                try:
                    answer = generate(case["question"], sources)
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(2 ** attempt)
            generation_seconds = time.perf_counter() - generation_started

            last_error = None
            for attempt in range(5):
                try:
                    scores = judge(client, case, answer, sources)
                    break
                except Exception as exc:  # retry transient API/JSON failures
                    last_error = exc
                    if attempt == 4:
                        raise
                    time.sleep(2 ** attempt)
            else:  # pragma: no cover
                raise RuntimeError(last_error)

            output["results"].append(
                {
                    "case_index": case_index,
                    "config": config,
                    "question": case["question"],
                    "answer": answer,
                    "source_ids": [source["id"] for source in sources],
                    "source_titles": [
                        source["metadata"]["title"] for source in sources
                    ],
                    "retrieval_seconds": round(retrieval_seconds, 6),
                    "generation_seconds": round(generation_seconds, 6),
                    "scores": scores,
                }
            )
            _save(output)

    metrics = (
        "faithfulness",
        "answer_relevance",
        "context_recall",
        "context_precision",
    )
    summary = {}
    for config in ("A", "B"):
        rows = [row for row in output["results"] if row["config"] == config]
        summary[config] = {
            metric: sum(row["scores"][metric] for row in rows) / len(rows)
            for metric in metrics
        }
        summary[config]["average"] = sum(summary[config].values()) / len(metrics)
        summary[config]["mean_retrieval_seconds"] = sum(
            row["retrieval_seconds"] for row in rows
        ) / len(rows)
        summary[config]["mean_generation_seconds"] = sum(
            row["generation_seconds"] for row in rows
        ) / len(rows)
    output["summary"] = summary
    _save(output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
