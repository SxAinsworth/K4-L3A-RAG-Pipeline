import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(
    page_title="UEH Student Support RAG",
    page_icon="🎓",
    layout="wide",
)


def render_sources(sources: list[dict], retrieval_source: str) -> None:
    """Hiển thị đúng các SearchResult đã được đưa vào context."""
    if not sources:
        return
    st.caption(f"Retrieval source: {retrieval_source}")
    with st.expander(f"Nguồn đã sử dụng ({len(sources)})"):
        for index, source in enumerate(sources, 1):
            metadata = source["metadata"]
            st.markdown(f"**[S{index}] {metadata['title']}**")
            url = metadata.get("url")
            if url:
                st.markdown(f"[{metadata['source']}]({url})")
            else:
                st.code(metadata["source"], language=None)
            st.caption(
                f"Method: {source['retrieval_method']} · "
                f"Score: {source['score']:.6f} · ID: {source['id']}"
            )
            st.text(source["content"])

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("UEH Student Support")
    st.caption("Tra cứu học bổng, học phí, học phần và quy định sinh viên UEH")
    top_k = st.slider("Số chunks", 3, 10, 5)

st.title("UEH Student Support RAG")
st.caption("Câu trả lời chỉ sử dụng tài liệu đã thu thập và hiển thị nguồn kiểm chứng.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(
                message.get("sources", []),
                message.get("retrieval_source", "none"),
            )

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang truy xuất và kiểm chứng nguồn..."):
            result = generate_with_citation(query, top_k)
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
