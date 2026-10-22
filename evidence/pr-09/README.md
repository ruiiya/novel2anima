# PR-09 evidence

Status: **READY** on staging (release gate exit `0`).

## Artifact

- [`release_gate.json`](release_gate.json): full JSON report + signed ledger.
- Database: `db/backup/pr-01/staging_live.db`
- Gate code: `scripts/release/release_gate.py`
- Guide: `docs/v4/BACKUP_RECOVERY.md`, `docs/v4/RELEASE_GATE.md`

## Results

| Check | Result |
|---|---|
| Source `quick_check` | ok |
| Migration ledger | all SQL files applied, checksums match |
| P8 disposition | pass (23/23; `act_publication` removed) |
| DB-only E2E | pass |
| Backup/restore | pass |
| Rollback drill | pass |
| Benchmark | pass |

E2E path: project + 2 characters + act + shot + participants + interaction
(actor=2, target=1) + outfit revisions + approved ShotSpec + approved prompt +
render BLOB + QA issue + prompt replay + render replay.

Verified:

- `prompt_sha` equals DB revision hash.
- `asset_blob` bytes hash equals `generation.image_sha256`.
- Replayed prompt and render read only from DB.
- Restored DB keeps counts, prompt SHA and asset SHA.
- Rollback restores the pre-cutover snapshot counts.

Staging benchmark:

- 1,208,773 tags on staging; 1,208,779 on the E2E copy (+6 synthetic).
- `tag_count`: 0.105 s.
- canonical name lookup: 0.000197 s.
- `foreign_key_check`: 29.36 s.
- backup + restore two layers: 10.2 s.

## Limitations

- E2E image is 20 synthetic bytes, not an Anima render.
- Staging DB has 0 project rows; E2E seeds a temporary copy.
- P8 transitional columns and `act_publication` are removed; legacy `etl/` shims are removed.
- `verify_p8_disposition.py --require-clean` exits `0`.
- QA/continuity projection tables remain as derived read models.
- No pilot/cutover or real Anima render was performed; production signoff still requires both.

## Reproduce

```powershell
python scripts\release\release_gate.py `
  --db db\backup\pr-01\staging_live.db `
  --report evidence\pr-09\release_gate.json
```

Exit code `0` means READY; `3` means a blocker remains.
