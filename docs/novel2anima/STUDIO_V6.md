# Novel2Anima V6 — Story & Prompt Studio (tiếng Việt)

## Phạm vi và nguồn sự thật

V6 dùng **Anima**, sinh **prompt text**. Người dùng trao đổi với AI để **chốt toàn bộ Story**, rồi **xác nhận từng giai đoạn**. Người dùng tự render bằng công cụ riêng; Novel2Anima không gọi ComfyUI, không nhận ảnh, seed, GPU hay quản lý queue. Blind/Non-Blind chỉ khác cách chọn nhân vật; `INDEPENDENT` / `CONTINUOUS` là quan hệ giữa các Shot, không có Album/Comic pipeline riêng.

Các dữ liệu gốc và `CONTENT_POLICY.md` không bị sửa bởi migration V6. Dữ liệu legacy giữ nguyên và vẫn có thể đọc/xuất theo quy trình legacy. Khi một Story đã `submit-stage`, lệnh export DB cũ cũng sẽ buộc có approval `PROMPTS` hợp lệ.

`n2a_studio.py` chỉ quản lý **hợp đồng quy trình** và kiểm tra hash/revision; **không tự sáng tác hoặc tự QA ngữ nghĩa**. `review-file` chứa bằng chứng do agent thực sự đánh giá. Không ghi `PASS` khi chưa đọc tài liệu nguồn. Các cổng approval là xác nhận người dùng **qua hội thoại**: CLI dùng `--user-confirmed` chỉ sau khi người dùng thực sự chốt; đây là attestation, không phải chữ ký mật mã chống giả mạo.

## Chuỗi stage và quy tắc chuyển bước

| Stage | Artifact chuẩn | Gate |
|---|---|---|
| `STORY` | `story_revisions` hiện hành (plan và nguồn) | Người dùng chốt toàn Story |
| `RESEARCH_VISUAL` | research document + Visual Bible, có provenance | Người dùng duyệt hướng biểu đạt |
| `STORYBOARD` | `storyboards` đang hiện hành, story revision đúng | Người dùng duyệt phân trang, nhịp kể, continuity |
| `PROMPTS` | `storyboard_seals` + danh sách Shot/Prompt/QA pin | Người dùng duyệt toàn bộ bộ prompt |

Phê duyệt phải khớp chính xác revision/hash. Khi Story thay đổi, tất cả các approval downstream tự được xác định `STALE` ngay khi kiểm tra trạng thái. Khi Visual Bible/Storyboard đổi, phần phụ thuộc cũng phải được review lại. Không suy luận từ im lặng hoặc `approval.status=APPROVED` đã nằm trong JSON cũ thành một **Studio approval**.

## Cách vận hành

Khởi tạo DB sau khi **sao lưu** bản hiện tại:

```powershell
python database/src/n2m_db.py init
python database/src/n2a_studio.py list-stories
python database/src/n2a_studio.py status --story-id STORY_ID
```

Agent tạo `reports/story.review.json` sau khi đối chiếu Story gốc, thử nghiệm mẫu:

```json
{"verdict":"PASS","evidence":"Đã kiểm tra đầy đủ các Act/Beat, quan hệ nhân quả, source coverage và các chỉnh sửa người dùng đã xác nhận.","findings":[]}
```

Khi người dùng **chưa xác nhận**, chỉ đưa kết quả để họ đánh giá. Khi review sẵn sàng:

```powershell
python database/src/n2a_studio.py submit-stage --story-id STORY_ID --stage STORY --review-file reports/story.review.json
# Chỉ sau khi người dùng thực sự chốt trong cuộc hội thoại:
python database/src/n2a_studio.py decide-stage --story-id STORY_ID --stage STORY --decision APPROVED --evidence "User chốt toàn Story r3" --user-confirmed
```

Bước `RESEARCH_VISUAL`: agent tự nghiên cứu theo nội dung đã chốt và lưu file JSON có `research_summary` và `visual_bible` (ghi provenance); người dùng duyệt rồi mới chuyển tiếp.

```powershell
python database/src/n2a_studio.py submit-stage --story-id STORY_ID --stage RESEARCH_VISUAL --file drafts/research_visual.json --review-file reports/research.review.json
python database/src/n2a_studio.py decide-stage --story-id STORY_ID --stage RESEARCH_VISUAL --decision APPROVED --evidence "User chốt Visual Bible" --user-confirmed
```

`STORYBOARD`: dùng các lệnh V5 để xây dựng, đối chiếu event → shot, world-state và QA, không bỏ qua review người dùng. Khi đã có storyboard mới:

```powershell
python database/src/n2a_studio.py submit-stage --story-id STORY_ID --stage STORYBOARD --review-file reports/storyboard.review.json
python database/src/n2a_studio.py decide-stage --story-id STORY_ID --stage STORYBOARD --decision APPROVED --evidence "User duyệt danh sách các trang" --user-confirmed
```

`PROMPTS`: tiếp tục lưu ShotSpec, continuity, biên dịch prompt và ghi QA **thật**. Seal storyboard như V5 (bao gồm QA xuyên Shot). Chỉ sau đó:

```powershell
python database/src/n2a_studio.py submit-stage --story-id STORY_ID --stage PROMPTS --review-file reports/prompts.review.json
python database/src/n2a_studio.py decide-stage --story-id STORY_ID --stage PROMPTS --decision APPROVED --evidence "User duyệt toàn bộ prompt" --user-confirmed
python database/src/n2a_studio.py export --story-id STORY_ID --out-dir exports/STORY_ID/r001
```

Output gồm `prompts.all.jsonl`, các bundle prompt `.txt`, `studio.manifest.json` ghim artifact approval + prompt IDs + hash. Không lưu thông số render. Với Story legacy chưa đăng ký V6, lệnh export V5 cũ vẫn đọc được dữ liệu lịch sử.

### Yêu cầu chỉnh sửa

Nếu người dùng `request changes` tại một stage: ghi quyết định `CHANGES_REQUESTED`; agent sửa đúng artifact, `submit-stage` để tạo revision mới rồi xin người dùng xác nhận lại. Không ghi đè bản cũ.

Sau khi người dùng tự render, họ có thể báo lỗi một trang **bằng mô tả text**. Studio lưu vấn đề và chỉ ra các Shot có dependency cần xem xét:

```powershell
python database/src/n2a_studio.py report-feedback --story-id STORY_ID --shot-key S08 --description "Sai màu áo; các trang khác giữ nguyên"
```

Agent đối chiếu Story/Visual Bible/ShotSpec, chỉ sửa nếu thực sự cần. Với **V5 Prompt Compiler**, việc sửa prompt thường đòi hỏi revision ShotSpec mới; không được tự thay nội dung prompt không khớp compiler. Seal cũ là immutable: nếu cần thay prompt trong cùng storyboard, tạo **board edition mới có nội dung tương tự** với:

```powershell
python database/src/n2m_workflow.py save-storyboard --story-id STORY_ID --file storyboard.json --force-new-revision
```

Sau đó tạo revision Shot/Prompt mới, QA và seal mới; trình diff + xin duyệt lại `STORYBOARD` (khi ngữ nghĩa thay đổi) và `PROMPTS`. Chỉ sửa đúng các trang phụ thuộc, các trang không liên quan có thể tái sử dụng binding nếu bằng chứng cho phép.

Khi đã có prompt revision mới, có thể đánh dấu feedback đã xử lý:

```powershell
python database/src/n2a_studio.py resolve-feedback --feedback-id FEEDBACK_ID --prompt-id NEW_PROMPT_ID --note "Đã cập nhật đúng áo theo Bible, kiểm tra các Shot phụ thuộc"
```

Điều này không tự phê duyệt prompt mới, không tự cập nhật ảnh. Người dùng phải xác nhận lại artifact liên quan.

## Full Review / Quality

AI kiểm tra theo từng stage, chỉ lưu bằng chứng khi đã thực sự đối chiếu:

- Story: cốt truyện, động cơ, nhịp cảm xúc, tính nhân quả, độ bao phủ các Event.
- Research/Visual: nguồn, định danh nhân vật, outfit, scene, đạo cụ, style; không tự đặt canon mới.
- Storyboard: thứ tự, nhịp kể, camera, actor/target, world-state `before/at/after`, chuyển cảnh, independent vs continuous.
- Prompts: Anima tag format, chính xác actor/target, nhận diện, trang phục, bối cảnh và QA xuyên trang; compile từ Bible và context đã duyệt.

Định dạng prompt canonical: tag dòng 1, tối đa **3 câu prose** cho một người / **4 câu** cho nhóm, giới hạn **320 từ**, quality/score prefix hợp lệ, không dùng JSON Layout. Đây là validator cú pháp, không thay kiểm tra ý nghĩa.

## Kiểm thử và rollback

Chạy `python -m unittest discover -s tests -v` trong thư mục repo. Windows: Python >=3.10, mọi file JSON/SQL đọc UTF-8, SQLite connections phải đóng trước cleanup. Migration `011` là **additive**, không sửa `001–010`; trước nâng cấp cần sao lưu file SQLite (không copy nóng trực tiếp từ một connection đang chạy; dùng SQLite backup API hoặc dừng các writer).
