# Phạm vi xác minh và chưa xác minh

| Claim | Nguồn | Trạng thái |
|---|---|---|
| 80 file source, 29 Python `etl` | zipped source + 2026-10-22 map | Count checked in source snapshot |
| 23 DB entities | SQL schema/stats | Snapshot only; includes FTS virtual |
| 18 groups of external paths | V2 mapping | Known patterns; not exhaustive on local checkout |
| 1,208,773 tags, 7,099 shots, ~361MB DB | `evidence/db_stats_snapshot_20261022.json` | User snapshot; not live SQL query |
| 75 pass + 1 skip legacy tests | `evidence/legacy_tests_20261022.txt` | Source bundle test baseline |
| 9 V3 schema tests | `tests/test_schema_v3.py` | In-memory SQLite; structural only |
| 005+006 production ready | No | **DRAFT ONLY**, need full migration runner/SQL review |
| External data fully imported | No | Missing raw runtime paths + DB |
| Source refactored | No | Skeleton + plan only |
| DB finalized and duplicate tables retired | No | P8 planned after parity |
| LLM instructions ready | No | 33 zero-byte file placeholders only |
| Anima render integration actually operating | Not demonstrated in source bundle | Mark as planned/integration gap |

No generated file in V4 should be represented as proof of successful production migration. Test only on DB copies, never use `stage_migration_copy.py` as a drop-in production migration.
