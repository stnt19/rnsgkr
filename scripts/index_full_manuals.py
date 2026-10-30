"""Extract every page; retain wiring as image-only and catalogs as references.

Uses the existing local manifest produced by import_manuals.py. Registry ranges
are only applied to the exact reviewed PDF fingerprint.
"""
import hashlib
import json
import re
from pathlib import Path
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]


def main():
    manuals=json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8'))
    parts=json.loads((ROOT/'data/parts.json').read_text(encoding='utf-8'))
    full=[]; records=[]
    for doc in manuals:
        fingerprint=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
        if fingerprint != doc['sha256']:
            raise ValueError('PDF changed; review registry before importing: '+doc['id'])
        pdf=pdfium.PdfDocument(doc['path'])
        doc['scope']='배선도 원문 확인 전용 · 문자 인코딩 문제로 자동 답변 제외' if doc['id']=='wiring' else '부품 구성·품번 원문 참고 · 연식/옵션 호환 자동 확정 제외' if doc['id']=='catalog' else '전체 텍스트 검색 · 상세 정비 안내와 원문 참고 안내 구분'
        for i in range(len(pdf)):
            page=pdf[i]; tp=page.get_textpage()
            text=tp.get_text_range().replace('\r','').replace('\x00','').strip()
            tp.close(); page.close()
            full.append({'docId':doc['id'],'page':i+1,'text':text,'lines':[l.strip() for l in text.splitlines() if l.strip()]})
            if doc['id']=='wiring' or len(text)<35:continue
            linked=[]
            for p in parts:
                locations=p.get('locations',[])
                valid_locations=[l for l in locations if l['docId']==doc['id'] and l['sourceHash']==fingerprint]
                if any(l['start']<=i+1<=l['end'] for l in valid_locations) or (valid_locations and p['docId']==doc['id'] and p.get('diagnosis') and p['diagnosis'][0]<=i+1<=p['diagnosis'][1]):
                    linked.append(p['id'])
            label=re.search(r'(?m)^\s*(\d{2}[-–]\d+)\s*$',text)
            records.append({'docId':doc['id'],'document':doc['name'],'page':i+1,'printedPage':label[1] if label else None,'text':text,'partIds':linked,'kind':'catalog' if doc['id']=='catalog' else 'manual','sourceHash':fingerprint})
        pdf.close()
        print(doc['id'],doc['pages'],flush=True)
    for name,value in [('manuals.local.json',manuals),('manual-fulltext.local.json',full),('manual-index.local.json',{'parts':parts,'pages':records}),('manual-import-report.local.json',{'documents':len(manuals),'totalPages':sum(d['pages'] for d in manuals),'indexedPages':len(records),'parts':len(parts)})]:
        (ROOT/'data'/name).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    print('Indexed',len(records),'pages; registered',len(parts),'topics')


if __name__=='__main__':main()
