# Novel2Anima — DB Operations V4 · Visual Storytelling

Dùng Python 3.10+, chạy từ project root. `--db PATH` luôn đứng **trước** subcommand.

## 1. Init / seed / stats

```powershell
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python database/src/n2m_db.py stats --detailed
python -m unittest discover -s tests -v
```

Migration 007 bổ sung `shot_prompts` và QA `PROMPT`, giữ các bảng Layout lịch sử. `seed` chỉ vocabulary + source registry; không seed Layout mới, không download.

Migration 008 thêm Visual Bible, storyboard, coverage, dependency, seal. Đọc `VISUAL_STORYTELLING.md` để dùng schema V4.

## 2. Import metadata (không thay đổi)

```powershell
python database/src/collect_sources.py list
python database/src/collect_sources.py fetch --source deepghs
python database/src/collect_sources.py verify
python database/src/n2m_db.py import-deepghs-md database/imports/deepghs/blue_archive.md
python database/src/n2m_db.py search-catalog character "asuna"
```

Chỉ nhập dataset có skill dùng thực sự; không lấy dữ liệu render hoặc ảnh vào DB. Các lệnh `import-tags-csv`, `import-costume-gallery-json`, `import-tag-relations-json` vẫn hoạt động như trước.

## 3. Story / Shot / Continuity

```powershell
python database/src/n2m_db.py create-story --title "Sample" --mode BLIND --text-file story.txt
python database/src/n2m_db.py add-role --story-id STORY_ID --key LEAD
python database/src/n2m_workflow.py save-plan --story-id STORY_ID --file story_plan.json
python database/src/n2m_workflow.py add-act --story-id STORY_ID --order 1 --title "Beginning"
python database/src/n2m_workflow.py add-beat --act-id ACT_ID --order 1 --summary "Beat 1"
python database/src/n2m_workflow.py save-shot --beat-id BEAT_ID --shot-key S01 --file shot_spec.json
python database/src/n2m_workflow.py save-continuity --shot-id SHOT_ID --file continuity.json
```

Blind có thể lưu Story/Shot trước casting. Non-Blind gán nhân vật trước Shot; cả hai đều dùng cùng định dạng prompt Anima.

V4: sau materialize Event và trước ShotSpec, lưu/đọc storyboard đã chốt bằng save-storyboard/get-storyboard. Sau QA thực, seal-storyboard, rồi export. Các lệnh trong ví dụ V3 giữ tương thích, nhưng storyboard mới phải theo hợp đồng V4.

## 4. Natural Prompt (định dạng duy nhất gửi model)

Soạn `drafts/S01.txt` theo `docs/novel2anima/ANIMA_TAG_PROMPT.md`; dòng 1 là tag block Anima, dòng 2 tối đa 2 câu bổ trợ bằng tiếng Anh mặc định. Natural prompt được **soạn trực tiếp từ ShotSpec** bởi skill/LLM của dự án; các script SQLite không tự sinh nội dung.

```powershell
python tools/novel2anima/validate_natural_prompt.py drafts/S01.txt
python database/src/n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file reports/S01.qa.json
python database/src/n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir exports/STORY_ID/S01/1
python tools/novel2anima/validate_natural_prompt.py exports/STORY_ID/S01/1/natural.prompt.txt --manifest exports/STORY_ID/S01/1/prompt.manifest.json
```

`PASS` trong lệnh QA chỉ được ghi khi đã đối chiếu ý nghĩa. V4 từ chối export prompt chưa PASS đúng policy; V3 legacy nếu chưa làm QA thì sidecar ghi SKIP, không giả báo PASS.

## 5. Export toàn Story

```powershell
python database/src/n2m_db.py export-story-prompts --story-id STORY_ID --out-dir exports/STORY_ID
```

Đầu ra:

```text
exports/STORY_ID/
  prompts.all.jsonl
  prompts/A01.jsonl
  prompts/A02.jsonl
  bundles/A01/B01/<shot_id>/<prompt_revision>/
    natural.prompt.txt
    prompt.manifest.json
    fidelity_report.json
```

Mỗi record JSONL chứa `shot_key`, `page`, `act`, `beat`, `camera`, `focus`, `bundle_dir`, `prompt_sha256`, **`prompt` (text string)**. Record nằm trên một dòng, cách nhau **một dòng trống**. Không có JSON Layout trong giá trị `prompt`. Khi thiếu prompt của Shot mới nhất hoặc QA `BLOCKED`, xuất cả Story thất bại thay vì âm thầm bỏ Shot.

V4 thêm storyboard_id/shot_order/branch_key/purpose/qa_id/continuity_sha256, lựa chọn revision theo seal, không chọn theo shot_key. Dùng thư mục riêng cho từng lần export để không trộn file lịch sử.

## 6. Ranh giới

Novel2Anima DB **dừng tại export**. Renderer lấy file `.txt`/`prompt` string, không gọi DB CLI hay truy vấn SQLite. Không có `queue-render`, `render_jobs`, `render_assets`, image QA. Lịch sử Layout từ V2 không bị xóa trong migration; không có lệnh ghi Layout mới.
