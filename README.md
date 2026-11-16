# Novel2Anima Skills V4 — Visual Storytelling · Natural Prompts · Database-First

Novel2Anima là project **độc lập**, hỗ trợ **Blind** và **Non-Blind**. Mỗi Shot được viết thành **một prompt Anima (tag block + tối đa 2 câu bổ trợ, UTF-8)** cho Anima-Aesthetic-v1.1. **Không dùng Layout JSON / bbox** trong luồng mới.

```text
Story → Act → Beat/Event → Visual Bible + Storyboard → ShotSpec → Continuity
      → Anima Prompt (mỗi Shot một .txt) → Fidelity/Sequence QA → Seal → Export
                                                                          │
                                                                          └── Renderer riêng, không kết nối DB
```

## Cài đặt

Python 3.10+; SQLite trong Python stdlib. Giải nén bundle này, sau đó:

```powershell
python install.py --target D:\NGV\novel2anima --mode claude --upgrade
cd D:\NGV\novel2anima
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python database/src/n2m_db.py stats --detailed
```

**Khi nâng cấp từ bản Layout V2:** `--upgrade` sao lưu file cũ trước khi thay. Installer dọn các skill/tool/docs Layout cũ theo **danh sách tệp cố định**, sao lưu trước khi xóa. Migration `007_natural_prompts.sql` chỉ **bổ sung** `shot_prompts` và QA `PROMPT`; **không drop hay sửa dữ liệu Layout lịch sử**. `CONTENT_POLICY.md` ở project đích luôn được giữ nguyên khi nâng cấp (cần đối chiếu thủ công nếu file policy cũ còn ghi “Layout”).

**Nâng cấp V3 → V4:** chạy installer --upgrade rồi init. Migration 008 bổ sung storyboard, coverage, Visual Bible, liên kết Shot và seal, không sửa dữ liệu cũ. Story chưa có storyboard vẫn export theo V3. Để dùng V4, lập storyboard có duyệt và QA lại; không tự coi dữ liệu lịch sử là storyboard đã duyệt.

## 12 skill

| Skill | Vai trò |
|---|---|
| `novel2anima-orchestrator` | Điều phối hai mode, dừng chờ duyệt Story trước khi commit |
| `novel2anima-story-planner` | Story/Act/Beat/Event |
| **`novel2anima-storyboard-planner`** | **Nhịp kể, Shot purpose/order/branch, Visual Bible, source coverage, seal** |
| `novel2anima-blind-cast` | Role tạm và casting về sau |
| `novel2anima-character-profile` | Identity và Outfit có provenance |
| `novel2anima-shot-spec` | Shot, actor→target, scene, camera |
| `novel2anima-continuity` | Before/delta/after xuyên Shot |
| **`novel2anima-anima-prompt`** | **Sinh positive prompt Anima (tag block) từ ShotSpec** |
| `novel2anima-fidelity-qa` | Kiểm tra fidelity trước export |
| `novel2anima-database` | Migration, revision, transaction, QA/export |
| `novel2anima-catalog-ingest` | Import catalog có nguồn, chỉ khi skill sử dụng |
| `novel2anima-render-adapter` | File-only downstream, độc lập DB |

## Sử dụng prompt theo Shot

Khởi đầu bằng orchestrator. Chốt Story Brief, sau đó chốt storyboard; mỗi prop/location/style/role có description và provenance. Blind giữ role tạm; Non-Blind dùng casting đã xác nhận. Đọc [hợp đồng V4](docs/novel2anima/VISUAL_STORYTELLING.md) và các JSON mẫu.

```powershell
python database/src/n2m_workflow.py save-storyboard --story-id STORY_ID --file storyboard.json --expected-revision 0
python database/src/n2m_workflow.py get-storyboard --storyboard-id BOARD_ID
```

Tạo ShotSpec/Continuity bằng các skill, soạn file `.txt` Anima (tag block + câu bổ trợ) theo `docs/novel2anima/ANIMA_TAG_PROMPT.md`, sau đó:

```powershell
# Validate định dạng (không thay QA ngữ nghĩa)
python tools/novel2anima/validate_anima_prompt.py drafts/S01.txt

# Lưu natural prompt vào DB, nhận PROMPT_ID
python database/src/n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt

# Lưu kết quả QA đã kiểm tra
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file reports/S01.qa.json

# Export prompt riêng
python database/src/n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir exports/STORY_ID/S01/1

# Seal đã pin Shot/Prompt/QA ID sau khi kiểm tra cả chuỗi
python database/src/n2m_workflow.py seal-storyboard --storyboard-id BOARD_ID --file seal.json

# Export toàn Story + các file mỗi Act (V4: chỉ lấy storyboard đã seal)
python database/src/n2m_db.py export-story-prompts --story-id STORY_ID --out-dir exports/STORY_ID
```

Bundle mỗi Shot: `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`.

Bundle cả Story: `prompts.all.jsonl` và `prompts/A01.jsonl`, `prompts/A02.jsonl`... Mỗi dòng JSON có `prompt` là **string văn xuôi**, một dòng trống ngăn cách record, không có Layout JSON.

V4 ghi thêm storyboard_id, shot_order, branch_key, purpose và QA/continuity tham chiếu. Sửa cục bộ dùng `compare-storyboards --old-id ... --new-id ...` để xác định slot thay đổi và hậu duệ cần kiểm tra. Không tự chọn revision gần nhất chưa được duyệt.

## Catalog

- `seed` chỉ thêm **47 vocabulary** do dự án xác định và đăng ký nguồn. Không tải dataset/ảnh, không seed layout templates mới.
- `collect_sources.py`, `catalog_imports.py` hỗ trợ metadata DeepGHS, Danbooru, outfit generic... chỉ được import khi đã có skill tiêu thụ. `docs/novel2anima/DATABASE_SOURCES.md` nêu phạm vi.

## Các ranh giới cố định

- Nội dung nguồn/nhãn và quyết định policy riêng tại `docs/novel2anima/CONTENT_POLICY.md`. Không tự suy diễn nhãn NSFW là lỗi format.
- DB chỉ phục vụ tạo Story → Prompt; **không chứa render job, image, GPU, checkpoint, seed hoặc image QA**.
- Renderer local/remote tùy chọn, chỉ nhận giá trị positive text từ `.txt`; không bắt buộc ComfyUI.
- Natural prompt phải nêu đủ người, hành động, trang phục, vị trí, camera, ánh sáng và chi tiết trực quan mà Shot yêu cầu. Tránh chuỗi tag và chi tiết tưởng tượng không có căn cứ.

## Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Migrations cũ 001–007 giữ nguyên. Không có chuyển đổi Layout→Natural hoặc V3→sealed storyboard tự động vì thiếu provenance. Các file Layout cũ trong DB vẫn có thể xem để kiểm tra lịch sử nhưng không được lấy làm đầu vào mặc định cho prompt mới.

## Tài liệu Anima

- https://huggingface.co/circlestone-labs/Anima (thứ tự tag, safety vocabulary, cú pháp tag)
- https://civitai.com/articles/35368 (prompting guidebook: camera/lighting/background, ngân sách token)
- Hợp đồng dự án: `docs/novel2anima/ANIMA_TAG_PROMPT.md`

*Chỉ phần tạo prompt/database được triển khai ở bundle; chưa tự gọi LLM hoặc render ảnh.*
