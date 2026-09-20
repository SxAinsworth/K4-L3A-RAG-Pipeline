"""Streamlit UI for the university-regulation RAG pipeline."""

from __future__ import annotations

from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import SAFE_REFUSAL, generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="Trợ lý quy chế đào tạo",
    page_icon="🎓",
    layout="wide",
)


def render_sources(sources: list[dict[str, Any]], retrieval_source: str) -> None:
    """Render only the SearchResults that were supplied to generation."""
    st.caption(f"Đường truy xuất: `{retrieval_source}`")
    if not sources:
        st.info("Không có nguồn đủ phù hợp để trích dẫn.")
        return

    with st.expander(f"Nguồn đã dùng ({len(sources)})", expanded=True):
        for index, source in enumerate(sources, start=1):
            metadata = source["metadata"]
            title = metadata["title"]
            source_name = metadata["source"]
            method = source["retrieval_method"]
            score = float(source["score"])

            st.markdown(f"**[Document {index}] {title}**")
            st.caption(
                f"Source: {source_name} · Method: {method} · Score: {score:.6f}"
            )
            if metadata.get("url"):
                st.markdown(f"[Mở nguồn gốc]({metadata['url']})")
            st.text(source["content"])
            if index < len(sources):
                st.divider()


def render_message(message: dict[str, Any]) -> None:
    """Render a stored message, including all evidence needed for replay."""
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(
                message.get("sources", []),
                message.get("retrieval_source", "none"),
            )


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("🎓 RAG Chatbot")
    st.caption("Hỏi đáp dựa trên các quy chế đào tạo đại học đã thu thập.")
    top_k = st.slider("Số chunks truy xuất", min_value=3, max_value=10, value=5)
    if st.button("Xóa lịch sử", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("Trợ lý quy chế đào tạo đại học")
st.caption(
    "Câu trả lời chỉ sử dụng corpus của dự án. Mở mục nguồn để kiểm tra từng "
    "citation, retrieval method và score."
)

for stored_message in st.session_state.messages:
    render_message(stored_message)

query = st.chat_input("Nhập câu hỏi về quy chế đào tạo...")

if query:
    user_message = {"role": "user", "content": query}
    st.session_state.messages.append(user_message)
    render_message(user_message)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm và kiểm tra bằng chứng..."):
            try:
                result = generate_with_citation(query, top_k=top_k)
            except Exception:
                # Keep the UI stable even for an unexpected integration error.
                result = {
                    "answer": SAFE_REFUSAL,
                    "sources": [],
                    "retrieval_source": "none",
                }
        st.markdown(result["answer"])
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "retrieval_source": result["retrieval_source"],
        }
    )
