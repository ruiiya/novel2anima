# PR-09 - Release gate

## Trạng thái hiện tại

**NOT_READY**. Gate chạy được toàn bộ E2E/restore/rollback/benchmark, nhưng
P8 vẫn còn legacy transitional nên không được signoff.

| Check | Kết quả |
|---|---|
| Migration ledger | pass, checksum khớp |
| P8 disposition | **fail**: còn `character_profile.*_json`, `shot.character_id/shot_spec_json`, `act_publication` |
| DB-only E2E | pass: project → participant → outfit → spec → prompt → render → QA → replay |
| Backup/restore | pass: counts, FKs, prompt SHA, asset SHA |
| Rollback drill | pass: counts khớp snapshot nguồn |
| Benchmark | pass: 1.2M tag, lookup 0.0007s, FK 37.6s |
| Signed ledger | pass: content hash (hoặc HMAC nếu có key) |

Report: [`evidence/pr-09/release_gate.json`](../../evidence/pr-09/release_gate.json).

## Chạy gate

```powershell
python scripts\release\release_gate.py `
  --db db\backup\pr-01\staging_live.db `
  --report evidence\pr-09\release_gate.json
```

Mặc định từ chối DB live. Chỉ dùng `--allow-live` sau khi có approval cutover.

Exit code:

- `0`: READY
- `3`: NOT_READY (có blocker)
- khác: lỗi thực thi

## Gate bắt buộc

1. `quick_check=ok`, `foreign_key_check=[]`.
2. Mọi file migration đã apply và checksum khớp.
3. 23/23 legacy table có disposition; không còn cột authoritative trùng.
4. E2E DB-only: không đọc file plan/prompt/review.
5. Render asset SHA khớp bytes; replay prompt/render chỉ từ DB.
6. Backup/restore: counts, prompt SHA, asset SHA khớp.
7. Rollback: khôi phục snapshot trước cutover, counts khớp.
8. Không có external source bắt buộc chưa xử lý.
9. Benchmark ghi nhận; vượt ngưỡng phải có quyết định.
10. Ledger có signature.

## Blocker hiện tại

`P8_LEGACY_DISPOSITION`:

- `character_profile.identity_json/outfit_json`
- `shot.character_id/shot_spec_json`
- `act_publication`
- projections `shot_finding`, `shot_state`, observations

Không được drop khi reader/writer cũ còn dùng. Đây là lý do PR-09 chưa READY.

## Signoff

Chỉ owner ký sau khi:

- blocker trên bằng 0 hoặc có disposition được chấp nhận;
- backup/restore drill trên DB có render thật;
- rollback drill trên bản cutover thật;
- E2E Anima/workflow thật, không chỉ stub bytes;
- performance backup/RTO nằm trong ngưỡng vận hành.
