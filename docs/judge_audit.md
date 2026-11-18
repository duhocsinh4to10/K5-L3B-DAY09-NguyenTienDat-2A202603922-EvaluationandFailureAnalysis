# Judge audit

Chạy:
- `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10`
- `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10`

| Tiêu chí | n | κ | Precision | Recall | Confusion (`FAIL` = dương tính) | Fail rate (observed → Rogan-Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` | 100 | **0.757** | **0.857** | **0.800** | `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}` | `0.280 → 0.300` | **Có** (`0.757 ≥ 0.6`, `0.857 ≥ 0.8`, `0.800 ≥ 0.7`) | **Dùng** (đánh giá văn phong/thái độ) |
| `helpful` | 100 | **0.375** | **1.000** | **0.300** | `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` | `0.090 → 0.300` | **Không** (`κ = 0.375 < 0.6`, `R = 0.300 < 0.7`) | **Loại** (cấm dùng làm gate) |

## ≥5 case audit thủ công (từ `judge_tone_public.csv` và `judge_helpful_public.csv`)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric / dữ liệu |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* — Xưng `"em"` + `"nha"` quá suồng sã; judge lầm tưởng là thân thiện. **Sửa rubric:** bắt buộc xưng `"LogiX"` và gọi khách `"anh/chị"`, cấm xưng `"em"`/`"bạn"` và khẩu ngữ `"nha"`/`"nhé"`. |
| 2 | `H-017` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* — Xưng `"bạn ơi"` + `"nha"` không đúng chuẩn CSKH. **Sửa rubric:** liệt kê rõ danh sách đại từ bị cấm (`bạn`, `cậu`, `mình`, `em`). |
| 3 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* — Có từ `"Dạ, vui lòng"` ở đầu nhưng vế sau mang giọng ra lệnh (`"không cần nhắn thêm"`). **Sửa rubric:** chấm toàn bộ câu, phạt các mệnh lệnh chặn họng khách dù có kính ngữ đầu câu. |
| 4 | `H-042` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** (FP) | Reply: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* — Câu ngắn gọn, lịch sự, đủ thông tin nhưng judge phạt vì thiếu câu xin lỗi dài dòng (verbosity bias). **Sửa rubric:** không bắt buộc câu xin lỗi rườm rà khi hoàn tiền thành công, chỉ cần đủ `"Dạ ... ạ"` và thông tin đơn/tiền. |
| 5 | `H-051` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** (FP) | Reply: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* — Quy chuẩn CSKH LogiX cho phép thuật ngữ `"refund"`, nhưng judge phạt vì pha tiếng Anh. **Sửa rubric:** thêm allowlist thuật ngữ nghiệp vụ được phép dùng (`refund`, `voucher`, `order`, `ship`). |
| 6 | `H-063` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* — Hứa hẹn `"sẽ hoàn thêm"` ngoài kết quả hệ thống. **Sửa rubric:** đánh `FAIL` mọi cam kết bồi thường/hoàn thêm không có trong kết quả xử lý. |
| 7 | `H-070` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* — Dùng emoji cười cợt (`😂😂`) trong ngữ cảnh khiếu nại. **Sửa rubric:** cấm tuyệt đối emoji trong phản hồi khiếu nại/hoàn tiền. |
| 8 | `H-081` (`tone_ok`) | `FAIL` | `PASS` | **Judge đúng** (Lỗi nhãn người) | Reply: *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* — Thiếu câu hỗ trợ mở và người gán nhãn đọc nhầm ticket. **Hành động:** sửa lại nhãn người (`human_label`) trong tập golden sau khi double-check. |
| 9 | `H-094` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** (FN) | Reply: *"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."* — Mất toàn bộ dấu tiếng Việt. **Sửa rubric:** yêu cầu tiếng Việt có dấu chuẩn, đánh `FAIL` văn bản không dấu. |
| 10 | `HL-016` (`helpful`) | `PASS` | `FAIL` | **Người đúng** (FN nghiêm trọng) | Reply xin lỗi rất dài và lịch sự nhưng báo hoàn `55.000đ` trong khi ledger chỉ ghi `35.000đ` (`FM-08`). Judge chấm `helpful` chỉ đọc câu chữ (bị thao túng bởi độ dài và lời xin lỗi) mà không đọc ledger. **Hành động:** loại bỏ `judge_helpful`, chuyển kiểm tra số tiền sang code grader `ReplyMatchesLedger` (`reply_matches_ledger`). |

## Kết luận
- **Tiêu chí được giữ lại (`tone_ok`):** Đạt cả 3 ngưỡng sàn ($\kappa = 0.757 \ge 0.6$, $\text{Precision} = 0.857 \ge 0.8$, $\text{Recall} = 0.800 \ge 0.7$). Tỷ lệ lỗi quan sát được là `28.0%`, sau khi hiệu chỉnh bằng công thức **Rogan-Gladen** (với $\text{sensitivity} = 0.800$, $\text{specificity} = 66/70 \approx 0.943$) cho tỷ lệ lỗi thực tế ước lượng là **`30.0%`**.
- **Tiêu chí bị loại (`helpful`) và lý do:**
  - Ma trận nhầm lẫn của `helpful` là `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` ($\text{Precision} = 1.000$, nhưng **$\text{Recall} = 0.300 < 0.70$** và **$\kappa = 0.375 < 0.60$**).
  - Trong 30 ca lỗi thực tế (`tp + fn = 30`), judge bỏ lọt tới **21 ca (`fn = 21`, tức 70% số lỗi)** — trong đó có **18 ca báo sai số tiền (`FM-08`)** kèm lời xin lỗi dài dòng (`HL-015`, `HL-016`, `HL-020`, `HL-028`, `HL-035`, `HL-041`, `HL-043`, `HL-053`, `HL-058`, `HL-062`, `HL-070`, `HL-072`, `HL-074`, `HL-087`, `HL-090`, `HL-096`, `HL-098`, `HL-100`) và 3 ca sai xưng hô (`HL-047`, `HL-091`, `HL-097`).
  - **Lý do cốt lõi:** LLM Judge chỉ nhìn văn bản `reply` nên mắc thiên kiến ưa lời văn trôi chảy/dài dòng (*verbosity & politeness bias*) và hoàn toàn mù trước trạng thái cơ sở dữ liệu (`refund_ledger`). Nếu dùng `judge_helpful` làm CI gate, 70% lỗi hoàn sai tiền hoặc hứa khống sẽ lọt qua cổng release. Do đó, mọi kiểm tra về số tiền và phê duyệt bắt buộc phải chấm bằng **code grader** (`RefundAmountCorrect`, `ReplyMatchesLedger`, `ApprovalBypass`).
- **Rủi ro còn lại:** Judge `tone_ok` hiện mới được kiểm định trên tập dữ liệu replay công khai (`n = 100`); nếu tinh chỉnh rubric theo các bất đồng ở trên và đánh giá lại trên chính tập này sẽ gây overfitting vào bộ calibration. Cần thu thập và gán nhãn kép (human double-annotation) trên một tập **held-out mới** trước khi đưa `tone_ok` vào production.
