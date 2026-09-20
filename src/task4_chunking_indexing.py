"""Task 4 - load, chunk, embed, and index the standardized corpus."""

import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .contracts import validate_document


ROOT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = ROOT_DIR / "data" / "standardized"
CHROMA_DIR = ROOT_DIR / "chroma_db"

# The regulations contain many short numbered clauses. A 500-character window
# usually keeps one or two clauses together, while 50 characters of overlap
# protects evidence that crosses a clause boundary without excessive duplication.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

load_dotenv(ROOT_DIR / ".env")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
EMBEDDING_PROVIDER = os.getenv(
    "EMBEDDING_PROVIDER", "local_lsa"
).strip().lower()
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "local/tfidf-lsa-v1"
).strip()
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

COLLECTION_NAME = "rag_documents"
UPSERT_BATCH_SIZE = 256
LSA_MODEL_PATH = CHROMA_DIR / "lsa_embedding.joblib"

_NEWS_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_NEWS_URL = re.compile(r"^-\s+\*\*URL:\*\*\s*(\S+)\s*$", re.MULTILINE)
_LSA_FIT_REQUESTED = False


@lru_cache(maxsize=1)
def _sentence_transformer():
    if EMBEDDING_PROVIDER != "sentence_transformers":
        raise ValueError(
            "This pipeline is configured for the local sentence_transformers "
            f"provider, not {EMBEDDING_PROVIDER!r}."
        )

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    actual_dimension = model.get_sentence_embedding_dimension()
    if actual_dimension != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: configured {EMBEDDING_DIM}, "
            f"but {EMBEDDING_MODEL} returns {actual_dimension}"
        )
    return model


@lru_cache(maxsize=1)
def _onnx_embedding_function():
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])


def _text_fingerprint(texts: list[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _lsa_embeddings(texts: list[str]) -> list[list[float]]:
    """Fit/transform a persisted TF-IDF + LSA embedding space."""
    import joblib
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    corpus_sized_call = _LSA_FIT_REQUESTED or len(texts) > EMBEDDING_DIM
    fingerprint = _text_fingerprint(texts) if corpus_sized_call else None
    bundle = joblib.load(LSA_MODEL_PATH) if LSA_MODEL_PATH.is_file() else None
    needs_fit = corpus_sized_call and (
        bundle is None or bundle.get("corpus_fingerprint") != fingerprint
    )

    if needs_fit:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.98,
            max_features=50_000,
            sublinear_tf=True,
            norm="l2",
        )
        matrix = vectorizer.fit_transform(texts)
        max_components = min(matrix.shape[0] - 1, matrix.shape[1] - 1)
        if max_components < EMBEDDING_DIM:
            raise ValueError(
                f"Corpus supports only {max_components} LSA dimensions, "
                f"but {EMBEDDING_DIM} were configured"
            )
        reducer = TruncatedSVD(
            n_components=EMBEDDING_DIM,
            n_iter=7,
            random_state=42,
        )
        vectors = normalize(reducer.fit_transform(matrix), norm="l2")
        bundle = {
            "vectorizer": vectorizer,
            "reducer": reducer,
            "corpus_fingerprint": fingerprint,
            "dimension": EMBEDDING_DIM,
        }
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = LSA_MODEL_PATH.with_suffix(".joblib.tmp")
        joblib.dump(bundle, temporary)
        temporary.replace(LSA_MODEL_PATH)
        return np.asarray(vectors, dtype="float32").tolist()

    if bundle is None:
        raise RuntimeError(
            "Local LSA embedding model is not fitted. Run "
            "`python -m src.task4_chunking_indexing` before querying."
        )
    if int(bundle.get("dimension", -1)) != EMBEDDING_DIM:
        raise RuntimeError("Persisted LSA model has an incompatible dimension")
    matrix = bundle["vectorizer"].transform(texts)
    vectors = normalize(bundle["reducer"].transform(matrix), norm="l2")
    return np.asarray(vectors, dtype="float32").tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the one shared, normalized local embedding model."""
    if not isinstance(texts, list):
        raise TypeError("texts must be a list of strings")
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("every embedding input must be a non-empty string")

    if EMBEDDING_PROVIDER == "local_lsa":
        output = _lsa_embeddings(texts)
    elif EMBEDDING_PROVIDER == "chroma_onnx":
        import numpy as np

        batches = []
        for start in range(0, len(texts), max(1, EMBEDDING_BATCH_SIZE)):
            batch = texts[start : start + max(1, EMBEDDING_BATCH_SIZE)]
            batches.extend(_onnx_embedding_function()(batch))
        vectors = np.asarray(batches, dtype="float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-12)
        output = vectors.tolist()
    elif EMBEDDING_PROVIDER == "sentence_transformers":
        vectors = _sentence_transformer().encode(
            texts,
            batch_size=max(1, EMBEDDING_BATCH_SIZE),
            show_progress_bar=len(texts) >= 32,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        output = vectors.astype("float32", copy=False).tolist()
    else:
        raise ValueError(f"Unsupported embedding provider: {EMBEDDING_PROVIDER!r}")
    if len(output) != len(texts) or any(
        len(vector) != EMBEDDING_DIM for vector in output
    ):
        raise RuntimeError("embedding provider returned an unexpected shape")
    return output


@lru_cache(maxsize=1)
def get_collection():
    """Open the persistent Chroma collection configured for cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIM,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        },
    )
    metadata = collection.metadata or {}
    if metadata.get("embedding_model") != EMBEDDING_MODEL or int(
        metadata.get("embedding_dimension", -1)
    ) != EMBEDDING_DIM:
        raise RuntimeError(
            "Existing Chroma collection uses a different embedding model or "
            "dimension. Remove chroma_db and rebuild the index."
        )
    return collection


def _metadata_from_markdown(path: Path, content: str) -> dict:
    relative = path.relative_to(STANDARDIZED_DIR)
    doc_type = relative.parts[0].lower()
    if doc_type not in {"legal", "news"}:
        raise ValueError(f"Unsupported standardized document type: {relative}")

    title = path.stem.replace("-", " ").replace("_", " ").strip()
    url = None
    if doc_type == "news":
        title_match = _NEWS_TITLE.search(content)
        url_match = _NEWS_URL.search(content)
        if title_match:
            title = title_match.group(1).strip()
        if url_match:
            url = url_match.group(1).strip()
    return {
        "source": relative.as_posix(),
        "title": title,
        "doc_type": doc_type,
        "url": url,
    }


def load_documents() -> list[dict]:
    """Read every standardized Markdown file into the Document contract."""
    if not STANDARDIZED_DIR.is_dir():
        raise FileNotFoundError(f"Missing standardized directory: {STANDARDIZED_DIR}")

    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Standardized document is empty: {path}")
        relative = path.relative_to(STANDARDIZED_DIR).as_posix()
        document = {
            "id": relative,
            "content": content,
            "metadata": _metadata_from_markdown(path, content),
        }
        validate_document(document)
        documents.append(document)

    if not documents:
        raise ValueError(f"No Markdown documents found in {STANDARDIZED_DIR}")
    ids = [document["id"] for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Document IDs must be unique")
    return documents


def _split_text(text: str) -> list[str]:
    """Split at the best nearby structural boundary with sliding overlap."""
    if len(text) <= CHUNK_SIZE:
        return [text.strip()] if text.strip() else []

    boundaries = ("\n## ", "\n### ", "\n\n", "\n", ". ", "; ", ", ", " ")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(start + CHUNK_SIZE, len(text))
        end = hard_end
        if hard_end < len(text):
            # Do not create tiny chunks merely because a heading occurs near
            # the beginning of the current window.
            boundary_floor = start + int(CHUNK_SIZE * 0.55)
            for separator in boundaries:
                position = text.rfind(separator, boundary_floor, hard_end)
                if position >= 0:
                    end = position + len(separator)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break

        next_start = max(start + 1, end - CHUNK_OVERLAP)
        # Prefer beginning the overlap at a word boundary when one is close.
        whitespace = text.find(" ", next_start, min(end, next_start + 20))
        if whitespace >= 0:
            next_start = whitespace + 1
        start = next_start
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split Documents recursively while preserving stable identity and metadata."""
    chunks: list[dict] = []
    document_ids: set[str] = set()
    for document in documents:
        validate_document(document)
        if document["id"] in document_ids:
            raise ValueError(f"Duplicate document ID: {document['id']}")
        document_ids.add(document["id"])

        texts = _split_text(document["content"])
        for index, text in enumerate(texts):
            chunk = {
                "id": f"{document['id']}::chunk-{index:04d}",
                "content": text,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            chunks.append(chunk)

    chunk_ids = [chunk["id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Chunk IDs must be unique")
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Return EmbeddedChunks without mutating the input chunk dictionaries."""
    global _LSA_FIT_REQUESTED
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    _LSA_FIT_REQUESTED = EMBEDDING_PROVIDER == "local_lsa"
    try:
        vectors = embed_texts([chunk["content"] for chunk in chunks])
    finally:
        _LSA_FIT_REQUESTED = False
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count does not match chunk count")
    return [
        {
            **chunk,
            "metadata": dict(chunk["metadata"]),
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors)
    ]


def _chroma_metadata(metadata: dict) -> dict:
    # Chroma metadata values cannot be None. Task 5 converts this sentinel back.
    return {**metadata, "url": metadata.get("url") or ""}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert EmbeddedChunks and remove stale IDs from previous corpus versions."""
    collection = get_collection()
    expected_ids: set[str] = set()

    for start in range(0, len(chunks), UPSERT_BATCH_SIZE):
        batch = chunks[start : start + UPSERT_BATCH_SIZE]
        for chunk in batch:
            validate_document(chunk, require_chunk=True)
            vector = chunk.get("embedding")
            if not isinstance(vector, list) or len(vector) != EMBEDDING_DIM:
                raise ValueError(f"Invalid embedding for chunk {chunk['id']}")
        ids = [chunk["id"] for chunk in batch]
        expected_ids.update(ids)
        collection.upsert(
            ids=ids,
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in batch],
        )

    existing_ids = set(collection.get(include=[])["ids"])
    stale_ids = sorted(existing_ids - expected_ids)
    for start in range(0, len(stale_ids), UPSERT_BATCH_SIZE):
        collection.delete(ids=stale_ids[start : start + UPSERT_BATCH_SIZE])

    if collection.count() != len(expected_ids):
        raise RuntimeError(
            f"Chroma count mismatch: expected {len(expected_ids)}, "
            f"found {collection.count()}"
        )


def run_pipeline() -> None:
    """Run load -> chunk -> embed -> persistent cosine index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(
        f"Indexed {len(embedded_chunks)} chunks from {len(documents)} documents "
        f"using {EMBEDDING_MODEL} ({EMBEDDING_DIM} dimensions)"
    )


if __name__ == "__main__":
    run_pipeline()
