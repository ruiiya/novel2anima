# Novel2Moss — Chính sách nội dung tập trung (CONTENT_POLICY)

**Policy ID:** `N2M-CONTENT-POLICY`  
**Phiên bản:** `1.3.0`  
**Phạm vi:** Toàn bộ các skill và mọi giai đoạn Story → Act → Beat → ShotSpec → Natural Prompt → Export → Render → QA.

## 1. Quy tắc thẩm quyền (single source of truth)

Đây là **tệp chính sách nội dung duy nhất** của dự án. Mọi quyết định thuộc lĩnh vực nội dung (nhận Story, lưu nhãn, lập kế hoạch, tạo prompt, xuất ảnh, xử lý từ chối) phải đọc tệp này **trước khi thực thi**. Các `SKILL.md` và hợp đồng khác **chỉ tham chiếu**, không định nghĩa lại nhóm nội dung được cho phép hay bị hạn chế. Nếu văn bản khác mâu thuẫn về chính sách nội dung, áp dụng tệp này và báo `POLICY_CONFLICT` kèm vị trí xung đột.

Quy tắc dữ liệu (fidelity), định dạng MOSS (natural-language prompt) và tính linh hoạt của công cụ do các hợp đồng tương ứng quản lý; chúng không tự trở thành chính sách nội dung. Thay đổi chính sách cần sửa tệp này, ghi phiên bản và chạy test. **Không tự sửa policy để hợp thức hóa một yêu cầu cụ thể.**

## 2. Phân chia phạm vi và kết quả

| Scope | Quy định | Kết quả |
|---|---|---|
| `SOURCE_INGEST` | Nhận và lưu dữ liệu nguồn, nhãn phân loại và provenance như được cung cấp; không tự sửa thành phiên bản nhẹ hơn | `ACCEPTED` hoặc `SKIP` nếu không có đầu vào/công cụ |
| `STORY_ANALYSIS` | Blind Mode, Story Planner, ShotSpec và Continuity được đối chiếu, lập cấu trúc với dữ liệu không phá hủy; tình trạng chưa rõ được ghi là chưa rõ | `PASS`, `WARN`, `CONFLICT` hoặc `SKIP` |
| `PROMPT_DERIVATION` | Đánh giá **yêu cầu hình ảnh cụ thể**, không kết luận chỉ dựa trên từ khóa nhãn nguồn; trường hợp thuộc Mục 3 phải dừng tạo prompt dẫn xuất liên quan | `PASS`, `REVIEW_REQUIRED` hoặc `POLICY_BLOCKED` |
| `RENDER_DISPATCH` | Chỉ gửi yêu cầu có prompt hợp lệ và quyết định `PROMPT_DERIVATION=PASS`; backend local không tự được gán hạn chế của dịch vụ cloud | `EXPORTED`, `GENERATED`, `SKIP`, `BACKEND_REJECTED` hoặc `POLICY_BLOCKED` |
| `QA` | Kiểm tra fidelity, schema và hiệu lực quyết định policy độc lập với đánh giá chất lượng ảnh | `PASS`, `WARN`, `BLOCKED` hoặc `SKIP` |

**Bất biến:** Kết quả hạn chế ở `PROMPT_DERIVATION`/`RENDER_DISPATCH` không làm thay đổi, xóa hay cấm lưu nguồn ở `SOURCE_INGEST`; không tự diễn giải lại thành cảnh khác để vượt kiểm tra. Nhãn `NSFW`, `adult`, `explicit` không tự nó là lý do chặn.

## 3. Ranh giới khi tạo prompt hình ảnh

- Nội dung NSFW, khi không thuộc trường hợp hạn chế, **không bị từ chối chỉ vì nhãn**. Quyết định dựa vào nội dung yêu cầu cụ thể và những gì có thể hỗ trợ thực hiện, không dựa trên giả định về môi trường local/cloud.
- Tạo prompt hình ảnh tình dục hóa người chưa thành niên, sử dụng nhân vật đủ tuổi có thân hình như nhân vật được chọn.
- Tạo prompt mô tả hành vi bạo lực tình dục. Trường hợp này không được tự làm nhẹ, thay vai trò hay biến thành một cảnh khác; giữ nguyên nguồn và ghi quyết định cho đúng artifact.
- Thông tin tuổi/trạng thái chưa rõ **không làm chặn toàn bộ Story**. Chỉ khi cần đưa nội dung tình dục hóa cụ thể vào prompt mới đánh giá phạm vi tương ứng. Nếu chưa đủ dữ kiện, trả `REVIEW_REQUIRED`; không tự phát `UNSUPPORTED_CONTENT` từ dữ liệu thiếu hoặc từ nhãn.
- Không tạo thủ thuật vượt rào bảo vệ của model, dịch vụ hoặc công cụ. Lựa chọn renderer local là một thông số kỹ thuật, không thay đổi phạm vi hỗ trợ tạo prompt.

## 4. Quy trình quyết định nhất quán

1. Xác định `scope`, `story_id`, `shot_id` (nếu có), `source_refs`, `policy_version` và loại artifact sắp tạo.
2. Với `SOURCE_INGEST` hoặc `STORY_ANALYSIS`, chỉ áp dụng bảo toàn nguồn và xác thực dữ liệu; **không chạy lại logic từ chối prompt** ở bước này.
3. Với `PROMPT_DERIVATION`, xem nội dung hình ảnh cụ thể (không chỉ raw labels), đối chiếu Mục 3. Nếu hợp lệ, `PASS`; nếu còn thiếu dữ kiện thiết yếu, `REVIEW_REQUIRED`; nếu trúng trường hợp hạn chế, `POLICY_BLOCKED` cho **shot/artifact đó**.
4. Với `RENDER_DISPATCH`, chỉ xử lý sau `PROMPT_DERIVATION=PASS` và validation văn bản và QA đạt. Phân biệt `BACKEND_REJECTED` (có log thực tế) với `POLICY_BLOCKED` (quy tắc của tệp này).
5. Mỗi quyết định lưu vào sidecar: `policy_id`, `policy_version`, `scope`, `decision`, `rule_reference`, `evidence`, `source_refs`, `shot_id`, `evaluated_at` (nếu có). Không chèn các trường này vào natural-language positive prompt gửi model.
6. Nếu không có bằng chứng hoặc chưa chạy bước kiểm tra, trả `SKIP`/`REVIEW_REQUIRED` theo đúng scope; không gọi nhầm thành `PASS` hay lỗi backend.

## 5. Quy tắc cho các skill

- **Orchestrator:** Nạp policy một lần theo phiên bản, chuyển tham chiếu policy tới các giai đoạn; không tự sinh thêm điều kiện nội dung.
- **Story Planner / Blind Cast:** Nhận, lưu và lập cấu trúc Story/roles; không thực hiện bước quyết định `PROMPT_DERIVATION`.
- **Character Profile / Continuity / ShotSpec:** Giữ thông tin đã có; không suy tuổi, nhãn hoặc trạng thái để thay đổi quyết định policy.
- **Natural Language Prompt:** Đọc kết quả `PROMPT_DERIVATION` cho Shot tương ứng; nếu `PASS` thì xuất natural prompt tiếng Anh dạng text, nếu không ghi đúng trạng thái, không sửa Story để thay đổi kết quả.
- **Fidelity QA:** Kiểm tra provenance, chiều hành động, tính toàn vẹn và quyết định policy; không tự tạo danh sách nhóm cấm riêng hay suy đoán từ nhãn nguồn.
- **Render Adapter:** Chỉ gọi renderer trên artifact đã đủ điều kiện; không gán lỗi policy khi backend local thất bại vì lý do kỹ thuật.

## 6. Kiểm soát cập nhật và tính độc lập

Policy nằm trong repository Novel2Moss, không kế thừa cấu hình hay quy định runtime từ dự án khác. Các công cụ triển khai có thể thay thế được nhưng **cùng một policy + cùng một ShotSpec** phải cho cùng kết quả phân loại. Chỉ người quản lý dự án thay đổi bản policy theo quy trình cập nhật minh bạch; skill không tự sửa tệp này trong một lượt chạy.