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

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_document


load_dotenv()


STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").strip().lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip() or "BAAI/bge-m3"
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

COLLECTION_NAME = "rag_documents"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the single provider configured in ``.env``."""
    if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
        raise TypeError("texts must be a list of strings")
    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("texts must not contain blank values")

    if EMBEDDING_PROVIDER == "sentence_transformers":
        vectors = _sentence_transformer_model().encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
    elif EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI

        response = OpenAI().embeddings.create(model=EMBEDDING_MODEL, input=texts)
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    elif EMBEDDING_PROVIDER == "gemini":
        from google import genai

        client = genai.Client()
        vectors = []
        for text in texts:
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
            if not response.embeddings or len(response.embeddings) != 1:
                raise ValueError("Gemini must return exactly one embedding per input text")
            vectors.append(response.embeddings[0].values)
    else:
        raise ValueError(
            "Unsupported EMBEDDING_PROVIDER. Use sentence_transformers, openai, or gemini."
        )

    normalized_vectors = [[float(value) for value in vector] for vector in vectors]
    _validate_embeddings(normalized_vectors, expected_count=len(texts))
    return normalized_vectors


@lru_cache(maxsize=1)
def _sentence_transformer_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def _validate_embeddings(vectors: list[list[float]], *, expected_count: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError(f"Expected {expected_count} embeddings, received {len(vectors)}")
    for index, vector in enumerate(vectors):
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Embedding {index} has dimension {len(vector)}; expected {EMBEDDING_DIM}"
            )


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "embedding_provider": EMBEDDING_PROVIDER,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIM,
        },
    )
    metadata = collection.metadata or {}
    configured = (
        metadata.get("hnsw:space"),
        metadata.get("embedding_provider"),
        metadata.get("embedding_model"),
        metadata.get("embedding_dimension"),
    )
    expected = ("cosine", EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIM)
    if configured != expected:
        raise ValueError(
            "Existing Chroma collection uses a different embedding configuration: "
            f"{configured!r} != {expected!r}. Remove or migrate the collection first."
        )
    return collection


def _parse_front_matter(text: str, path: Path) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        raise ValueError(f"Missing YAML front matter: {path}")
    try:
        header, content = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ValueError(f"Unterminated YAML front matter: {path}") from error

    metadata: dict[str, object] = {}
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Invalid front-matter line in {path}: {line!r}")
        key, raw_value = line.split(":", 1)
        raw_value = raw_value.strip()
        if raw_value in {"null", "None", "~", ""}:
            value: object = None
        elif raw_value.startswith(('"', "'")):
            try:
                value = json.loads(raw_value) if raw_value.startswith('"') else raw_value[1:-1]
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid quoted value for {key.strip()} in {path}") from error
        else:
            value = raw_value
        metadata[key.strip()] = value
    return metadata, content.strip()


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document."""
    documents: list[dict] = []
    seen_ids: set[str] = set()
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        front_matter, content = _parse_front_matter(path.read_text(encoding="utf-8"), path)
        document_id = str(front_matter.get("id") or path.relative_to(STANDARDIZED_DIR).with_suffix(""))
        doc_type = str(front_matter.get("doc_type") or path.parent.name)
        document = {
            "id": document_id,
            "content": content,
            "metadata": {
                "source": str(front_matter.get("source") or path.name),
                "title": str(front_matter.get("title") or path.stem),
                "doc_type": doc_type,
                "url": front_matter.get("url"),
            },
        }
        if document_id in seen_ids:
            raise ValueError(f"Duplicate document id: {document_id}")
        if doc_type not in {"legal", "news"}:
            raise ValueError(f"Invalid doc_type for {path}: {doc_type!r}")
        validate_document(document)
        seen_ids.add(document_id)
        documents.append(document)
    if not documents:
        raise ValueError(f"No Markdown documents found under {STANDARDIZED_DIR}")
    return documents


def _fallback_recursive_chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Simple recursive fallback when langchain_text_splitters is not installed."""
    stripped = text.strip()
    if not stripped:
        return []
    if len(stripped) <= chunk_size:
        return [stripped]

    chunks: list[str] = []
    start = 0
    while start < len(stripped):
        end = min(start + chunk_size, len(stripped))
        chunk = stripped[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(stripped):
            break
        if chunk_overlap > 0:
            start = max(end - chunk_overlap, start + 1)
        else:
            start = end
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    if CHUNK_SIZE <= 0 or CHUNK_OVERLAP < 0 or CHUNK_OVERLAP >= CHUNK_SIZE:
        raise ValueError("Chunk settings require 0 <= CHUNK_OVERLAP < CHUNK_SIZE")
    if CHUNKING_METHOD != "recursive":
        raise ValueError(f"Unsupported CHUNKING_METHOD: {CHUNKING_METHOD}")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        chunk_source = lambda text: splitter.split_text(text)
    except ModuleNotFoundError:
        chunk_source = lambda text: _fallback_recursive_chunk_text(
            text,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

    chunks: list[dict] = []
    seen_ids: set[str] = set()
    for document in documents:
        validate_document(document)
        for index, text in enumerate(chunk_source(document["content"])):
            chunk_id = f"{document['id']}::chunk-{index}"
            chunk = {
                "id": chunk_id,
                "content": text.strip(),
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk id: {chunk_id}")
            validate_document(chunk, require_chunk=True)
            seen_ids.add(chunk_id)
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk."""
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    collection = get_collection()
    ids: list[str] = []
    metadatas: list[dict] = []
    embeddings: list[list[float]] = []
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
        vector = chunk.get("embedding")
        if not isinstance(vector, list):
            raise ValueError(f"Chunk has no embedding: {chunk['id']}")
        _validate_embeddings([vector], expected_count=1)
        ids.append(chunk["id"])
        embeddings.append(vector)
        metadatas.append(
            {
                **chunk["metadata"],
                "url": chunk["metadata"].get("url") or "",
            }
        )

    if len(ids) != len(set(ids)):
        raise ValueError("Chunk IDs must be unique before indexing")
    if ids:
        collection.upsert(
            ids=ids,
            documents=[chunk["content"] for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
        )

    existing_ids = set(collection.get()["ids"])
    stale_ids = sorted(existing_ids - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
