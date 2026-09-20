import json

from src.contracts import validate_search_results


def _document() -> dict:
    return {
        "id": "legal/policy.md",
        "content": "# Quy chế đào tạo\n\nĐiều kiện công nhận tốt nghiệp.",
        "metadata": {
            "source": "legal/policy.md",
            "title": "Quy chế đào tạo",
            "doc_type": "legal",
            "url": None,
        },
    }


def test_upload_documents_uses_fingerprint_cache(monkeypatch, tmp_path):
    import src.task8_pageindex_vectorless as pageindex

    cache_path = tmp_path / "pageindex_doc_ids.json"
    upload_pdf = tmp_path / "policy.pdf"
    upload_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    calls = []

    class FakeClient:
        def submit_document(self, file_path):
            calls.append(file_path)
            return {"doc_id": "doc-123"}

    monkeypatch.setattr(pageindex, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pageindex, "load_documents", lambda: [_document()])
    monkeypatch.setattr(pageindex, "_configured_api_key", lambda: "test-key")
    monkeypatch.setattr(pageindex, "_make_client", lambda api_key: FakeClient())
    monkeypatch.setattr(pageindex, "_prepare_upload_pdf", lambda document: upload_pdf)

    pageindex.upload_documents()
    pageindex.upload_documents()

    assert calls == [str(upload_pdf)]
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["documents"]["legal/policy.md"]["doc_id"] == "doc-123"


def test_pageindex_search_parses_nested_contents(monkeypatch, tmp_path):
    import src.task8_pageindex_vectorless as pageindex

    cache_path = tmp_path / "pageindex_doc_ids.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "documents": {
                    "legal/policy.md": {
                        "doc_id": "doc-123",
                        "source": "legal/policy.md",
                        "title": "Quy chế đào tạo",
                        "doc_type": "legal",
                        "url": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def submit_query(self, doc_id, query):
            assert doc_id == "doc-123"
            assert query == "điều kiện tốt nghiệp"
            return {"retrieval_id": "retrieval-1"}

        def get_retrieval(self, retrieval_id):
            assert retrieval_id == "retrieval-1"
            return {
                "status": "completed",
                "retrieved_nodes": [
                    {
                        "node_id": "node-a",
                        "title": "Công nhận tốt nghiệp",
                        "relevant_contents": [
                            {
                                "page_index": 12,
                                "relevant_content": "Sinh viên phải tích lũy đủ tín chỉ.",
                            },
                            {
                                "page_index": 13,
                                "relevant_content": "Sinh viên hoàn thành nghĩa vụ học phí.",
                            },
                        ],
                    }
                ],
            }

    monkeypatch.setattr(pageindex, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pageindex, "_configured_api_key", lambda: "test-key")
    monkeypatch.setattr(pageindex, "_metadata_catalog", lambda: {})
    monkeypatch.setattr(pageindex, "_make_client", lambda api_key: FakeClient())

    results = pageindex.pageindex_search("điều kiện tốt nghiệp", top_k=2)

    validate_search_results(results, top_k=2, expected_method="pageindex")
    assert [item["score"] for item in results] == [1.0, 0.5]
    assert results[0]["metadata"]["page_index"] == 12
    assert results[0]["metadata"]["source"] == "legal/policy.md"


def test_pageindex_search_survives_provider_error(monkeypatch, tmp_path):
    import src.task8_pageindex_vectorless as pageindex

    cache_path = tmp_path / "pageindex_doc_ids.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "documents": {
                    "legal/policy.md": {
                        "doc_id": "doc-123",
                        "source": "legal/policy.md",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class UnavailableClient:
        def submit_query(self, doc_id, query):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(pageindex, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pageindex, "_configured_api_key", lambda: "test-key")
    monkeypatch.setattr(pageindex, "_metadata_catalog", lambda: {})
    monkeypatch.setattr(
        pageindex, "_make_client", lambda api_key: UnavailableClient()
    )

    assert pageindex.pageindex_search("điều kiện tốt nghiệp", top_k=2) == []
