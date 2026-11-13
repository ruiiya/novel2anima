# Novel2Moss — Công cụ linh hoạt

Skill định nghĩa đầu vào, hợp đồng và QA; **không** khóa vào LLM/IDE/framework/model API cụ thể. Dùng Python/SQLite mặc định để kiểm chứng và xuất file; có thể thay tool nếu kết quả giữ nguyên.

| Giai đoạn | Năng lực | Bằng chứng |
|---|---|---|
| Story | Nhận nguồn, Story/Act/Beat và role | provenance, revision |
| Catalog | Tìm đúng nhân vật/outfit/vocab | source, trạng thái review |
| Shot | ShotSpec actor→target, pose, outfit | shot ID/revision |
| Continuity | Trạng thái before/delta/after | snapshot |
| **Natural Prompt** | Viết mô tả hình ảnh hoàn chỉnh bằng tiếng Anh, trực tiếp từ ShotSpec | `.txt` UTF-8, prompt ID/hash |
| QA | Kiểm tra ý nghĩa & dạng văn bản | report subject=PROMPT |
| Export | Text + manifest/QA sidecar, file gộp Story/Act | hash, số Shot đúng |
| Render (ngoài DB) | Sử dụng text trong ComfyUI hoặc backend tương thích | runtime log và file ảnh ngoài DB |

Không dựng Layout/bbox hay bắt buộc dùng prompt enhancer. Nếu backend có enhancer tự viết lại, tắt khi cần giữ nguyên prompt đã QA. Negative prompt/seed/steps/model nằm ở renderer ngoài DB. Khi chưa thực thi tool, trả `SKIP` và bằng chứng; không tuyên bố đã render.

Artifact:

```text
story_source.json → story_plan.json → shot_spec.json → natural.prompt.txt
                                 → fidelity_report.json + prompt.manifest.json
                                 → renderer downstream (ngoài DB)
```

Mọi quyết định nội dung thuộc `docs/novel2moss/CONTENT_POLICY.md`, không tự áp quy định của cloud cho backend local. Thay tool không được làm thay đổi nguồn hoặc lời miêu tả đã duyệt.
