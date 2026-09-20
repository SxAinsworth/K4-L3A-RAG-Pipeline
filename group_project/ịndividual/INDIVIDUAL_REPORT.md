# Individual contribution report

Mỗi thành viên copy template này thành:

```text
reports/<student-id>-<short-name>.md
```

Giới hạn khuyến nghị: 1 trang, không chép lại README hoặc mô tả lý thuyết chung. Báo cáo không phải một bài pipeline cá nhân; mục đích là ghi nhận ownership và bằng chứng đóng góp trong sản phẩm nhóm.

---

## Thông tin

- Họ và tên: Trương Thị Lan Anh
- Mã học viên: 2A202602451
- Nhóm: فتيات جميلات
- Repository/branch:lananh

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Thu thập và chuẩn hóa dữ liệu | Thu thập 3 PDF quy chế và 5 trang công khai; hoàn thiện crawler, metadata JSON, chuyển đổi Markdown và OCR cho PDF dạng ảnh | `data/landing/`, `data/standardized/`, `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py`, `src/task3_convert_markdown.py` | Done |
| Chunking và indexing | Cài đặt document loader, recursive chunking 500/50, ID ổn định, embedding TF-IDF + LSA 384 chiều và lưu vào ChromaDB | `src/task4_chunking_indexing.py` | Done |
| Retrieval | Hoàn thiện dense search, BM25, RRF; bảo đảm kết quả đúng schema, không trùng ID và sắp xếp giảm dần | `src/task5_semantic_search.py`, `src/task6_lexical_search.py`, `src/task7_reranking.py` | Done |
| PageIndex fallback | Chuyển Markdown sang PDF Unicode, cache `doc_id`, polling có timeout, parse kết quả PageIndex và xử lý lỗi provider | `src/task8_pageindex_vectorless.py`, `tests/test_task8_pageindex.py` | Partial — chưa chạy API thật vì thiếu key |
| Generation và giao diện | Hoàn thiện context, citation, safe refusal, dispatch LLM và giao diện Streamlit hiển thị source, method, score | `src/task9_retrieval_pipeline.py`, `src/task10_generation.py`, `app.py` | Partial — chưa gọi LLM thật vì thiếu key |
| Evaluation và kiểm thử | Tạo 15 golden cases, chạy contract test, acceptance test và smoke test giao diện | `group_project/evaluation/`, `tests/` | Partial — chưa chạy A/B metrics |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Sử dụng recursive chunking với `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50` và embedding local TF-IDF + LSA 384 chiều.

   **Lý do/evidence:** Tài liệu quy chế có nhiều điều và khoản ngắn. Kích thước 500 ký tự thường giữ được một đến hai khoản trong cùng chunk, còn overlap 50 giúp bảo toàn nội dung tại ranh giới. Mô hình embedding local chạy ổn định và không phụ thuộc API hoặc quá trình tải model bên ngoài.

   **Trade-off:** Hệ thống dễ chạy lại và không tốn API embedding, nhưng khả năng hiểu từ đồng nghĩa tiếng Việt hạn chế hơn multilingual embedding. BM25 được sử dụng bổ sung để tìm thuật ngữ, mã văn bản và tên riêng.

2. **Quyết định:** Kết hợp dense và BM25 đúng một lần bằng RRF; dùng dense score gốc để quyết định PageIndex fallback và gắn nhãn citation trước khi reorder context.

   **Lý do/evidence:** Dense score, BM25 score và RRF score thuộc các thang đo khác nhau nên không thể so sánh trực tiếp. Nhãn `[Document N]` ổn định giúp citation trong câu trả lời đối chiếu chính xác với phần tử tương ứng trong `sources`.

   **Trade-off:** Fusion, kiểm tra citation và fallback làm tăng độ trễ, nhưng giảm nguy cơ so sánh score sai, trả lời thiếu căn cứ hoặc hiển thị nguồn không khớp.

## Kiểm thử và kết quả

- **Test hoặc query tôi đã dùng:** `pytest tests/test_contracts.py -q`, `pytest -q`; query “Điều kiện công nhận tốt nghiệp đại học là gì?” và query ngoài domain “Thời tiết trên sao Hỏa hôm nay thế nào?”.
- **Kết quả trước/sau nếu có:** Contract test từ 5 failure còn `15 passed`; toàn bộ test suite đạt `23 passed`. Corpus gồm 8 document và 1.134 chunk có ID duy nhất. Task 8 chuyển đổi thành công 8/8 tài liệu sang PDF.
- **Lỗi đã phát hiện và cách xử lý:** PDF Thăng Long chỉ chứa ảnh nên bổ sung OCR fallback; fallback từng sử dụng sai thang điểm nên chuyển sang dense score gốc; citation từng có nguy cơ lệch sau reorder nên gắn citation index trước khi đổi thứ tự; giao diện luôn safe-refuse được xác định do thiếu `LLM_MODEL` và API key, không phải lỗi retrieval.

## Điều còn hạn chế

- **Một hạn chế cụ thể của phần tôi làm:** Chưa có API key nên chưa kiểm thử trực tiếp OpenAI/Gemini/Anthropic và PageIndex Cloud. Các metric faithfulness, answer relevance, context recall và context precision chưa được chạy.
- **Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện:** Cấu hình LLM provider, kiểm thử PageIndex thật, hiệu chỉnh fallback threshold bằng câu hỏi in-domain/out-of-domain và chạy A/B dense-only so với hybrid + RRF trên cùng 15 golden cases.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 20/9/2026
- Tên thành viên: Trương Thị Lan Anh
