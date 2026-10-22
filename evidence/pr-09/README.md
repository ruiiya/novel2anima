# PR-09 evidence

Status: **NOT_READY** (release gate ran; P8 blocker remains).

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
| P8 disposition | **fail** (transitional columns remain) |
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
- canonical name lookup: 0.0007 s.
- `foreign_key_check`: 37.6 s.
- backup + restore two layers: 10.2 s.

## Limitations

- E2E image is 20 synthetic bytes, not an Anima render.
- Staging DB has 0 project rows; E2E seeds a temporary copy.
- P8 columns still authoritative in old readers/writers:
  `character_profile.identity_json/outfit_json`,
  `shot.character_id/shot_spec_json`,
  `act_publication`,
  QA projections.
- Therefore `verify_p8_disposition.py --require-clean` exits `3`.
- No pilot/cutover was performed. PR-09 is not signed off.

## Reproduce

```powershell
python scripts\release\release_gate.py `
  --db db\backup\pr-01\staging_live.db `
  --report evidence\pr-09\release_gate.json
```

Exit code `3` is expected until the P8 blocker is removed.
