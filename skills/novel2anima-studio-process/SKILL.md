---
name: novel2anima-studio-process
description: "V6: quản lý chốt Story, approval theo revision/hash, status nhiều Story, review và prompt export; không tạo ảnh hoặc kết nối ComfyUI."
---
# Novel2Anima — Studio Process V6

## Mục tiêu

Là **process checker**, không thay kỹ năng sáng tác. Người dùng và AI đối thoại nhiều vòng để chốt toàn Story rồi người dùng xác nhận **từng stage** `STORY → RESEARCH_VISUAL → STORYBOARD → PROMPTS → export`. Người dùng tự render và phản hồi bằng mô tả văn bản. **Không tự duyệt thay người dùng.**

## Hợp đồng bắt buộc

Đọc `docs/novel2anima/STUDIO_V6.md` và `docs/novel2anima/CONTENT_POLICY.md`. Sử dụng `database/src/n2a_studio.py`; không dùng `save-plan` với `approval.status` làm thay xác nhận Stage. Chỉ chạy `decide-stage --user-confirmed` sau khi người dùng thật sự nói rõ duyệt/chốt artifact được trình bày; không tự tạo evidence phê duyệt từ suy đoán. Không tự chuyển stage.

- `submit-stage` cần review JSON với verdict PASS và bằng chứng rõ ràng, không ghi PASS cho QA chỉ chạy cú pháp.
- `status` và `list-stories` trả trạng thái từng Story, revision, stage tiếp theo; `STALE` buộc review/duyệt lại.
- Không thay đổi artifact đã duyệt; tạo version mới và chỉ invalidate downstream dựa trên dependency thực tế.
- `export` chỉ khi stage PROMPTS đã duyệt theo hash/revision, lấy đúng seal, prompt IDs và QA được pin.
- Khi user báo lỗi trang N: `report-feedback`, đối chiếu Story/Bible/Storyboard/Prompt, đề xuất diff và sửa tại tầng phù hợp; `resolve-feedback` không tự cấp approval mới.

## Không làm

Không quản lý ComfyUI, video, ảnh, candidate, GPU, seed, CFG, scheduler render hay LoRA. Không tách Album/Comic thành hai engine; Blind/Non-Blind vẫn ở casting. Không đặt policy nội dung mới ngoài `CONTENT_POLICY.md`.
