#!/usr/bin/env python3
"""Validate one MOSS positive natural-language prompt and optional sidecar hash.

Only format and integrity are checked; content fidelity requires human/LLM QA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# One camera angle only. These families are mutually exclusive when rendered,
# so a prompt mixing two of them gets an averaged, wrong angle.
ANGLE_FAMILIES = {
    'overhead': re.compile(r"(?i)\b(top[- ]down|overhead|bird'?s[- ]eye)\b"),
    'low': re.compile(r"(?i)\b(low[- ]angle|worm'?s[- ]eye)\b"),
    'high': re.compile(r"(?i)\bhigh[- ]angle\b"),
    'eye_level': re.compile(r"(?i)\beye[- ]level\b"),
}
BBOX_RE = re.compile(r"\[\s*-?\d+\s*,\s*-?\d+\s*,")


def validate(text: str) -> list[str]:
    errors = []
    if not text.strip():
        errors.append('EMPTY_PROMPT')
    if text.lstrip().startswith('```') or text.rstrip().endswith('```'):
        errors.append('CODE_FENCE')
    if '\x00' in text:
        errors.append('NUL_CHARACTER')
    if len([name for name, rx in ANGLE_FAMILIES.items() if rx.search(text)]) > 1:
        errors.append('CAMERA_CONFLICT')
    if BBOX_RE.search(text):
        errors.append('BBOX_IN_PROMPT')
    if text.lstrip().startswith('{'):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(data, dict):
                errors.append('JSON_OBJECT_NOT_NATURAL_PROMPT')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--manifest', type=Path)
    args = p.parse_args()
    data = args.file.read_bytes()
    text = data.decode('utf-8')
    issues = validate(text)
    digest = hashlib.sha256(data).hexdigest()
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        if digest != manifest.get('prompt_sha256'):
            issues.append('SHA256_MISMATCH')
        if manifest.get('format') != 'moss-natural-v1':
            issues.append('FORMAT_MISMATCH')
    print(json.dumps({'status': 'PASS' if not issues else 'BLOCKED',
                      'prompt_sha256': digest, 'issues': issues}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
