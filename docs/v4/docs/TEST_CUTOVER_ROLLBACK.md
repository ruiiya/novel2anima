# Test matrix, acceptance và rollback V4

## Coverage

| Gate | Validation | Không đạt khi |
|---|---|---|
| Source baseline | 75 pre-existing unittest pass + 1 documented skip; capture diff & dirty files | tests regress, untracked data lost |
| Migration dry-run | copied source DB, 005/006 draft adapted into versioned runner, `foreign_key_check`, `integrity_check`, SHA versions | DB original changed or checksum drift ignored |
| Catalog | all tag IDs/canonical names, alias/source links, FTS counts/retrieval parity | row loss / silent alias overwrite |
| Content | 31 project, 574 character, 77 act, 7099 shot snapshot **rechecked with DB runtime** | missing rows/invalid FK |
| External migration | 18 groups inventoried; SHA ledger and mapped destination; blocked ones explicit | file unaccounted, byte mismatch, wrong shot mapping |
| Action direction | solo/duo headpat male→female and inverse as separate tests | inversion or cross-project actor allowed |
| Outfit | two shots same outfit revision + anchor, explicit changes create new revision | drift hidden by prompt tag overlap |
| LLM | prompt template approval, revision pin, JSON schema, retry idempotency, invalid response rollback | blank stage calls model, duplicate work, illegal IDs |
| QA | repeated reviews append history, approved records immutable | overwrite current finding loses evidence |
| Render | seed/model/prompt/spec/outfit/reference pin; asset BLOB sha recoverable | needs image_path after restore or wrong prompt binding |
| DB-only recovery | restore DB + Git source into workspace **without** legacy plans/prompts/reviews | any runtime file not reconstructible |
| Performance | large catalog query plans, writer contention, full DB+assets backup/restore | latency/backup target violated |
| Final cleanup | 0 legacy reads/writes; unnecessary columns/tables retired after archival | V4 still depends on file/duplicate current states |

## Practical commands (inside extracted V4 dir)

```powershell
python .\tools\validate_v4_bundle.py
python -m unittest discover -s tests -v
python .\tools\audit_db_readonly.py --db D:\Novel2Anima\db\novel_anima.db --output .\db-audit.json
python .\tools\inventory_external_readonly.py --root D:\Novel2Anima --output .\runtime-inventory.json --sha256
python .\tools\stage_migration_copy.py --source D:\Novel2Anima\db\novel_anima.db --target D:\Novel2Anima\db\novel_anima_v4_staging.db --report .\stage-report.json
```

## Cutover: có chuyển lại được không?

**Pre-cutover:** freeze writers; maintenance window, backup by SQLite API including WAL-consistent transactions; restore rehearsal onto separate file; archive raw runtime inputs, commit code, collect queries/config and approved revision IDs; validate FKs/integrity and row counts.

**Switch:** application points to staged/migrated DB, marks new schema/app version, exercises smoke path (catalog→ShotSpec→prompt→render→QA), logs each run ID. Old DB stays read-only snapshot, no dual-write to two authorities.

**Rollback:** stop writes on new version; archive new-DB snapshot for forensic preservation; restore old DB and old app version atomically; re-enable old filesystem inputs as archived snapshot; reconcile all writes created since switch as separate migration, never overwrite old approved rows silently.

**Sign-off:** owner approves counts, blocked exceptions 0 or explicit accepted dispositions, restore time, render hash comparison, status/IDs, performance metrics and backward plan. If any unknown actor/target or lost outfit anchor exists, hold that project/act in NEEDS_REVIEW before all-project cutover.
