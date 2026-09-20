# Báo cáo đóng góp cá nhân

## Thông tin

- **Họ và tên:** [Bổ sung họ và tên]
- **Mã học viên:** [Bổ sung mã học viên]
- **Nhóm:** [Bổ sung số nhóm]
- **Repository/branch:** `https://github.com/SxAinsworth/K4-L3A-RAG-Pipeline` — `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Corpus và chuẩn hóa dữ liệu | Thu thập 3 PDF quy chế và 5 trang công khai; hoàn thiện crawler, metadata JSON, chuyển Markdown, OCR fallback cho PDF dạng ảnh và kiểm tra lại output | `data/landing/`, `data/standardized/`, `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py`, `src/task3_convert_markdown.py` | Done |
| Chunking, index và retrieval | Cài đặt loader, recursive chunking 500/50, ID ổn định, embedding TF-IDF + LSA 384 chiều, Chroma cosine, dense search, BM25 và RRF | `src/task4_chunking_indexing.py` đến `src/task7_reranking.py` | Done |
| PageIndex và retrieval pipeline | Cài đặt chuyển 8 Markdown sang PDF Unicode, cache/fingerprint `doc_id`, polling có timeout, parse `retrieved_nodes`, score theo rank và fallback an toàn; nối dense + BM25 + RRF + PageIndex | `src/task8_pageindex_vectorless.py`, `src/task9_retrieval_pipeline.py`, `tests/test_task8_pageindex.py` | Done bằng mock; chưa kiểm thử API thật vì thiếu key |
| Generation và UI | Cài đặt reorder không mutate, context có title/source/URL, dispatch OpenAI/Gemini/Anthropic, kiểm tra citation, safe refusal; nối Streamlit và lưu đầy đủ sources trong lịch sử | `src/task10_generation.py`, `app.py` | Done bằng mock; chưa gọi LLM thật vì thiếu key |
| Dữ liệu đánh giá và kiểm thử | Tạo 15 câu hỏi grounded, ghi cấu hình retrieval trung thực, chạy contract/acceptance test và smoke test UI | `group_project/evaluation/golden_dataset.json`, `group_project/evaluation/RESULT.md`, `tests/` | Partial: chưa chạy A/B metrics |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Dùng recursive chunking `500/50` và embedding local TF-IDF + LSA 384 chiều, đồng thời bắt buộc corpus và query dùng chung `embed_texts()`.
   **Lý do/evidence:** Quy chế có nhiều điều/khoản ngắn; cửa sổ 500 ký tự thường giữ được một đến hai khoản, overlap 50 bảo vệ nội dung ở ranh giới. Việc tải mô hình Hugging Face/ONNX không ổn định trong môi trường thực thi, trong khi LSA chạy offline và tái lập được.
   **Trade-off:** Không phụ thuộc API và dễ chạy lại, nhưng khả năng hiểu đồng nghĩa tiếng Việt kém hơn multilingual embedding; vì vậy cần BM25 để hỗ trợ thuật ngữ, mã văn bản và tên riêng.

2. **Quyết định:** Fuse dense và BM25 đúng một lần bằng RRF, chỉ dùng dense score gốc để quyết định PageIndex fallback; giữ nhãn `[Document N]` ổn định trước khi reorder context.
   **Lý do/evidence:** Dense score, BM25 score và RRF score khác thang đo. Nhãn citation ổn định giúp từng citation trong câu trả lời truy ngược chính xác về `sources` mà UI hiển thị.
   **Trade-off:** Pipeline có thêm bước fusion, kiểm tra citation và fallback nên tăng độ trễ; đổi lại tránh so sánh score sai và giảm nguy cơ hiển thị nguồn không khớp câu trả lời.

## Kiểm thử và kết quả

- **Test/query đã dùng:** `pytest tests/test_contracts.py -q`, `pytest -q`; query retrieval “Điều kiện công nhận tốt nghiệp đại học là gì?”; query ngoài domain “Thời tiết trên sao Hỏa hôm nay thế nào?”.
- **Kết quả trước/sau:** Contract test từ 5 failure còn `15 passed`; toàn bộ suite hiện `23 passed`. Corpus gồm 8 document và 1.134 chunk không trùng ID. Task 8 chuyển thành công 8/8 PDF; smoke test UI không có exception, citation mapping đúng và lịch sử giữ đủ sources/score sau rerun.
- **Lỗi phát hiện và cách xử lý:** PDF Thăng Long chỉ có ảnh nên bổ sung OCR fallback; fallback từng dùng nhầm thang điểm nên chuyển sang dense score gốc; reorder từng có nguy cơ làm `[Document N]` lệch với `sources` nên gắn citation index trước reorder; thiếu `.env` khiến UI luôn safe-refuse, đã xác định là lỗi cấu hình LLM thay vì lỗi retrieval.

## Điều còn hạn chế

- **Hạn chế cụ thể:** Chưa có API key nên chưa kiểm thử live OpenAI/Gemini/Anthropic và PageIndex Cloud. Các metric faithfulness, answer relevance, context recall và context precision chưa được chạy; `RESULT.md` đang ghi `N/A` thay vì đưa số liệu không có bằng chứng.
- **Ưu tiên tiếp theo:** Cấu hình một LLM provider, upload PageIndex thật, hiệu chỉnh threshold bằng tập câu hỏi in-domain/out-of-domain, rồi chạy A/B dense-only so với hybrid + RRF trên cùng 15 golden cases.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- **Ngày:** 20/09/2026
- **Tên thành viên:** [Bổ sung họ và tên]
