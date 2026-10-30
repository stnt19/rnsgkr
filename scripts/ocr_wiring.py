"""Local Korean Windows OCR, resumable per-page cache, original PDF unchanged."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1]
VERSION=1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pages',help='Comma-separated pilot pages; omit for all pages')
    args=parser.parse_args()
    doc=next(d for d in json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8')) if d['id']=='wiring')
    fingerprint=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
    if fingerprint!=doc['sha256']:raise ValueError('Original PDF fingerprint changed')
    cache=ROOT/'data/manual-cache/wiring-ocr'/fingerprint/f'v{VERSION}'
    cache.mkdir(parents=True,exist_ok=True)
    pages=sorted(set(map(int,args.pages.split(',')))) if args.pages else list(range(1,doc['pages']+1))
    if not all(1<=n<=doc['pages'] for n in pages):raise ValueError('Invalid page')
    pdf=pdfium.PdfDocument(doc['path'])
    for offset in range(0,len(pages),24):
        jobs=[]
        for n in pages[offset:offset+24]:
            output=cache/f'{n}.json'
            if output.exists():continue
            page=pdf[n-1];bitmap=page.render(scale=min(3,2500/max(page.get_size())))
            image=bitmap.to_pil();path=cache/f'{n}.png';image.save(path)
            image.close();bitmap.close();page.close()
            jobs.append({'page':n,'image':str(path),'output':str(output)})
        if jobs:
            batch=cache/'batch.json';batch.write_text(json.dumps(jobs),encoding='utf-8')
            subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/ocr_windows.ps1'),'-Batch',str(batch)],check=True,stdout=subprocess.DEVNULL)
            for job in jobs:Path(job['image']).unlink()
        print(f'OCR {min(offset+24,len(pages))}/{len(pages)}',flush=True)
    pdf.close()
    records=[]
    for n in pages:
        row=json.loads((cache/f'{n}.json').read_text(encoding='utf-8'))
        if row['page']!=n or row['engine']!='Windows.Media.Ocr':raise ValueError('Invalid OCR cache')
        records.append(row)
    result={'version':VERSION,'sourceHash':fingerprint,'docId':'wiring','engine':'Windows.Media.Ocr','language':'ko',
            'createdAt':datetime.now(timezone.utc).isoformat(),'totalPages':doc['pages'],'complete':len(records)==doc['pages'],'pages':records}
    output=ROOT/'data'/('wiring-ocr.local.json' if result['complete'] else 'wiring-ocr-pilot.local.json')
    output.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print(f'Saved {len(records)} OCR pages',flush=True)


if __name__=='__main__':main()
