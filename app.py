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
    st.caption("Hỏi đáp từ quy định và thông tin hỗ trợ sinh viên UEH")
    top_k = st.slider("Số chunks", 3, 10, 5)

st.title("UEH Student Support RAG Chatbot")
st.caption("Câu trả lời chỉ dựa trên tài liệu chính sách và bài hỗ trợ sinh viên UEH đã lập chỉ mục.")


def show_sources(sources: list[dict], retrieval_source: str) -> None:
    if not sources:
        return
    st.caption(f"Retrieval method: {retrieval_source}")
    with st.expander(f"Nguồn đã dùng ({len(sources)})"):
        for index, source in enumerate(sources, 1):
            metadata = source["metadata"]
            st.markdown(f"**[{index}] {metadata['title']}** — `{source['retrieval_method']}`, score `{source['score']:.4f}`")
            if metadata.get("url"):
                st.markdown(f"{metadata['url']}")
            st.caption(f"{metadata['source']} · chunk {metadata['chunk_index']}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        show_sources(message.get("sources", []), message.get("retrieval_source", "none"))

query = st.chat_input("Nhập câu hỏi...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm tài liệu UEH..."):
            result = generate_with_citation(query, top_k=top_k)
        st.markdown(result["answer"])
        show_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append({"role": "assistant", "content": result["answer"], "sources": result["sources"], "retrieval_source": result["retrieval_source"]})
