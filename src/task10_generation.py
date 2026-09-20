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

from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "")

SYSTEM_PROMPT = """Trả lời chỉ từ context được cung cấp.
Mỗi khẳng định phải có citation. Nếu thiếu evidence, hãy từ chối xác minh."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context."""
    if len(chunks) <= 2:
        return list(chunks)
    front = list(chunks[::2])
    back = list(chunks[1::2])
    return front + back[::-1]


def format_context(chunks: list[dict]) -> str:
    """Tạo context có title và source label."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata") or {}
        title = metadata.get("title") or "Unknown title"
        source = metadata.get("source") or "unknown source"
        parts.append(
            f"[Document {index} | Title: {title} | Source: {source}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình."""
    provider = str(LLM_PROVIDER).lower()
    model_name = LLM_MODEL or {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-1.5-flash",
        "anthropic": "claude-3-haiku-20240307",
    }.get(provider, "gpt-4o-mini")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        from openai import OpenAI

        response = OpenAI(api_key=api_key).chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
        )
        return response.choices[0].message.content or ""

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=f"{system_prompt}\n\n{user_message}",
        )
        return getattr(response, "text", "") or ""

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        from anthropic import Anthropic

        response = Anthropic(api_key=api_key).messages.create(
            model=model_name,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
        )
        return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Trả về GenerationResult."""
    try:
        chunks = retrieve(query, top_k=top_k)
        if not chunks:
            return {
                "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
                "sources": [],
                "retrieval_source": "none",
            }
        reordered = reorder_for_llm(chunks)
        context = format_context(reordered)
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
        answer = call_llm(SYSTEM_PROMPT, user_message)
        return {
            "answer": answer or "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": chunks,
            "retrieval_source": chunks[0]["retrieval_method"],
        }
    except Exception:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": [],
            "retrieval_source": "none",
        }


if __name__ == "__main__":
    print(generate_with_citation("test query"))
