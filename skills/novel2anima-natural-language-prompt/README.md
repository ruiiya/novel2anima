# Novel2Anima Natural Language Prompt — V4.1

Optional read/transform/validate skill for stage `08_natural_prompt`. This skill does not
start stories, execute ETL, write the database or create canonical prompt TXT/JSONL files.
The application may persist a validated proposal as a new `shot_prompt_revision`.

See `SKILL.md`, `references/integration.md`, and the canonical root documentation:
`docs/architecture/PIPELINE_EXECUTION_CONTROL.md` and
`docs/contracts/SKILL_RUNTIME_CONTRACTS.md`. For runtime mode and approvals, consult the
backend; do not infer enabled stages from files in the repository.
