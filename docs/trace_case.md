# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (`item_id`: `E-002`), run ID `E-seeded_regression-20261118-e698` trong `src/reports/eval_seeded_regression.json` (và xuất hiện tương tự trên `swarm C-002@55`, run ID `E-swarm-20261118-e698` trong `src/reports/baseline_v1.json`) |
| Triệu chứng | `TrialPass` (`lab8_pass`), `DbFactKept` và `RefundAmountCorrect` đều `FAIL` (`status resolved != denied`). Event `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` và ledger (`refund_ledger`) thực sự đã ghi `refund_vnd = 20000`, `refund_count = 1`, trong khi nhãn chuẩn (`labels_v1.json`) yêu cầu `status = "denied"`, `refund_vnd = 0`, `refund_count = 0`. |
| Bước sai đầu tiên | Event `3` · kind `model_override` · payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `1` (`handoff`) khởi tạo đúng phạm vi chỉ đọc cho `C-002` (`allowed_tools: ["lookup_order", "lookup_policy", "compute_compensation"]`). Event `2` (`investigator`) truy vấn DB trả về đúng sự thật của đơn `O-202`: `{"visible": true, "order": {"order_id": "O-202", "status": "delivered", "delay_days": 2, "shipping_fee_vnd": 20000}}` và báo giá gốc từ investigator là `0đ` (do `delay_days = 2 < 3`). Phải tới Event `3` (`model_override`), agent mới lấy con số `"trễ 5 ngày"` từ nội dung ticket của khách để ghi đè `order["delay_days"] = 5`, kéo theo Event `4` (`quote`) tính lại `amount_vnd = 20000` (`SHIP-LATE-03`) và gọi `issue_refund` ghi sai `20.000đ` vào ledger. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11` (`E-fixed-20261118-e698`), sau Event `2` (`investigator` đọc `delay_days = 2`), agent **không** phát sinh event `model_override`, giữ nguyên `delay_days = 2` của DB nên Event `3` (`quote`) giữ `{"amount_vnd": 0, "reason": "not_eligible", "clause_ids": [], "parts": {}}`, không gọi `issue_refund` (`ledger.refund_vnd = 0`), và Event `4` (`reply`) trả lời đúng `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."` (`status = "denied"`). |
| Regression test | `tests/test_lab9_graders.py::test_trace_case_c002_seed11_regression` — kiểm tra đồng thời `DbFactKept` (step-level: bắt `model_override`) và `RefundAmountCorrect` (outcome-level: đối chiếu `snapshot["refund_vnd"]` với nhãn, bắt được cả biến thể `quiet_override` khi không ghi event `model_override`). Đã xác nhận `FAIL` (`False`) trên `seeded_regression C-002@11` và `PASS` (`True`) trên `fixed C-002@11`. |
| Chưa chắc chắn | Trace chỉ ghi nhận việc `order["delay_days"]` bị đè bởi `parsed_delay = 5` sau khi gọi `parse_delay_days(ticket)`, nhưng trên LLM thật trace ở mức event này không cho biết model bị prompt injection đánh lừa ở bước suy luận nội bộ (chain-of-thought) hay do lỗi code điều phối truyền nhầm biến `parsed_delay` vào tool `compute_compensation`. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
