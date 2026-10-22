#!/usr/bin/env python3
"""Static validation of V4 unified pack (no DB access, no filesystem modifications)."""
import csv
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def check(ok,msg):
    if not ok:ERR.append(msg)

def read_rows(name):
    p=ROOT/'mappings'/name
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

r=read_rows('REPOSITORY_80_FILES.csv');t=read_rows('LEGACY_23_DB_TABLES.csv');e=read_rows('EXTERNAL_DATA_18_GROUPS.csv');m=read_rows('MASTER_MAPPING.csv')
for label,items,n in [('repository',r,80),('legacy DB',t,23),('external data',e,18),('unified',m,121)]:check(len(items)==n,f'{label}: expected {n}, got {len(items)}')
check(len(set((x['category'],x['legacy_path_or_table']) for x in m))==len(m),'duplicate unified mapping keys')
for cat,items in [('SOURCE_FILE',r),('LEGACY_DB_TABLE',t),('EXTERNAL_RUNTIME',e)]:
    check(sum(x['category']==cat for x in m)==len(items),f'{cat} master coverage mismatch')
stages=[p for p in (ROOT/'llm/prompts').iterdir() if p.is_dir()]
check(len(stages)==11,f'expected 11 stages, got {len(stages)}')
for stage in stages:
    for n in ('system.txt','task.txt','examples.txt'):
        f=stage/n;check(f.is_file() and f.stat().st_size==0,f'{f.relative_to(ROOT)} not present/zero-byte')
check(sum(1 for p in (ROOT/'llm/prompts').rglob('*.txt'))==33,'expected exactly 33 LLM txt')
for n in ('005_db_first_DRAFT.sql','006_normalization_DRAFT.sql'):
    check((ROOT/'sql/proposals'/n).is_file(),n+' draft missing')
check(not (ROOT/'sql/migrations').exists(),'proposals must not be in active migrations')
for p in (ROOT/'llm/schemas').glob('*.json'):
    try:json.loads(p.read_text(encoding='utf-8'))
    except (ValueError,OSError) as ex:ERR.append(f'{p}: {ex}')
print('V4 static validation: mapping=',len(m),' stages=',len(stages),' prompt_files=33')
if ERR:
    for x in ERR:print('FAIL:',x,file=sys.stderr)
    sys.exit(1)
print('PASS: V4 bundle integrity (does not prove runtime DB data migrated).')
