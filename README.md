# Novel2Moss Skills V3 — Natural Prompts · Độc lập · Database-First

Novel2Moss là project **độc lập**, hỗ trợ **Blind** và **Non-Blind**. Mỗi Shot được viết thành **một prompt ngôn ngữ tự nhiên (UTF-8, mặc định tiếng Anh)** cho MOSS-Image. **Không dùng Layout JSON / bbox** trong luồng mới.

```text
Story → Act → Beat → ShotSpec → Character/Outfit/Continuity
      → Natural Prompt (mỗi Shot một .txt) → Fidelity QA → Export Bundle
                                                     │
                                                     └── Renderer riêng, không đọc/ghi DB
```

## Cài đặt

Python 3.10+; SQLite trong Python stdlib. Giải nén bundle này, sau đó:

```powershell
python install.py --target D:\NGV\novel2moss --mode claude --upgrade
cd D:\NGV\novel2moss
python database/src/n2m_db.py init
python database/src/n2m_db.py seed
python database/src/n2m_db.py stats --detailed
```

**Khi nâng cấp từ bản Layout V2:** `--upgrade` sao lưu file cũ trước khi thay. Installer dọn các skill/tool/docs Layout cũ theo **danh sách tệp cố định**, sao lưu trước khi xóa. Migration `007_natural_prompts.sql` chỉ **bổ sung** `shot_prompts` và QA `PROMPT`; **không drop hay sửa dữ liệu Layout lịch sử**. `CONTENT_POLICY.md` ở project đích luôn được giữ nguyên khi nâng cấp (cần đối chiếu thủ công nếu file policy cũ còn ghi “Layout”).

## 11 skill

| Skill | Vai trò |
|---|---|
| `novel2moss-orchestrator` | Điều phối hai mode, dừng chờ duyệt Story trước khi commit |
| `novel2moss-story-planner` | Story/Act/Beat/Event |
| `novel2moss-blind-cast` | Role tạm và casting về sau |
| `novel2moss-character-profile` | Identity và Outfit có provenance |
| `novel2moss-shot-spec` | Shot, actor→target, scene, camera |
| `novel2moss-continuity` | Before/delta/after xuyên Shot |
| **`novel2moss-natural-language-prompt`** | **Sinh positive prompt trực tiếp từ ShotSpec** |
| `novel2moss-fidelity-qa` | Kiểm tra fidelity trước export |
| `novel2moss-database` | Migration, revision, transaction, QA/export |
| `novel2moss-catalog-ingest` | Import catalog có nguồn, chỉ khi skill sử dụng |
| `novel2moss-render-adapter` | File-only downstream, độc lập DB |

## Sử dụng prompt theo Shot

Tạo ShotSpec/Continuity bằng các skill, soạn file `.txt` natural-language theo `docs/novel2moss/MOSS_NATURAL_PROMPT.md`, sau đó:

```powershell
# Validate định dạng (không thay QA ngữ nghĩa)
python tools/novel2moss/validate_natural_prompt.py drafts/S01.txt

# Lưu natural prompt vào DB, nhận PROMPT_ID
python database/src/n2m_workflow.py save-natural-prompt --shot-id SHOT_ID --file drafts/S01.txt

# Lưu kết quả QA đã kiểm tra
python database/src/n2m_workflow.py save-qa --kind PROMPT --subject-id PROMPT_ID --verdict PASS --file reports/S01.qa.json

# Export prompt riêng
python database/src/n2m_db.py export-bundle --prompt-id PROMPT_ID --out-dir exports/STORY_ID/S01/1

# Export toàn Story + các file mỗi Act
python database/src/n2m_db.py export-story-prompts --story-id STORY_ID --out-dir exports/STORY_ID
```

Bundle mỗi Shot: `natural.prompt.txt`, `prompt.manifest.json`, `fidelity_report.json`.

Bundle cả Story: `prompts.all.jsonl` và `prompts/A01.jsonl`, `prompts/A02.jsonl`... Mỗi dòng JSON có `prompt` là **string văn xuôi**, một dòng trống ngăn cách record, không có Layout JSON.

## Catalog

- `seed` chỉ thêm **47 vocabulary** do dự án xác định và đăng ký nguồn. Không tải dataset/ảnh, không seed layout templates mới.
- `collect_sources.py`, `catalog_imports.py` hỗ trợ metadata DeepGHS, Danbooru, outfit generic... chỉ được import khi đã có skill tiêu thụ. `docs/novel2moss/DATABASE_SOURCES.md` nêu phạm vi.

## Các ranh giới cố định

- Nội dung nguồn/nhãn và quyết định policy riêng tại `docs/novel2moss/CONTENT_POLICY.md`. Không tự suy diễn nhãn NSFW là lỗi format.
- DB chỉ phục vụ tạo Story → Prompt; **không chứa render job, image, GPU, checkpoint, seed hoặc image QA**.
- Renderer local/remote tùy chọn, chỉ nhận giá trị positive text từ `.txt`; không bắt buộc ComfyUI.
- Natural prompt phải nêu đủ người, hành động, trang phục, vị trí, camera, ánh sáng và chi tiết trực quan mà Shot yêu cầu. Tránh chuỗi tag và chi tiết tưởng tượng không có căn cứ.

## Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Migrations cũ 001–006 giữ nguyên; không có chuyển đổi Layout→Natural tự động vì có nguy cơ mất ngữ nghĩa. Các file Layout cũ trong DB vẫn có thể xem để kiểm tra lịch sử nhưng không được lấy làm đầu vào mặc định cho prompt mới.

## Tài liệu MOSS-Image

- https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md#prompt-guidelines
- https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md
- https://github.com/Comfy-Org/docs/blob/main/tutorials/image/moss-image/moss-image.mdx

*Chỉ phần tạo prompt/database được triển khai ở bundle; chưa tự gọi LLM hoặc render ảnh.*
