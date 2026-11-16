#!/usr/bin/env python3
"""Cài Novel2Anima skills và SQLite starter vào project độc lập.

Mặc định không ghi đè. --upgrade backup từng file sẽ thay thế; CONTENT_POLICY.md
đang tồn tại luôn được bảo toàn để người quản lý tự quyết định merge.
"""
from __future__ import annotations
import argparse
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def digest(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',type=Path,required=True)
    p.add_argument('--mode',choices=('claude','portable','both'),default='claude')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--upgrade',action='store_true',help='Backup từng file cũ rồi cập nhật; không ghi đè policy đang có')
    args=p.parse_args()
    target=args.target.expanduser().resolve()
    dirs=[]
    if args.mode in ('claude','both'):dirs.append(target/'.claude'/'skills')
    if args.mode in ('portable','both'):dirs.append(target/'skills')
    pairs=[]
    for dest in dirs:
        for skill in sorted((ROOT/'skills').iterdir()):
            if skill.is_dir():pairs.append((skill,dest/skill.name))
    pairs.extend([
        (ROOT/'docs'/'novel2anima',target/'docs'/'novel2anima'),
        (ROOT/'tools'/'novel2anima',target/'tools'/'novel2anima'),
        (ROOT/'examples',target/'examples'/'novel2anima'),
        (ROOT/'database',target/'database'),
    ])
    conflicts=[str(dst) for src,dst in pairs if dst.exists()]
    if conflicts and not args.upgrade:
        raise SystemExit('BLOCKED: destination exists, use --upgrade to backup/reconcile or install in clean project:\n'+'\n'.join(conflicts))
    backup_root=target/'.novel2anima-installer-backup'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    copied=skipped=backed_up=0
    for src,dst in pairs:
        for file in sorted(src.rglob('*')):
            if not file.is_file() or '__pycache__' in file.parts or file.suffix=='.pyc':continue
            rel=file.relative_to(src)
            # Raw licensed downloads and the runtime DB are local artifacts, not
            # part of the installable skill package.
            if src.name=='database' and rel.parts and rel.parts[0] in ('imports','data'):
                if file.name!='.gitkeep':continue
            dest=dst/rel
            if dest.exists() and file.name=='CONTENT_POLICY.md' and dest.parent.name=='novel2anima':
                print(f'PRESERVE (manual merge): {dest}')
                skipped+=1
                continue
            if dest.exists() and digest(file)==digest(dest):
                skipped+=1
                continue
            if dest.exists():
                b=backup_root/dest.relative_to(target)
                print(f'BACKUP: {dest} -> {b}')
                if not args.dry_run:
                    b.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(dest,b)
                backed_up+=1
            print(f'{"PLAN" if args.dry_run else "COPY"}: {file.relative_to(ROOT)} -> {dest}')
            if not args.dry_run:
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,dest)
            copied+=1
    # Retire only known V2 files. Always back them up before removal.
    if args.upgrade:
        obsolete = [
            Path('docs/novel2anima/MOSS_LAYOUT.md'),
            Path('tools/novel2anima/compile_layout.py'),
            Path('tools/novel2anima/flatten_layout.py'),
            Path('examples/novel2anima/layout_draft.example.json'),
            Path('examples/novel2anima/layout_prompt.example.json'),
            Path('examples/novel2anima/layout_manifest.example.json'),
        ]
        if args.mode in ('claude','both'):
            obsolete.append(Path('.claude/skills/novel2anima-layout-planner/SKILL.md'))
        if args.mode in ('portable','both'):
            obsolete.append(Path('skills/novel2anima-layout-planner/SKILL.md'))
        for rel in obsolete:
            old = target / rel
            if not old.is_file():
                continue
            backup = backup_root / rel
            print(f'{"PLAN RETIRE" if args.dry_run else "RETIRE"}: {old} -> {backup}')
            if not args.dry_run:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, backup)
                old.unlink()
                if old.parent.name == 'novel2anima-layout-planner' and not any(old.parent.iterdir()):
                    old.parent.rmdir()
            backed_up += 1
    print(f'{"DRY-RUN" if args.dry_run else "PASS"}: copied={copied}, backup={backed_up}, skipped={skipped}')

if __name__=='__main__':main()
