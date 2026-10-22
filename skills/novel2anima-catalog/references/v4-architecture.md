# V4.1 architecture redirect

This file is intentionally small. Do not treat any earlier V1 snapshot as live runtime
schema or as proof that a database is populated.

Canonical sources:

- [`docs/architecture/PIPELINE_EXECUTION_CONTROL.md`](../../../docs/architecture/PIPELINE_EXECUTION_CONTROL.md)
- [`docs/v4/P8_LEGACY_DISPOSITION.md`](../../../docs/v4/P8_LEGACY_DISPOSITION.md)
- [`docs/contracts/SKILL_RUNTIME_CONTRACTS.md`](../../../docs/contracts/SKILL_RUNTIME_CONTRACTS.md)
- Actual `sqlite_master` and `PRAGMA table_info(...)` on the target DB.

The catalog skill owns read-only retrieval semantics. Runtime story state is SQLite;
files are import/export/preview only. The story path cannot run catalog ETL.
