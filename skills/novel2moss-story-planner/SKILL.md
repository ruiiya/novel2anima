---
name: novel2moss-story-planner
description: "Lập Story, Act, Beat và diễn tiến sự kiện của Novel2Moss mà không bịa hoặc làm nhẹ ý định người dùng, giữ nhãn nguồn nhạy cảm và tính liên tục ngữ nghĩa."
---
# Novel2Moss — Lập kế hoạch Story

> **Policy nội dung bắt buộc:** Đọc `docs/novel2moss/CONTENT_POLICY.md` trước khi xử lý. Mọi quyết định nội dung tuân theo scope và phiên bản tại đó; skill này không tự đặt chính sách khác.

## Vai trò

Tạo và sửa **cấu trúc câu chuyện**, không tạo prompt MOSS cuối hoặc payload render. Đọc `docs/novel2moss/CONTENT_FIDELITY.md` trước tiên. Story người dùng cung cấp và các revision tường minh là nguồn có thẩm quyền.

## Khi kích hoạt

Khi tạo Story mới, viết tiếp truyện, thiết kế Act, tạo nhánh, chỉnh plot, chọn sự kiện hoặc chuyển nội dung truyện nguồn thành kế hoạch có cấu trúc.

## Quy trình

1. Giữ văn bản gốc và xuất xứ. Ghi nguyên thể loại, sắc thái, mức độ cùng các nhãn NSFW/người lớn như nguồn. Không tự hạ mức, tăng mức hoặc nói giảm. Nhãn nguồn và điều kiện đủ để sinh ảnh là hai mục riêng.
2. Nếu người dùng đang cần ý tưởng và chưa chọn, đưa một vài concept khác biệt, ngắn gọn; nếu đã chọn, **phát triển đúng nội dung đã chọn** mà không hỏi chọn lại. Sau khi trình brief (premise, nhân vật, nhãn, dàn ý Act/Beat), **dừng và chờ người dùng chốt**; không tự coi việc đã chọn ý tưởng là đã duyệt Story.
3. Chỉ sau khi chốt mới tạo `story_id`, ID vai trò nhân vật ổn định, tiền đề chính, các Beat quan trọng, nhánh và ràng buộc đã biết. Một nhân vật có thể thuộc nhiều Story; trạng thái giới hạn trong từng Story/Act, không thuộc canon toàn cục.
4. Chia Act rồi chia Beat với ID sự kiện và hệ quả dự kiến. Xác định tiến triển dựa trên quan hệ nhân quả và quyết định trong truyện, **không** ép số lượng Shot hay thêm nhánh ngẫu nhiên ngoài yêu cầu.
5. Mỗi sự kiện chỉ rõ `actor_id`, hành động/mục tiêu chính, `target_id` nếu có, phản ứng, kết quả và kiểu chuyển trạng thái. Để `unknown` thay vì bịa đối tượng, tuổi, bối cảnh, sự kiện hoặc người tham gia mới.
6. Trạng thái Beat sau phải nối hợp lý với Beat trước. Ghi rõ camera cut/time cut nếu không cần thể hiện quá trình đổi tư thế/đạo cụ liên tục; cut không cho phép tự xóa trạng thái thể chất.
7. Phân biệt ngữ cảnh truyện với những gì nhìn thấy trong Shot hiện tại. Xuất kế hoạch Act/Beat đủ rõ để ShotSpec chuyển thành mô tả một khung hình.
8. Khi chỉnh sửa, giữ snapshot cũ, tăng revision và xuất semantic delta trước/sau. Không âm thầm sinh lại nội dung đã duyệt.
9. Ghi source_fragment cho Event và các turning point, visual opportunity, reaction, hệ quả quan trọng. Phân biệt sự kiện gốc với gợi ý hình ảnh; bàn giao tất cả Event (kể cả ngữ cảnh) cho storyboard-planner để lập coverage. Không coi phân tích cao trào là lý do cắt nguồn.

## Cổng chốt Story (bắt buộc)

- Brief phải nêu premise, nhân vật/vai trò, nhãn nội dung, scope và dàn ý Act/Beat. Chỉ chuyển sang ghi cấu trúc khi người dùng xác nhận rõ ràng (`chốt`, `duyệt`, `đồng ý`, `ok`).
- Im lặng, câu hỏi hoặc yêu cầu chỉnh sửa **không** phải xác nhận. Không suy diễn từ việc người dùng đã chọn ý tưởng/nhân vật.
- Trước khi chốt: không `create-story`, `add-role`, `bind-role`, `save-plan`, `add-act`, `add-beat`, `add-event`; chỉ trình bày brief. Nếu đã có bản nháp, giữ `DRAFT` và không mở rộng.
- Khi chốt: lưu `approval` vào plan (`status=APPROVED`, người xác nhận, thời điểm) hoặc revision tương ứng. Chưa chốt: `approval.status=PENDING`, kết quả `WAITING_FOR_STORY_APPROVAL`.
- Thay đổi premise, nhân vật, nhãn hoặc phạm vi sau khi chốt phải mở lại cổng và chờ xác nhận mới.

## Lưu nguồn và chính sách

Phân loại gốc phải giữ nguyên và truy vết được. Story Planner hoạt động trong `SOURCE_INGEST` và `STORY_ANALYSIS`; không tự quyết định điều kiện sinh prompt. Mọi quyết định ở bước sau chỉ được lấy từ `CONTENT_POLICY.md` với đúng scope và phiên bản.

## Đầu ra

Kế hoạch truyện có cấu trúc với `story_id`, `source_refs`, `revision`, `approval`, `intent.raw_labels`, `characters[]`, `acts[].beats[].events[]`, tham chiếu nhánh, ràng buộc và các thông tin chưa rõ. Có thể ánh xạ sang bảng dữ liệu thực tế với tài liệu mapping, nhưng không được bỏ các trường ngữ nghĩa bắt buộc.

## Cổng kiểm tra

Không được thiếu/đảo actor-target; mỗi Beat có vai trò nhân quả và thay đổi quan trọng phải tường minh. Khi gặp mâu thuẫn cốt lõi, dừng với `BLOCKED`, không tự xử lý bằng cách bịa sự kiện.

## Đọc/ghi Database V2

- Trước tiên đọc `stories.cast_mode`, `story_sources` (immutable), `story_roles`, `story_revisions` hiện hành. Nếu Story chưa tồn tại, **chỉ sau khi người dùng chốt** mới tạo qua `n2m_db.py create-story` rồi `add-role`; role phải tồn tại trước `story_events`. Trước khi chốt, dừng ở brief và trả `WAITING_FOR_STORY_APPROVAL`.
- Lưu kế hoạch vào `story_revisions.plan_json` bằng `n2m_workflow.py save-plan`. `source_sha256` lấy từ Story nguồn; không ghi đè nguồn hay revision cũ. Khi sửa kế hoạch, tạo revision mới và kiểm tra `--expected-revision` khi có concurrent writers.
- Ánh xạ Act/Beat/Event sang `acts`, `beats`, `story_events` bằng lệnh `add-act`, `add-beat`, `add-event` độc lập; giữ actor/target ở `story_role_id`. **Chưa** có auto-sync nested JSON, không được báo đã tạo Act/Beat nếu chỉ lưu `plan_json`.
- Không ghi đè một Act/Beat/Event khác nội dung; tạo workflow revision projection riêng khi ứng dụng triển khai phần đó. Xem `DATABASE_OPERATIONS.md`.
