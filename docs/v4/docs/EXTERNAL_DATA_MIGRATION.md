# Migration dữ liệu JSON/TXT/ảnh ngoài DB — DB-first V4

## Phạm vi

18 nhóm nguồn tại `mappings/EXTERNAL_DATA_18_GROUPS.csv`, trong đó có `data/plans/*.json`, `prompts/*.txt`/`.neg.txt`, `data/reviews/*.json`, `data/wardrobe/colour_{choice,cue}.json`, `data/characters/*.json`, `act_specs/*.json`, `etl/sources.json`, `data/sources/manifest.json`, `db/import_report.json`, ảnh/reference và các file import sources. Có thể còn file chưa được Git track: cần chạy inventory trên máy thật; snapshot ZIP không đủ khẳng định complete.

## Quy trình chung cho mỗi loại

1. **Inventory read-only**: path tương đối, kích thước, mtime UTC, sha256 (nếu chọn), type, owner, importer, git ignored/tracked; ghi manifest ngoài folder nguồn. Không follow symlink mặc định.
2. **Classify**: canonical business input, import source, source-controlled fixture, historical export, temp/cache, secret/config. Never import secrets from provider accounts/tokens/passwords into LLM request logs.
3. **Parse+validate**: UTF-8/JSON schema/source version, reference IDs, shot count, prompt block order, document revision. Không đủ bằng chứng → manual review; không sinh dữ liệu thay.
4. **Create import_batch**: provenance+file asset/hash+import status (`imported`,`duplicate`,`blocked`,`skipped_by_policy`) và lý do. Idempotency by content SHA and stable source ID.
5. **Insert in DB transaction**: document→normalized project/act/shot; roster→character identity; outfit rules→outfit revision/setting; prompt→shot_prompt_revision; review→llm_run/qa; assets→asset_blob+generation_asset. FK and ownership enforced.
6. **Reconcile**: row count, normalized content, bytes/sha, number of duplicated or unidentified shot blocks, status/revisions, unknown actor/target, assets. Preserve source file until reconciliation signed.
7. **Switch read-path**: code reads DB; filesystem only for explicit import/export/cache. Remove legacy fs inputs in staging copy to test DB-only restore.
8. **Retire legacy**: archive/backup and remove only after P9 signoff, never automatically in import code.

## File-specific pitfalls

- Plan JSON may contain character refs via name; enforce stable IDs and no cross-project links.
- Prompt TXT splitting needs reliable `(act_id,shot_no)` pairing and positive/negative block counts; any mismatch is `BLOCKED`, not best-effort merge.
- Reviews `shot_finding` can be UPSERT; preserve full raw JSON in `llm_run`, map each run to immutable `qa_run` records; no overwrites.
- Colour rules precedence: explicit shot > explicit act > catalog selected underwear > heuristic. Store source/decision version; no silent default overrides.
- Source data files may be large: if strict DB-only reproducibility required, preserve raw bytes in `asset_blob` and measure DB growth. For upstream reproducible downloads a verified source digest+URL alone is **not equivalent** to actual bytes recoverable offline.
- Renders/anchors: dedup bytes by SHA-256 and MIME, verify `length`, persist references in DB; preserve generator temp copies as cache only. Measure backup/restore for full media size.
- Empty scaffold `.txt` are never imported as active prompt content; activation requires DB template record, nonempty text, validation and explicit approval.
- `sql/*`, tests, skills, README, source code are Git files by design — do not misclassify as data needing BLOB replication.

## Migration ledger (must implement in code during P4)

```
source_relative_path,source_sha256,source_bytes,classified_as,target_table,target_pk,parser_version,import_batch_id,status,exception,verified_sha256
```

Generated output should be SQL-backed ledger or a read-only report view of DB; CSV files can be used for operator review, not source-of-truth. Required proof: every inventory item is mapped `imported/duplicate/skipped_by_policy/blocked` and blockers addressed before cutover. Do not report a raw cache file skipped as migrated business data.
