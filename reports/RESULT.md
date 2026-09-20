# RAG evaluation results

## Run information

| Field | Value |
|---|---|
| Evaluation date | 2026-09-20 (Asia/Ho_Chi_Minh) |
| Framework and version | Custom rubric evaluator v1; `google-genai==2.24.0` |
| Evaluator model | `gemini-3.5-flash-lite`, temperature 0 |
| Generator model | `gemini-3.1-flash-lite`, temperature 0.3, top-p 0.9 |
| Embedding model | `keepitreal/vietnamese-sbert`, 768 dimensions |
| Corpus version/commit | Git `6275777493f2a6c7f04f23f00ec47373496420d0`; 8 documents / 461 chunks |
| Golden dataset size | 15 cases |
| `top_k` | 5 final results for both configs |
| Fallback threshold and calibration | 0.45; in-domain 0.684271, out-of-domain 0.278075 |

## Configurations

- **Config A — dense-only:** cosine search lấy trực tiếp 5 chunk từ ChromaDB.
- **Config B — hybrid + RRF:** dense top 10 và BM25 top 10, fuse đúng một lần
  bằng RRF (`k=60`), sau đó giữ 5 chunk. Candidate depth thuộc retrieval
  strategy; final `top_k` vẫn bằng Config A.

Hai config dùng cùng golden dataset, generator, evaluator, prompt và final
`top_k`; biến thay đổi duy nhất là retrieval strategy.

### Retrieval and indexing configuration

- Chunking: recursive, `chunk_size=500`, `chunk_overlap=50`. Overlap 10% hạn chế
  mất ngữ cảnh ở ranh giới mà không làm số vector tăng quá nhiều.
- Stable chunk ID: `{relative_document_path}::chunk-{chunk_index}`. ChromaDB dùng
  upsert và xóa ID không còn trong corpus nên re-index không tạo bản sao.
- Embedding: `keepitreal/vietnamese-sbert`, vector 768 chiều được normalize và
  tìm bằng cosine distance. Corpus và query đều gọi chung `embed_texts()`.
- Corpus: 8 documents, 461 chunks, gồm 183 legal và 278 news. Re-index lần hai
  vẫn giữ nguyên 461 records.
- Threshold `0.45` được chọn từ query in-domain có best dense score `0.684271`
  và query out-of-domain có score `0.278075`. Đây là calibration cho corpus hiện
  tại, không phải ngưỡng đúng cho mọi dữ liệu.
- PageIndex chưa bật vì chưa có `PAGEINDEX_API_KEY`. Khi provider unavailable,
  pipeline bắt lỗi và giữ kết quả hybrid.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
|---|---:|---:|---:|
| Faithfulness | 1.000 | 0.953 | -0.047 |
| Answer relevance | 0.773 | 0.847 | +0.073 |
| Context recall | 0.760 | 0.853 | +0.093 |
| Context precision | 0.613 | 0.680 | +0.067 |
| **Average** | **0.787** | **0.833** | **+0.047** |

## A/B comparison

- Cấu hình tốt hơn: **Config B cho retrieval**, nhưng chưa nên coi là cấu hình
  cuối cùng vì faithfulness giảm ở hai case.
- Evidence: hybrid tăng recall mạnh nhất (+0.093), tiếp theo là relevance (+0.073)
  và precision (+0.067). Ở case 13 về hình thức đóng học phí, dense-only không
  lấy được evidence và phải từ chối, trong khi hybrid lấy được `article_04` và
  trả lời đúng. Tuy nhiên hybrid kéo thêm thông tin vay tín dụng ở case này và
  thiếu nửa điều kiện ở case 6, làm faithfulness trung bình giảm 0.047.
- Trade-off: sau khi bỏ lượt cold-start, retrieval trung bình là 0.0827 giây với
  A và 0.1229 giây với B; B chậm hơn khoảng 49% do thêm BM25 và RRF. Generation
  lần lượt là 1.7644 và 2.1605 giây; end-to-end xấp xỉ 1.847 và 2.283 giây
  (+24%). Hai config có cùng số lần gọi generator/evaluator và cùng final top-5.
  Lượt A đầu tiên mất 15.40 giây để load embedding model nên không được dùng để
  so sánh latency steady-state.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | UEH hỗ trợ những hình thức đóng học phí nào? | A | 1.00 | 0.00 | 0.00 | 0.00 | retrieval | Dense top-5 chỉ lấy nội dung học bổng/hỗ trợ, không lấy `article_04`; generator từ chối đúng theo context. |
| 2 | Sinh viên ĐHCQ cần đăng ký tối thiểu bao nhiêu tín chỉ để được xét học bổng khuyến khích học tập? | B | 1.00 | 0.00 | 0.00 | 0.00 | retrieval | Dense và BM25 đều xếp các chunk học bổng liên quan nhưng không đưa chunk chứa điều kiện 15 tín chỉ vào final top-5; RRF không cứu được evidence bị xếp quá sâu. |
| 3 | Điểm rèn luyện yêu cầu cho học bổng Hỗ trợ học tập toàn phần và bán phần khác nhau thế nào đối với sinh viên ĐHCQ? | A | 1.00 | 0.00 | 0.00 | 0.20 | retrieval | Hai điều kiện nằm qua ranh giới chunk; top-5 thiếu cặp evidence nên model từ chối. Config B cải thiện nhưng chunk 42 vẫn bị cắt trước phần bán phần. |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
|---:|---|---|---|---|
| 1 | Thêm title, heading và field định danh tài liệu vào văn bản BM25; thử Vietnamese word segmentation. | Case 2 có từ khóa rõ nhưng cả A/B không lấy điều kiện 15 tín chỉ vào top-5. | Tăng recall cho điều khoản chính xác, mã và tên riêng mà không đổi embedding. | Chạy lại cùng 15 case; case 2 phải có expected evidence trong top-5 và recall > 0, precision tổng không giảm. |
| 2 | Chunk theo heading/list để giữ trọn cụm bullet; thử `chunk_size` 650–750 và overlap 75. | Case 5–6 thiếu các bullet liền kề; case 6 hybrid chỉ thấy điều kiện toàn phần. | Tăng recall và faithfulness cho câu hỏi tổng hợp nhiều điều kiện. | Re-index và chạy lại A/B; chỉ nhận thay đổi nếu recall case 5–6 tăng và báo cáo đầy đủ precision/latency. |
| 3 | Thêm bước lọc hoặc rerank nhẹ sau RRF, không đưa chunk dưới ngưỡng liên quan vào context. | Case 13B có 3/5 chunk nhiễu; model thêm chi tiết vay tín dụng ngoài trọng tâm, faithfulness còn 0.8. | Tăng context precision và giảm nội dung mở rộng ngoài câu hỏi. | So B hiện tại với B+rereanker trên đúng 15 case; yêu cầu precision và faithfulness tăng, recall không giảm quá 0.02. |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
|---|---|---:|---:|---|
| Chưa chạy bonus | Config B ở trên | N/A | N/A | Không tuyên bố bonus khi chưa có phép đo riêng. |

## Evaluation method and reproducibility

Mỗi case được chấm một lần bằng cùng rubric judge. Bốn định nghĩa metric bám theo
faithfulness, answer relevance, context recall và context precision của RAGAS,
nhưng đây là **custom Gemini rubric**, không phải kết quả trực tiếp từ package
RAGAS. Raw answer, source ID, title, latency, score và rationale nằm trong
`group_project/evaluation/evaluation_results.json`. Có thể chạy lại bằng:

```bash
python group_project/evaluation/run_evaluation.py
```

Evaluator LLM có tính chủ quan và một lần chấm chưa tạo confidence interval.
Recommendation vì vậy dựa thêm trên việc đọc answer và chunk của ba case thấp
nhất, không chỉ dựa trên average. Khi thay corpus, chunking hoặc model cần xóa
artifact cũ hay version hóa run để không tái sử dụng cache của cấu hình trước.
