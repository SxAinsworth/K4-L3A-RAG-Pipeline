"""
Task 4 — Chunking, embedding và indexing.

Hướng dẫn:
    1. Đọc toàn bộ Markdown trong data/standardized/.
    2. Chia văn bản bằng strategy đã chọn.
    3. Embed chunks bằng một provider duy nhất.
    4. Upsert vào ChromaDB với cosine distance.

Mỗi document/chunk phải theo docs/MODULE_CONTRACTS.md. ID cần ổn định để
chạy lại pipeline không tạo dữ liệu trùng. Task 5 phải dùng chung embed_texts().
"""

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_document


STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "keepitreal/vietnamese-sbert"
EMBEDDING_DIM = 768

COLLECTION_NAME = "rag_documents"

load_dotenv()


@lru_cache(maxsize=4)
def _get_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text bằng provider/model dùng chung cho indexing và query."""
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding input must contain non-empty strings")

    provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL).strip()
    if provider == "sentence_transformers":
        model = _get_sentence_transformer(model_name)
        vectors = model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 32,
        )
        return vectors.tolist()
    if provider == "openai":
        from openai import OpenAI

        response = OpenAI().embeddings.create(model=model_name, input=texts)
        return [item.embedding for item in response.data]
    if provider == "gemini":
        from google import genai

        response = genai.Client().models.embed_content(
            model=model_name,
            contents=texts,
        )
        return [embedding.values for embedding in response.embeddings]
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document."""
    documents = []
    for doc_type in ("legal", "news"):
        directory = STANDARDIZED_DIR / doc_type
        for path in sorted(directory.glob("*.md")):
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise ValueError(f"Standardized document is empty: {path}")

            title = path.stem
            url = None
            if doc_type == "news":
                title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                source_match = re.search(
                    r"^\*\*Source:\*\*\s*(\S+)\s*$",
                    content,
                    re.MULTILINE,
                )
                if title_match:
                    title = title_match.group(1).strip()
                if source_match:
                    url = source_match.group(1).strip()

            document = {
                "id": path.relative_to(STANDARDIZED_DIR).as_posix(),
                "content": content,
                "metadata": {
                    "source": path.name,
                    "title": title,
                    "doc_type": doc_type,
                    "url": url,
                },
            }
            validate_document(document)
            documents.append(document)
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for document in documents:
        validate_document(document)
        for index, text in enumerate(splitter.split_text(document["content"])):
            content = text.strip()
            if not content:
                continue
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": content,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk."""
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding provider returned an unexpected vector count")

    embedded_chunks = []
    for chunk, vector in zip(chunks, vectors):
        if not vector:
            raise ValueError(f"Empty embedding for chunk: {chunk['id']}")
        embedded_chunks.append({**chunk, "embedding": vector})
    return embedded_chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    collection = get_collection()
    ids = [chunk["id"] for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Chunk IDs must be unique before indexing")

    current_ids = set(collection.get(include=[])["ids"])
    stale_ids = sorted(current_ids - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)
    if not chunks:
        return

    metadatas = []
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
        vector = chunk.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError(f"Chunk has no embedding: {chunk['id']}")
        metadata = dict(chunk["metadata"])
        metadata["url"] = metadata["url"] or ""
        metadatas.append(metadata)

    collection.upsert(
        ids=ids,
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=metadatas,
    )


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
