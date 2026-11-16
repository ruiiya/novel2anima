# Novel2Anima V4 — Visual Storytelling

V4 bổ sung storyboard, Visual Bible, source coverage và sequence QA trước khi export prompt Anima. Tất cả là văn bản/metadata phục vụ Story → Prompt; renderer hoàn toàn độc lập. Nội dung gốc và nhãn được bảo toàn; mọi quyết định nội dung theo `CONTENT_POLICY.md` hiện hành.

## Luồng

Story nguồn → Story Brief đã chốt → materialize Act/Beat/Event → Blind role hoặc Non-Blind casting → Visual Bible + storyboard đã chốt → ShotSpec → Continuity → Natural Prompt → Fidelity/Sequence QA → seal → export.

Hai cổng chốt Story và storyboard riêng biệt. Agent có thể trình một bảng Shot ngắn để người dùng xem. Không ép số Shot, không tự sáng tác Event mới. Mỗi Shot = một khung hình → một prompt Anima UTF-8. Không dùng Layout JSON, bbox, tọa độ canvas, ghép panel, render job hoặc image QA.

## Hợp đồng Visual Bible và storyboard

Tạo JSON theo `examples/storyboard.example.json` (project cài qua installer: `examples/novel2anima/storyboard.example.json`). Thay ID minh họa bằng ID DB thật. `story_revision` là current_revision (bao gồm casting); plan Story mới nhất phải APPROVED. Storyboard approval cũng phải APPROVED có evidence do người dùng cung cấp. `revision_note` dùng cho một revision mới khi nội dung plan không đổi nhưng sửa prompt/QA/binding.

- `visual_bible.characters`: theo role_key, description, provenance, character_id/outfit_id đúng casting tại story_revision (null khi Blind chưa chọn). Canon identity không trộn với outfit/state theo cảnh. Không tự gán thông tin chưa rõ thành canon.
- `locations`: key ổn định, kiến trúc, nội thất, cửa sổ, trục không gian, nguồn sáng, provenance.
- `props`: key, hình dáng/màu, provenance. Trạng thái sở hữu, vị trí, hư hỏng thuộc continuity.
- `styles`: key, art medium, linework, palette, tone, light treatment, provenance. Tách tone khỏi art style, tùy Story/Shot; không tự thay lựa chọn đã khóa. Không áp preset cố định.
- `shots`: shot_key duy nhất trong storyboard; shot_order chính xác 1..N; beat_id của Story; branch_key; previous_shot_key; transition; purpose; camera; focus; visual_moment; role_keys; location_key; prop_keys; style_key. Camera/focus là ngôn ngữ tự nhiên, không tọa độ.
- `coverage`: mỗi materialized Event của Story phải có ít nhất một mapping. VISUALIZED khóa Event vào Shot trong cùng Beat; CONTEXT_ONLY cần giải thích; UNRESOLVED/UNSUPPORTED_CONTENT giữ nguyên nguồn, không tự chuyển thành cảnh khác. Mỗi slot có ít nhất một Event thật. Nhiều Shot / Event và nhiều Event / Shot đều được phép.

Chuyển camera không thay đổi thế giới. Vị trí trái/phải trên ảnh nằm trong ShotSpec; trái/phải cơ thể và vị trí vật lý nằm trong world state. Chọn góc máy, điểm nhìn, eyeline, khoảng cách, crop vừa đủ để không che khuất hành động chính. Với reverse shot, screen-left/right có thể đổi nhưng người trao/nhận, tay và vật thể không tự đổi.

## CLI (stdlib SQLite)

```powershell
python database/src/n2m_db.py init
python database/src/n2m_workflow.py save-storyboard --story-id STORY_ID --file storyboard.json --expected-revision 0
python database/src/n2m_workflow.py get-storyboard --storyboard-id BOARD_ID
```

`get-storyboard` trả plan, slots theo shot_order, context_sha256 và seal (nếu có). Khi tạo ShotSpec, sao đúng context_sha256 vào `visual_context_sha256`, camera/focus/location_key từ slot; participants dùng role_key, interactions có event_id, actor_role_key/target_role_key và action_text theo Event. Lưu bằng save-shot V3, giữ cùng shot_key. Context hash gồm plan ID, nội dung slot, Event, casting và Bible liên quan; thay đổi không liên quan không làm mất hash. Thứ tự thay đổi được kiểm tra ở cấp sequence, không làm thay đổi wording tự động.

### Continuity V4

Mỗi Shot lưu một snapshot scene (`role_key: null`) và mỗi role hiện diện một snapshot. Dữ liệu `before`, `delta`, `after` ghi world-space; delta tường minh dạng `{"set":{"holding":"notebook"},"remove":[]}`. Set thay giá trị top-level nguyên khối, remove xóa key tường minh. Không có delta ngầm. Scene after phải chứa location_key khớp slot. Với LOCATION_CUT/TIME_CUT, trước vẫn kế thừa, delta diễn tả thay đổi; BRANCH kế thừa đúng predecessor của nhánh. Role ngoài khung giữ state qua Shot trung gian, không tự reset.

Lệnh `save-continuity --shot-id SHOT_ID --file continuity.json`. V3 lịch sử dùng định dạng delta cũ; không tự chuyển đổi. Khi dùng storyboard V4 phải tạo Shot revision/continuity tương thích.

Mẫu CLI: `examples/shot_spec_v4.example.json` và `examples/continuity_v4.example.json` (installer: dưới examples/novel2anima). Mẫu shot_spec.example.json V1 và audit_shot.py chỉ minh họa kiểm tra dạng cũ; V4 dùng role_key + interactions[].event_id + coverage và seal. Nếu thay continuity mà direction/caption không đổi, vẫn cập nhật `continuity_revision_note` với thay đổi state có evidence để save-shot tạo revision mới trước khi lưu snapshot.

### QA, seal và export

Agent thực hiện QA ngữ nghĩa với source, từng ShotSpec, prompt, coverage và sequence; không dùng CLI thay cho LLM/human. Lưu prompt như V3. QA PASS phải có policy_ref và report.policy_decision (scope= PROMPT_DERIVATION, decision=PASS, shot_id chính xác, policy_version và evidence văn bản). Đây là quyết định đã thực hiện, không phải mẫu PASS mặc định. `sequence_qa` ghi verdict PASS và evidence của việc đối chiếu xuyên Shot.

```powershell
python database/src/n2m_workflow.py seal-storyboard --storyboard-id BOARD_ID --file seal.json
python database/src/n2m_db.py export-story-prompts --story-id STORY_ID --out-dir exports/STORY_ID/v4
```

`seal.json` theo `examples/seal.example.json`: bindings map shot_key → shot_id/prompt_id. Seal chỉ thành công khi mọi slot đúng ID/visual context/camera/focus/location/participants, mọi coverage được giải quyết, mọi snapshot đúng continuity, mọi prompt đã QA PASS và sequence QA PASS. Seal pin exact IDs + hash, append-only. Export mặc định chọn storyboard mới nhất, từ chối khi chưa seal hoặc Story/casting hiện hành đã đổi. Không nhảy về revision cũ. Một bản lịch sử đã seal chỉ xuất khi chỉ định rõ `--storyboard-id BOARD_ID` (đối chiếu/archive, không mặc định là bản hiện hành). QA sau seal không còn PASS cũng chặn export.

V3 Story chưa có storyboard vẫn dùng luồng export cũ, giữ tương thích. Không tự seal V3 vì không có đủ provenance/coverage. Chuyển sang V4 cần lập storyboard và QA thật.

Kết quả: mọi dòng JSONL chứa prompt dạng string; với V4 thêm storyboard_id, shot_order, branch_key, purpose, qa_id, continuity_sha256. File bundle .txt dùng định dạng Anima (tag block). Các sidecar không gửi model. Nên dùng thư mục export riêng cho mỗi revision để tránh file cũ lẫn vào.

## Sửa cục bộ / revision

Tìm tầng lỗi → sửa evidence/slot/ShotSpec/continuity/prompt đúng tầng → tạo storyboard revision kế tiếp (expected-revision đúng). So sánh context hash của slot, sau đó so sánh before với predecessor. Chỉ reuse artifact khi bằng chứng xác nhận không bị ảnh hưởng; nếu thay state thì tính lại hậu duệ của nhánh. Nếu chỉ sửa wording, ghi revision_note mới, tạo prompt revision mới rồi QA và seal lại; không ghi đè seal trước. Đừng tái sinh toàn bộ Story do một lỗi cục bộ.

```powershell
python database/src/n2m_workflow.py compare-storyboards --old-id OLD_BOARD_ID --new-id NEW_BOARD_ID
```

Trả added/removed/changed, recheck_descendants, candidate_reuse và order_changed. Candidate reuse chỉ là gợi ý kỹ thuật, không thay QA. Cần kiểm tra lại cả coverage và sequence khi đổi thứ tự.

## Nguồn kỹ thuật tham khảo (không là runtime dependency)

- [Baoyu Comic](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-comic): storyboard, art style/tone, review gate.
- [Agentic Comic Drama Studio](https://github.com/siyuan-liu31/agentic-comic-drama-studio): Visual Bible, versioned assets, linked shotlist.
- [Agent Mangaka Forge](https://github.com/RemiPelloux/agent-mangaka-forge): character visual lock.
- [Agent Comic Kit](https://github.com/Saeyeon-developer/agent-comic-kit): sửa cục bộ, khóa direction.
- [Comic Studio](https://github.com/CallmeTruong/Comic_Studio): kiểm tra storyboard trước render.
- [Anima prompting guidebook](https://civitai.com/articles/35368): thứ tự tag, camera/lighting/background block, ngân sách token. Hợp đồng dự án: `docs/novel2anima/ANIMA_TAG_PROMPT.md`.
