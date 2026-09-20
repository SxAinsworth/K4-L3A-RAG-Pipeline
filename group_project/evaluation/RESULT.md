# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-20 |
| Framework and version              | pytest acceptance checks; runtime A/B evaluation not run |
| Evaluator model                    | Not run |
| Generator model                    | Configured by `.env`; not recorded in an evaluation run |
| Embedding model                    | Configured by `.env`; not recorded in an evaluation run |
| Corpus version/commit              | Working tree snapshot; commit not recorded |
| Golden dataset size                | 15 |
| `top_k`                            | 5 in the application default |
| Fallback threshold and calibration | Configured by retrieval pipeline; calibration not measured |

## Configurations

- **Config A — dense-only:** Defined as the planned dense retrieval baseline; no metric run recorded.
- **Config B — hybrid + RRF:** Implemented in the pipeline; no metric run recorded.

Hai config phải dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric            | Config A | Config B | Delta B−A |
| ----------------- | -------: | -------: | --------: |
| Faithfulness      |     N/A |     N/A |      N/A |
| Answer relevance  |     N/A |     N/A |      N/A |
| Context recall    |     N/A |     N/A |      N/A |
| Context precision |     N/A |     N/A |      N/A |
| **Average**       |     N/A |     N/A |      N/A |

## A/B comparison

- Cấu hình tốt hơn: Chưa kết luận vì chưa có run A/B.
- Evidence: Acceptance tests xác nhận golden dataset có 15 case và corpus có đủ hai loại nguồn; chưa có điểm metric.
- Trade-off về latency/cost: Chưa đo; hybrid + RRF dự kiến tốn thêm chi phí truy vấn BM25 và fusion so với dense-only.

## Worst performers

|   # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage             | Root cause |
| --: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------------------- | ---------- |
|   1 | Chưa có run đánh giá | N/A | N/A | N/A | N/A | N/A | not run | Chưa thu thập log lỗi |
|   2 | Chưa có run đánh giá | N/A | N/A | N/A | N/A | N/A | not run | Chưa thu thập log lỗi |
|   3 | Chưa có run đánh giá | N/A | N/A | N/A | N/A | N/A | not run | Chưa thu thập log lỗi |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
|        1 | Chạy cùng một golden dataset qua dense-only và hybrid + RRF | Chưa có baseline số liệu | Có cơ sở chọn retrieval strategy | Lưu output và điểm theo từng case |
|        2 | Ghi lại model, embedding, top_k và threshold trong mỗi run | Metadata runtime hiện chưa đầy đủ | Tăng khả năng tái lập | Kiểm tra metadata trong artifact run |
|        3 | Phân tích ba case điểm thấp nhất sau khi có output | Chưa có log lỗi để phân tích | Xác định lỗi retrieval hay generation | Tạo bảng failure analysis từ kết quả |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Chưa chạy | Không có baseline đo được | N/A | N/A | Chạy evaluation runner khi API key và evaluator đã cấu hình |
