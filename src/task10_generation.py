"""Task 10: grounded generation with verifiable citations."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

from .contracts import validate_generation_result
from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ các nguồn hiện có."
SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp về quy chế đào tạo đại học.
Chỉ trả lời bằng bằng chứng trong Context. Mỗi khẳng định thực tế phải dẫn nguồn
bằng nhãn [Document N]. Nếu Context không đủ bằng chứng, hãy nói rõ rằng không
thể xác minh; không suy đoán hoặc tự bổ sung thông tin."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Place high-ranked chunks near both ends without mutating the input."""
    copied = [{**chunk, "metadata": dict(chunk["metadata"])} for chunk in chunks]
    if len(copied) <= 2:
        return copied
    return copied[::2] + copied[1::2][::-1]


def format_context(chunks: list[dict]) -> str:
    """Format chunks with stable labels that the model can cite."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        citation_index = chunk.get("_citation_index", index)
        metadata = chunk["metadata"]
        source = metadata["source"]
        title = metadata["title"]
        url = metadata.get("url") or "N/A"
        chunk_index = metadata.get("chunk_index", "N/A")
        parts.append(
            f"[Document {citation_index}]\n"
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"URL: {url}\n"
            f"Chunk: {chunk_index}\n"
            f"Content:\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call the configured OpenAI, Gemini, or Anthropic provider."""
    if not LLM_MODEL:
        raise RuntimeError("LLM_MODEL is not configured")

    if LLM_PROVIDER == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        text = response.choices[0].message.content
    elif LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        response = genai.Client(api_key=api_key).models.generate_content(
            model=LLM_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                top_p=TOP_P,
            ),
        )
        text = response.text
    elif LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        response = Anthropic(api_key=api_key).messages.create(
            model=LLM_MODEL,
            max_tokens=1200,
            temperature=TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("LLM returned an empty response")
    return text.strip()


def _safe_result() -> dict[str, Any]:
    result: dict[str, Any] = {
        "answer": SAFE_REFUSAL,
        "sources": [],
        "retrieval_source": "none",
    }
    validate_generation_result(result)
    return result


def _citation_labels_are_valid(answer: str, source_count: int) -> bool:
    """Require at least one citation and reject labels absent from sources."""
    labels = [int(value) for value in re.findall(r"\[Document\s+(\d+)\]", answer)]
    return bool(labels) and all(1 <= label <= source_count for label in labels)


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve evidence, generate an answer, and return GenerationResult."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return _safe_result()

    try:
        chunks = retrieve(query.strip(), top_k=top_k)
        if not chunks:
            return _safe_result()

        # Labels are assigned in the original score-sorted order returned as
        # ``sources``. Reordering then changes only context position, never the
        # citation-to-source mapping used by the UI.
        labelled_chunks = [
            {**chunk, "metadata": dict(chunk["metadata"]), "_citation_index": index}
            for index, chunk in enumerate(chunks, start=1)
        ]
        context = format_context(reorder_for_llm(labelled_chunks))
        answer = call_llm(
            SYSTEM_PROMPT,
            f"Context:\n{context}\n\nQuestion: {query.strip()}",
        )
    except Exception:
        return _safe_result()

    if not _citation_labels_are_valid(answer, len(chunks)):
        return _safe_result()

    method = chunks[0]["retrieval_method"]
    retrieval_source = "pageindex" if method == "pageindex" else "hybrid"
    result = {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source,
    }
    validate_generation_result(result)
    return result


if __name__ == "__main__":
    print(generate_with_citation("Quy định về điều kiện tốt nghiệp là gì?"))
