# Individual contribution report

## Thông tin

- Họ và tên: Lê Thị Hoài Thương
- Mã học viên: 2A202602898
- Nhóm: Chưa được cung cấp
- Repository/branch: https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline/tree/thuong

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Chuẩn hoá dữ liệu | Cài đặt chuyển PDF/DOCX và JSON bài viết thành Markdown; kiểm tra metadata bắt buộc, không ghi file rỗng. | `src/task3_convert_markdown.py` (working tree trên branch `thuong`) | Done |
| Chunking, embedding và index | Cài đặt đọc Markdown, giữ metadata/ID ổn định, recursive chunking, embedding dispatch và Chroma cosine upsert. | `src/task4_chunking_indexing.py` | Done |
| Hybrid retrieval | Cài đặt dense search, BM25 dùng chung corpus chunks, RRF theo rank và retrieval pipeline chỉ fuse một lần. | `src/task5_semantic_search.py`, `src/task6_lexical_search.py`, `src/task7_reranking.py`, `src/task9_retrieval_pipeline.py` | Done |
| Fallback và generation | Cài đặt fallback an toàn khi PageIndex chưa cấu hình; generation đa provider, citation context và safe refusal khi không đủ evidence/provider lỗi. | `src/task8_pageindex_vectorless.py`, `src/task10_generation.py` | Done |
| Chatbot UI | Tích hợp Streamlit với `generate_with_citation`, lịch sử chat, nguồn, phương thức retrieval và score. | `app.py` | Done |
| Corpus UEH và evaluation | Đã xác định chủ đề PDF quy định và bài hỗ trợ sinh viên UEH; chưa có 3 PDF, 5 URL bài viết hoặc API/evaluation run để tạo corpus và A/B thực tế. | `data/`, `group_project/evaluation/` | Blocked |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Dùng một schema `SearchResult` thống nhất cho dense, BM25, hybrid và PageIndex; RRF chỉ gộp thứ hạng một lần.
   **Lý do/evidence:** `src/contracts.py` quy định schema; `src/task5_semantic_search.py`, `src/task6_lexical_search.py` và `src/task7_reranking.py` trả cùng các trường `id`, `content`, `score`, `metadata`, `retrieval_method`. `tests/test_contracts.py` kiểm tra uniqueness, sort giảm dần và công thức RRF.
   **Trade-off:** RRF score không còn diễn giải như cosine/BM25 score; vì vậy pipeline phải giữ riêng dense cosine score cho quyết định fallback.

2. **Quyết định:** Khi không có evidence hoặc dịch vụ ngoài/LLM lỗi, chatbot trả safe refusal thay vì tạo câu trả lời không kiểm chứng.
   **Lý do/evidence:** `src/task9_retrieval_pipeline.py` bắt lỗi fallback; `src/task10_generation.py` trả câu từ chối chuẩn nếu retrieval rỗng hoặc provider lỗi. Đây là invariant trong `docs/MODULE_CONTRACTS.md`.
   **Trade-off:** Một số câu hỏi có thể bị từ chối dù người dùng kỳ vọng câu trả lời; cần bổ sung corpus UEH và hiệu chỉnh threshold để giảm false refusal.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: `python -m pytest tests/test_contracts.py -q`; `python -m compileall -q src app.py`; query safe-refusal ngoài corpus.
- Kết quả trước/sau nếu có: Contract test hiện **15/15 passed** (`pytest tests/test_contracts.py -q`, 20/09/2026). Test BM25 trên corpus hai đoạn từng thất bại vì mọi IDF có thể bằng 0; đã thêm fallback lexical score theo số token giao nhau chỉ cho edge case này trong `src/task6_lexical_search.py`. `compileall` đã pass sau khi hoàn thiện các module.
- Lỗi đã phát hiện và cách xử lý: Khi Chroma chưa có dữ liệu, `semantic_search()` từng có thể tải embedding model `BAAI/bge-m3` (~2.27 GB) không cần thiết và gây lỗi thiếu bộ nhớ. Đã kiểm tra collection rỗng trước khi embed trong `src/task5_semantic_search.py`; guard `hasattr` giữ tương thích fake collection của contract test.

## Điều còn hạn chế

- Việc cần hoàn thành trước khi nộp: (1) lưu ít nhất 3 PDF/DOCX quy định UEH vào `data/landing/legal/`; (2) cung cấp/crawl ít nhất 5 URL bài hỗ trợ sinh viên UEH thành JSON trong `data/landing/news/`; (3) chạy convert, index và hiệu chỉnh `SCORE_THRESHOLD`; (4) tạo ít nhất 15 câu golden grounded; (5) chạy dense-only và hybrid+RRF, rồi ghi bốn metric thật vào `group_project/evaluation/RESULT.md`.
- Cách xử lý giới hạn tài nguyên: Nếu máy không tải được `BAAI/bge-m3`, đổi `EMBEDDING_MODEL` trong `.env` sang `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, chạy lại index từ đầu và ghi model thực dùng trong báo cáo evaluation. Chỉ so sánh A/B trên cùng một embedding model.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/09/2026
- Tên thành viên: Lê Thị Hoài Thương
