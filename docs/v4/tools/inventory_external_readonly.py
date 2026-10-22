#!/usr/bin/env python3
"""Read-only inventory of candidate legacy runtime files; optional SHA256 per file.
No writes to source tree; output JSON supplied via --output. Ignores symlinks and .git.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

PATTERNS = [
    'data/plans/**/*.json','data/reviews/**/*.json','data/wardrobe/**/*.json',
    'data/characters/**/*.json','data/sources/**/*','data/imports/**/*',
    'act_specs/**/*.json','act_tools/**/*','prompts/**/*.txt','prompts/**/*.neg.txt',
    'workspaces/**/*','db/import_report.json','db/*.db-wal','db/*.db-shm',
    'outputs/**/*','renders/**/*','references/**/*','etl/sources.json',
]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda:fh.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def build(root, do_hash=False):
    root=root.resolve(strict=True)
    if not root.is_dir():raise ValueError('--root must be a directory')
    selected={}
    for pattern in PATTERNS:
        for f in root.glob(pattern):
            if not f.is_file() or f.is_symlink() or '.git' in f.relative_to(root).parts:continue
            selected[f.relative_to(root).as_posix()]=f
    out=[]
    for rel,f in sorted(selected.items()):
        try:
            st=f.stat()
            item={'relative_path':rel,'size_bytes':st.st_size,'mtime_utc':datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat(), 'sha256':digest(f) if do_hash else None,'status':'INVENTORY_ONLY_NOT_MIGRATED'}
        except OSError as e:
            item={'relative_path':rel,'status':'READ_ERROR','error':str(e)}
        out.append(item)
    return {'root':str(root),'generated_at_utc':datetime.now(timezone.utc).isoformat(),'sha256_enabled':bool(do_hash), 'items':out,'file_count':len(out), 'total_bytes':sum(x.get('size_bytes',0) for x in out),'note':'Snapshot, not evidence of successful import or DB completeness. Globs are not exhaustive; review untracked paths.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--sha256',action='store_true',help='Hash all matching files (can be slow with large media)')
    args=p.parse_args()
    root=Path(args.root)
    report=Path(args.output).resolve()
    if root.resolve()==report or report.is_dir():p.error('invalid report path')
    if root.resolve() in report.parents:p.error('write report outside the source tree to avoid confusing source inventory')
    result=build(root,args.sha256)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Inventory:',result['file_count'],'files,',result['total_bytes'],'bytes. Report:',report)
