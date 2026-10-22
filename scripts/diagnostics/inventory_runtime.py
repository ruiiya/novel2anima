#!/usr/bin/env python3
"""Read-only inventory of the Novel2Anima working tree.

This is the PR-00 baseline tool. It never writes inside the source tree; the
caller supplies an output path. It records every candidate runtime file with
size, UTC mtime, optional SHA-256, git tracked/ignored state and a coarse
category so that later import PRs can prove file -> DB coverage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "node_modules",
}
SKIP_PREFIXES = ("db/backup",)
HASH_BLOCK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(HASH_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        check=False,
    )


def git_meta(root: Path) -> dict:
    meta = {"available": False, "branch": None, "head": None, "dirty": None}
    probe = _git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return meta
    meta["available"] = True
    meta["branch"] = _git(root, "branch", "--show-current").stdout.strip() or None
    meta["head"] = _git(root, "rev-parse", "HEAD").stdout.strip() or None
    status = _git(root, "status", "--porcelain")
    meta["dirty"] = bool(status.stdout.strip())
    return meta


def git_tracked_and_ignored(root: Path, paths: Iterable[str]) -> tuple[set[str], set[str]]:
    tracked: set[str] = set()
    ignored: set[str] = set()
    probe = _git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return tracked, ignored
    listed = _git(root, "ls-files", "-z")
    if listed.returncode == 0:
        tracked = {p for p in listed.stdout.split("\0") if p}
    candidates = [p for p in paths if p]
    if candidates:
        checked = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--stdin", "-z"],
            input=("\0".join(candidates) + "\0").encode("utf-8", "surrogateescape"),
            capture_output=True,
            check=False,
        )
        if checked.returncode in (0, 1):
            ignored = {
                line
                for line in checked.stdout.decode("utf-8", "surrogateescape").split("\0")
                if line
            }
    return tracked, ignored


def _should_skip_dir(rel_dir: str, name: str) -> bool:
    if name in DEFAULT_SKIP_DIRS:
        return True
    rel = f"{rel_dir}/{name}".strip("/")
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in SKIP_PREFIXES)


def _category(rel_path: str) -> str:
    top = rel_path.split("/", 1)[0]
    if top in {"etl", "src", "scripts", "tests", "sql", "skills", "docs", "evidence"}:
        return "source_docs"
    if top == "data":
        return "external_data"
    if top == "prompts":
        return "legacy_prompt_export"
    if top in {"act_tools", "765"}:
        return "workspace"
    if top == "db":
        return "database"
    if top == "dist":
        return "bundle_archive"
    return "other"


def _role(rel_path: str) -> str:
    if rel_path == "db/novel_anima.db":
        return "canonical_database"
    if rel_path.startswith("db/") and rel_path.endswith(("-wal", "-shm")):
        return "sqlite_sidecar"
    if rel_path.startswith("data/plans/"):
        return "legacy_plan_input"
    if rel_path.startswith("prompts/"):
        return "legacy_prompt_export"
    if rel_path.startswith("data/reviews/"):
        return "legacy_llm_review"
    if rel_path.startswith("data/characters/"):
        return "character_seed_or_report"
    if rel_path.startswith("data/wardrobe/"):
        return "wardrobe_setting"
    if rel_path.startswith("data/sources/"):
        return "catalog_source_cache"
    if rel_path.startswith("765/"):
        return "untracked_story_workspace"
    if rel_path.startswith("act_tools/"):
        return "local_act_workspace"
    if rel_path.startswith("docs/v4/"):
        return "v4_design_pack"
    if rel_path.startswith("docs/audits/"):
        return "audit_archive"
    if rel_path.startswith("etl/"):
        return "legacy_etl_source"
    if rel_path.startswith("tests/"):
        return "test"
    if rel_path.startswith("sql/"):
        return "schema_or_migration"
    if rel_path.startswith("skills/"):
        return "agent_skill"
    return "other"


def _summarize(files: list[dict]) -> dict:
    by_category: dict[str, dict] = {}
    by_top_dir: dict[str, dict] = {}
    by_extension: dict[str, dict] = {}
    for item in files:
        for bucket, key in (
            (by_category, item["category"]),
            (by_top_dir, item["relative_path"].split("/", 1)[0]),
            (by_extension, item["extension"] or "<none>"),
        ):
            entry = bucket.setdefault(key, {"files": 0, "bytes": 0})
            entry["files"] += 1
            entry["bytes"] += item["size_bytes"]
    largest = sorted(files, key=lambda item: item["size_bytes"], reverse=True)[:20]
    empty = [item["relative_path"] for item in files if item["size_bytes"] == 0]
    return {
        "by_category": dict(sorted(by_category.items())),
        "by_top_dir": dict(sorted(by_top_dir.items())),
        "by_extension": dict(sorted(by_extension.items(), key=lambda pair: pair[1]["bytes"], reverse=True)),
        "largest_files": [
            {
                "relative_path": item["relative_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in largest
        ],
        "empty_files": empty,
        "tracked_files": sum(1 for item in files if item["git_tracked"]),
        "untracked_files": sum(1 for item in files if item["git_tracked"] is False),
        "ignored_files": sum(1 for item in files if item["git_ignored"] is True),
    }


def build_inventory(root: Path, sha256: bool = False, include_git: bool = True) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--root must be a directory")
    paths: list[tuple[Path, str]] = []
    skipped: list[dict] = []
    symlinks: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        kept = []
        for name in sorted(dirnames):
            if _should_skip_dir(rel_dir, name):
                skipped.append({"relative_path": f"{rel_dir}/{name}".strip("/"), "reason": "configured_skip"})
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = current / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                symlinks.append(rel)
                continue
            if not path.is_file():
                continue
            paths.append((path, rel))

    rel_paths = [rel for _, rel in paths]
    tracked, ignored = git_tracked_and_ignored(root, rel_paths) if include_git else (set(), set())
    files: list[dict] = []
    for path, rel in paths:
        stat = path.stat()
        files.append(
            {
                "relative_path": rel,
                "size_bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "sha256": sha256_file(path) if sha256 else None,
                "category": _category(rel),
                "role": _role(rel),
                "extension": path.suffix.lower(),
                "is_empty": stat.st_size == 0,
                "git_tracked": rel in tracked if include_git else None,
                "git_ignored": rel in ignored if include_git else None,
            }
        )

    files.sort(key=lambda item: item["relative_path"])
    summary = _summarize(files)
    return {
        "root": str(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256_enabled": bool(sha256),
        "include_git": bool(include_git),
        "git": git_meta(root) if include_git else {"available": False},
        "file_count": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "summary": summary,
        "skipped_directories": skipped,
        "skipped_symlinks": symlinks,
        "files": files,
        "note": (
            "Read-only inventory. It does not prove that a file was imported; "
            "SHA-256 and the mapping ledger are the evidence used by later PRs."
        ),
    }


def write_csv(path: Path, inventory: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "relative_path",
        "category",
        "role",
        "size_bytes",
        "sha256",
        "git_tracked",
        "git_ignored",
        "is_empty",
        "mtime_utc",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in inventory["files"]:
            writer.writerow({field: item.get(field) for field in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root (read-only)")
    parser.add_argument("--output", required=True, help="JSON report path outside the source tree")
    parser.add_argument("--csv", help="Optional flat CSV manifest")
    parser.add_argument("--sha256", action="store_true", help="Hash every file (slower, recommended for baseline)")
    parser.add_argument("--no-git", action="store_true", help="Skip git tracked/ignored classification")
    args = parser.parse_args(argv)

    root = Path(args.root)
    report_path = Path(args.output).resolve()
    if root.resolve() == report_path:
        parser.error("output must not be the root")
    inventory = build_inventory(root, sha256=args.sha256, include_git=not args.no_git)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.csv:
        write_csv(Path(args.csv).resolve(), inventory)
    print(
        "Inventory:",
        inventory["file_count"],
        "files,",
        inventory["total_bytes"],
        "bytes, tracked=",
        inventory["summary"]["tracked_files"],
        "untracked=",
        inventory["summary"]["untracked_files"],
        "ignored=",
        inventory["summary"]["ignored_files"],
    )
    print("Report:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
