# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-20 (Asia/Ho_Chi_Minh) |
| Framework and version              | Custom rubric evaluator v1; `google-genai==2.24.0` |
| Evaluator model                    | `gemini-3.5-flash-lite`, temperature 0 |
| Generator model                    | `gemini-3.1-flash-lite`, temperature 0.3, top-p 0.9 |
| Embedding model                    | `keepitreal/vietnamese-sbert`, 768 dimensions |
| Corpus version/commit              | Git `6275777493f2a6c7f04f23f00ec47373496420d0`; 8 documents / 461 chunks |
| Golden dataset size                | 15 cases |
| `top_k`                            | 5 final results for both configs |
| Fallback threshold and calibration | 0.45; in-domain 0.684271, out-of-domain 0.278075 |

## Configurations

- **Config A — dense-only:** cosine search lấy trực tiếp 5 chunk từ ChromaDB.
- **Config B — hybrid + RRF:** dense top 10 và BM25 top 10, fuse đúng một lần
  bằng RRF (`k=60`), sau đó giữ 5 chunk. Candidate depth là một phần của retrieval
  strategy; final `top_k` vẫn bằng Config A.

Hai config phải dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

### Retrieval and indexing configuration

- Chunking: recursive, `chunk_size=500`, `chunk_overlap=50`. Kích thước này giữ
  các đoạn đủ ngắn để định vị điều khoản, còn overlap 10% hạn chế mất ngữ cảnh ở
  ranh giới mà không làm số vector tăng quá nhiều.
- Stable chunk ID: `{relative_document_path}::chunk-{chunk_index}`; ChromaDB dùng
  upsert và xóa ID không còn trong corpus để re-index không tạo bản sao hoặc giữ
  chunk lỗi thời.
- Embedding: `keepitreal/vietnamese-sbert`, 768 dimensions, normalized vectors,
  cosine distance. Đây là model chuyên tiếng Việt và được dùng chung qua
  `embed_texts()` cho cả corpus lẫn query.
- Corpus tại checkpoint retrieval: 8 documents, 461 chunks (183 legal và 278
  news). Re-index lần hai vẫn giữ nguyên 461 records.
- Fallback threshold tạm chọn: `0.45`, dựa trên best dense cosine score của câu
  in-domain “Điều kiện nhận học bổng hỗ trợ học tập UEH là gì?” (`0.684271`)
  và câu out-of-domain “Nhiệt độ bề mặt của sao Betelgeuse là bao nhiêu?”
  (`0.278075`). Đây chỉ là calibration ban đầu cho corpus và embedding model
  hiện tại; cần hiệu chỉnh lại trên toàn bộ golden dataset.
- PageIndex chưa được bật vì `PAGEINDEX_API_KEY` chưa cấu hình. Pipeline vẫn thử
  fallback dưới threshold và giữ kết quả hybrid nếu provider unavailable.

## Overall scores

| Metric            | Config A | Config B | Delta B−A |
| ----------------- | -------: | -------: | --------: |
| Faithfulness      |    1.000 |    0.953 |    -0.047 |
| Answer relevance  |    0.773 |    0.847 |    +0.073 |
| Context recall    |    0.760 |    0.853 |    +0.093 |
| Context precision |    0.613 |    0.680 |    +0.067 |
| **Average**       |    0.787 |    0.833 |    +0.047 |

## A/B comparison

- Cấu hình tốt hơn: **Config B cho retrieval**, nhưng chưa nên coi là cấu hình
  cuối cùng vì faithfulness giảm ở hai case.
- Evidence: hybrid tăng recall mạnh nhất (+0.093), tiếp theo là relevance (+0.073)
  và precision (+0.067). Case 13 (hình thức đóng học phí) là khác biệt rõ nhất:
  dense-only không lấy được evidence và phải từ chối, trong khi hybrid lấy được
  `article_04` và trả lời đúng. Tuy vậy, hybrid kéo thêm thông tin vay tín dụng ở
  case này và thiếu nửa điều kiện ở case 6, làm faithfulness trung bình giảm 0.047.
- Trade-off về latency/cost: bỏ lượt cold-start đầu tiên, retrieval trung bình là
  0.0827 giây (A) và 0.1229 giây (B), tức B chậm hơn khoảng 49% do chạy thêm BM25
  và RRF. Generation lần lượt là 1.7644 và 2.1605 giây; end-to-end xấp xỉ 1.847
  và 2.283 giây (+24%). Hai config đều gọi generator và evaluator đúng 15 lần,
  cùng final top-5 nên số API call bằng nhau; B chỉ tăng chi phí CPU retrieval và
  có thể tăng token theo độ dài chunk thực tế. Lượt đầu A mất 15.40 giây để load
  embedding model nên không dùng để so latency steady-state.

## Worst performers

|   # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage             | Root cause |
| --: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------------------- | ---------- |
|   1 | UEH hỗ trợ những hình thức đóng học phí nào? | A | 1.00 | 0.00 | 0.00 | 0.00 | retrieval | Dense top-5 chỉ lấy nội dung học bổng/hỗ trợ, không lấy `article_04`; generator từ chối đúng theo context. |
|   2 | Sinh viên ĐHCQ cần đăng ký tối thiểu bao nhiêu tín chỉ để được xét học bổng khuyến khích học tập? | B | 1.00 | 0.00 | 0.00 | 0.00 | retrieval | Cả dense lẫn BM25 xếp các chunk học bổng liên quan nhưng không đưa chunk chứa điều kiện 15 tín chỉ vào final top-5; RRF không cứu được evidence bị xếp quá sâu. |
|   3 | Điểm rèn luyện yêu cầu cho học bổng Hỗ trợ học tập toàn phần và bán phần khác nhau thế nào đối với sinh viên ĐHCQ? | A | 1.00 | 0.00 | 0.00 | 0.20 | retrieval | Điều kiện toàn phần và bán phần nằm qua ranh giới chunk; top-5 thiếu cặp evidence nên model từ chối. Config B cải thiện nhưng chunk 42 vẫn bị cắt trước phần bán phần. |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
|        1 | Thêm title/heading và các field định danh tài liệu vào văn bản được BM25 lập chỉ mục; cân nhắc Vietnamese word segmentation. | Case 2 dùng từ khóa rất rõ nhưng cả A/B không đưa điều kiện 15 tín chỉ vào top-5. | Tăng recall cho điều khoản chính xác, mã và tên riêng mà không đổi embedding. | Chạy lại cùng 15 case; case 2 phải có expected evidence trong top-5 và recall > 0, đồng thời precision tổng không giảm. |
|        2 | Chunk theo heading/list và giữ trọn cụm bullet điều kiện; thử `chunk_size` 650–750 với overlap 75 rồi re-index. | Case 5–6 thiếu các bullet liền kề; case 6 hybrid chỉ thấy điều kiện toàn phần vì ranh giới chunk. | Tăng recall và faithfulness cho câu hỏi tổng hợp nhiều điều kiện. | A/B lại trên cùng golden set; kiểm tra source ID case 5–6 và chỉ nhận thay đổi nếu recall tăng mà precision/latency vẫn được báo cáo. |
|        3 | Sau RRF, thêm bước lọc/rerank nhẹ theo độ liên quan trước generation, không đưa chunk dưới ngưỡng vào context. | Case 13B trả đúng nhưng 3/5 chunk là nhiễu và model thêm chi tiết vay tín dụng ngoài trọng tâm, làm faithfulness 0.8. | Giảm nhiễu, tăng context precision và ngăn generator mở rộng sang thông tin không được hỏi. | So sánh B hiện tại với B+rereanker trên đúng 15 case; yêu cầu precision và faithfulness tăng, recall không giảm quá 0.02, đồng thời ghi latency. |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Chưa chạy bonus | Config B ở trên | N/A | N/A | Không tuyên bố bonus khi chưa có phép đo riêng. |

## Evaluation method and reproducibility

Mỗi case được chấm một lần bằng cùng rubric judge. Bốn định nghĩa metric bám theo
faithfulness, answer relevance, context recall và context precision của RAGAS,
nhưng đây là **custom Gemini rubric**, không phải kết quả từ package RAGAS. Raw
answer, source ID, title, latency, score và rationale được lưu trong
`evaluation_results.json`; runner có cache theo cặp `(case_index, config)` và có
thể chạy lại bằng `python group_project/evaluation/run_evaluation.py`.

Evaluator LLM có tính chủ quan và một lần chấm chưa cho confidence interval. Vì
vậy recommendation dựa thêm trên việc đọc answer và chunk của ba case thấp nhất,
không chỉ dựa trên average. Khi thay corpus/chunking/model cần xóa artifact cũ hoặc
version hóa run để tránh tái sử dụng cache của cấu hình trước.
