import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RAG Chatbot")
    st.caption("Thay mô tả theo đề tài của nhóm")
    top_k = st.slider("Số chunks", 3, 10, 5)

st.title("RAG Chatbot")
st.caption("Hỏi về chính sách, tin tức và câu trả lời có nguồn chứng minh")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources") or []
        retrieval_source = message.get("retrieval_source")
        if sources:
            st.caption(f"Nguồn: {retrieval_source or 'unknown'}")
            for index, source in enumerate(sources, 1):
                metadata = source.get("metadata") or {}
                title = metadata.get("title") or "Unknown title"
                file_source = metadata.get("source") or "unknown source"
                score = source.get("score", 0)
                method = source.get("retrieval_method", "unknown")
                st.markdown(
                    f"{index}. **{title}** — {file_source}  "
                    f"(score: {score:.3f}, method: {method})"
                )

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        result = generate_with_citation(query, top_k=top_k)
        answer = result.get("answer") or "Tôi không thể xác minh thông tin này từ nguồn hiện có."
        sources = result.get("sources") or []
        retrieval_source = result.get("retrieval_source") or "none"
        st.markdown(answer)

        if sources:
            st.caption(f"Nguồn: {retrieval_source}")
            for index, source in enumerate(sources, 1):
                metadata = source.get("metadata") or {}
                title = metadata.get("title") or "Unknown title"
                file_source = metadata.get("source") or "unknown source"
                score = source.get("score", 0)
                method = source.get("retrieval_method", "unknown")
                st.markdown(
                    f"{index}. **{title}** — {file_source}  "
                    f"(score: {score:.3f}, method: {method})"
                )
        else:
            st.caption("Không có nguồn evidence nào được tìm thấy.")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieval_source": retrieval_source,
        }
    )
