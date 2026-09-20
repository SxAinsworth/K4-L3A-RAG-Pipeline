# Báo cáo đóng góp cá nhân

## Thông tin

- Họ và tên: Đinh Thị Minh Tâm
- Mã học viên: 2A202602433
- Nhóm: فتيات جميلات
- Repository: [SxAinsworth/K4-L3A-RAG-Pipeline](https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline)
- Branch phụ trách: [`minhtam`](https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline/tree/minhtam)
- Commit chính: [`6275777`](https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline/commit/6275777493f2a6c7f04f23f00ec47373496420d0), [`52fb610`](https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline/commit/52fb6101472b81ef31c76a63586886f52c80f438)

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Thu thập và chuẩn hóa dữ liệu | Thu thập 3 PDF pháp lý và crawl 5 bài hỗ trợ sinh viên UEH; hoàn thiện chuyển đổi Markdown và giữ cấu trúc `legal/`, `news/`. | `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py`, `src/task3_convert_markdown.py`, `data/`; commit `6275777` | Done |
| Chunking và vector index | Load document theo contract, recursive chunk 500/50, tạo stable chunk ID, embedding bằng Vietnamese SBERT và upsert 461 chunk vào ChromaDB. | `src/task4_chunking_indexing.py`; commit `6275777` | Done |
| Dense, BM25 và RRF | Hoàn thiện semantic search, BM25 search và Reciprocal Rank Fusion; bảo đảm kết quả không trùng ID, đúng schema và giảm dần theo score. | `src/task5_semantic_search.py`, `src/task6_lexical_search.py`, `src/task7_reranking.py`; commit `6275777` | Done |
| Retrieval pipeline | Kết hợp dense và BM25, fuse một lần, dùng best dense score cho threshold và giữ hybrid result khi PageIndex fallback lỗi. | `src/task9_retrieval_pipeline.py`; commit `6275777` | Done |
| Generation và giao diện | Hoàn thiện reorder, context có title/source, gọi Gemini, citation mapping, safe refusal; tích hợp Streamlit và hiển thị nguồn, method, score, lịch sử chat. | `src/task10_generation.py`, `app.py`; commit `6275777` | Done |
| Evaluation và báo cáo | Tạo 15 golden cases từ corpus, viết runner có cache/retry, chạy dense-only so với hybrid+RRF, lưu 30 kết quả thô và phân tích ba failure case. | `group_project/evaluation/`; commits `6275777`, `52fb610` | Done |

## Quyết định kỹ thuật quan trọng

1. **Dùng `keepitreal/vietnamese-sbert` và một hàm `embed_texts()` chung cho corpus lẫn query.**

   **Lý do/evidence:** Model phù hợp dữ liệu tiếng Việt, tạo vector 768 chiều ổn định; cùng một hàm giúp Task 4 và Task 5 không lệch model hoặc dimension. Re-index hai lần vẫn giữ 461 record nhờ stable ID và upsert.

   **Trade-off:** Lần tìm kiếm đầu phải tải model cục bộ nên có cold-start khoảng 15,40 giây; các lượt warm dense retrieval trung bình còn khoảng 0,083 giây.

2. **So sánh dense-only và hybrid+RRF với mọi biến còn lại giữ nguyên.**

   **Lý do/evidence:** Cùng 15 golden cases, final `top_k=5`, generator, evaluator và prompt. Hybrid tăng điểm trung bình từ 0,787 lên 0,833; context recall tăng 0,093 và context precision tăng 0,067.

   **Trade-off:** Hybrid retrieval warm chậm hơn khoảng 49% do thêm BM25/RRF và faithfulness giảm 0,047 vì một số chunk nhiễu; vì vậy không thể kết luận hybrid tốt hơn ở mọi case.

## Kiểm thử và kết quả

- Test đã chạy: `pytest tests/test_acceptance.py -q` đạt **5/5** và `pytest tests/test_contracts.py -q` đạt **15/15**.
- Dữ liệu sau chuẩn hóa: **8 document**, gồm 3 legal và 5 news; vector store có **461 chunk** (183 legal, 278 news).
- Query hiệu chỉnh threshold: câu in-domain “Điều kiện nhận học bổng hỗ trợ học tập UEH là gì?” đạt best dense score **0,684271**; câu ngoài domain “Nhiệt độ bề mặt của sao Betelgeuse là bao nhiêu?” đạt **0,278075**. Từ đó chọn threshold tạm thời **0,45**.
- Lỗi đã phát hiện: `GenerationResult.sources` từng bị reorder làm score không còn giảm dần, gây `ValueError`. Tôi giữ `sources` theo thứ tự score, chỉ reorder bản sao dùng làm context và thêm `_citation_index` để citation vẫn ánh xạ đúng nguồn.
- Evaluation A/B: hybrid+RRF tăng relevance **+0,073**, recall **+0,093**, precision **+0,067**, nhưng faithfulness giảm **−0,047**. Raw answer, source ID, latency và rationale được lưu tại `group_project/evaluation/evaluation_results.json`.

## Điều còn hạn chế

- BM25 hiện tokenize bằng biểu thức chính quy, chưa tách từ tiếng Việt; các danh sách điều kiện dài đôi khi bị chia qua ranh giới chunk. Điều này làm case về 15 tín chỉ và điều kiện học bổng toàn phần/bán phần thiếu evidence trong final top-5.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thử là chunk theo heading/list với kích thước 650–750, overlap 75 và thêm Vietnamese word segmentation cho BM25. Tôi sẽ chạy lại đúng 15 golden cases và chỉ giữ thay đổi nếu recall tăng mà precision không giảm đáng kể.
- PageIndex chưa được đánh giá end-to-end vì repository chưa cấu hình `PAGEINDEX_API_KEY`; pipeline hiện xử lý lỗi provider và giữ kết quả hybrid thay vì làm ứng dụng dừng.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/09/2026
- Tên thành viên: Đinh Thị Minh Tâm
