#!/usr/bin/env python3
"""Audit corpus pages without deleting source scans.

When Gemini is configured this script can be extended with the vision adapter;
without it every row remains explicitly ``unavailable``.  Conservative filename
signals identify obvious quarantine candidates but never silently move files.
"""
from __future__ import annotations
import argparse, csv, json, re, shutil
from pathlib import Path
from datetime import datetime, timezone

IMAGE_EXT={'.jpg','.jpeg','.png','.webp','.tif','.tiff','.pdf','.idml'}
POLLUTION=("certificate","certificat","diccionario","manualzilla","ecinepramaan","bedienungsanleitung","dictionary")

def audit(root: Path, *, apply: bool=False) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    quarantine=root/'_quarantine'; quarantine.mkdir(exist_ok=True)
    rows=[]
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXT and '_quarantine' not in p.parts):
        lowered=path.name.casefold()
        obvious=any(token in lowered for token in POLLUTION)
        if obvious:
            status='rejected'; reason='filename signal suggests non-editorial scan'
        else:
            status='unavailable'; reason='Gemini vision audit is not configured; page was not auto-approved'
        target=''
        if apply and status=='rejected':
            target=str(quarantine/path.relative_to(root)); Path(target).parent.mkdir(parents=True,exist_ok=True); shutil.move(str(path),target)
        rows.append({'path':str(path),'status':status,'is_newspaper_or_magazine_page':None,'title_matches_folder':'unknown','reason':reason,'quarantine_path':target})
    report={'created_at':datetime.now(timezone.utc).isoformat(),'root':str(root.resolve()),'checked':len(rows),'rejected':sum(r['status']=='rejected' for r in rows),'unavailable':sum(r['status']=='unavailable' for r in rows),'rows':rows}
    (root/'CORPUS_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (root/'CORPUS_AUDIT.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','status','is_newspaper_or_magazine_page','title_matches_folder','reason','quarantine_path']); writer.writeheader(); writer.writerows(rows)
    return report

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('root',nargs='?',default='corpus',type=Path); parser.add_argument('--apply',action='store_true'); args=parser.parse_args(); report=audit(args.root,apply=args.apply); print(json.dumps({k:report[k] for k in ('checked','rejected','unavailable')},ensure_ascii=False))
if __name__=='__main__': main()
