"""
Task 10 — Generation có citation.

Hướng dẫn:
    1. Retrieve top-k chunks.
    2. Reorder để giảm lost-in-the-middle.
    3. Format context kèm title và source.
    4. Gọi provider được chọn trong .env.
    5. Trả answer, sources và retrieval_source.

Nếu context không đủ hoặc provider lỗi, trả safe refusal; không bịa thông tin.
"""

import os
import re
from copy import deepcopy

from dotenv import load_dotenv

from .contracts import validate_generation_result, validate_search_results
from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "")

SYSTEM_PROMPT = """Trả lời chỉ từ context được cung cấp.
Mỗi khẳng định phải có citation dạng [S1], [S2] tương ứng với nhãn trong
context. Không được tự tạo nguồn hoặc dùng kiến thức bên ngoài. Nếu context
không đủ evidence, hãy trả lời đúng câu: 'Tôi không thể xác minh thông tin này
từ nguồn hiện có.'"""

SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."


def _safe_result() -> dict:
    result = {
        "answer": SAFE_REFUSAL,
        "sources": [],
        "retrieval_source": "none",
    }
    validate_generation_result(result)
    return result


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context."""
    copied = deepcopy(chunks)
    if len(copied) <= 2:
        return copied
    front = copied[::2]
    back = copied[1::2]
    return front + back[::-1]


def format_context(chunks: list[dict]) -> str:
    """Tạo context có title và source label."""
    parts = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk["metadata"]
        url = metadata.get("url") or "N/A"
        citation_index = chunk.get("_citation_index", index)
        parts.append(
            f"[S{citation_index}]\n"
            f"Title: {metadata['title']}\n"
            f"Source: {metadata['source']}\n"
            f"URL: {url}\n"
            f"Chunk ID: {chunk['id']}\n"
            f"Content:\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình."""
    provider = LLM_PROVIDER.strip().lower()
    if not LLM_MODEL.strip():
        raise RuntimeError("LLM_MODEL is not configured")

    if provider == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
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
        text = response.choices[0].message.content or ""
    elif provider == "gemini":
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                top_p=TOP_P,
            ),
        )
        text = response.text or ""
    elif provider == "anthropic":
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        response = Anthropic(api_key=api_key).messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

    text = text.strip()
    if not text:
        raise RuntimeError(f"{provider} returned an empty response")
    return text


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Trả về GenerationResult."""
    if top_k <= 0 or not query.strip():
        return _safe_result()
    try:
        chunks = retrieve(query, top_k=top_k)
    except Exception:
        return _safe_result()
    if not chunks:
        return _safe_result()

    method = chunks[0]["retrieval_method"]
    if method not in {"hybrid", "pageindex"} or any(
        chunk["retrieval_method"] != method for chunk in chunks
    ):
        return _safe_result()
    validate_search_results(chunks, top_k=top_k, expected_method=method)

    sources = deepcopy(chunks)
    citation_indexes = {
        source["id"]: index for index, source in enumerate(sources, 1)
    }
    reordered = reorder_for_llm(sources)
    context_chunks = [
        {**chunk, "_citation_index": citation_indexes[chunk["id"]]}
        for chunk in reordered
    ]
    context = format_context(context_chunks)
    user_message = f"Context:\n{context}\n\nQuestion: {query.strip()}"
    try:
        answer = call_llm(SYSTEM_PROMPT, user_message)
    except Exception:
        return _safe_result()

    citations = [int(value) for value in re.findall(r"\[S(\d+)\]", answer)]
    if not citations or any(index < 1 or index > len(sources) for index in citations):
        return _safe_result()

    result = {
        "answer": answer,
        "sources": sources,
        "retrieval_source": method,
    }
    validate_generation_result(result)
    return result


if __name__ == "__main__":
    print(generate_with_citation("Điều kiện nhận học bổng hỗ trợ học tập là gì?"))
