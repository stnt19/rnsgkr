"""Register local PDFs and build a full searchable index. PDFs stay local."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pypdf import PdfReader
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    ('engine','3. 2023 렉스턴스포츠-엔진.pdf','엔진','부품·시스템 점검·탈거/장착 선별'),
    ('chassis','4. 2023 렉스턴스포츠-새시.pdf','새시','등록만: 구동·조향·제동은 이번 부품 범위에서 제외'),
    ('service-lower','5. 2023 렉스턴스포츠-정비지침서-하.pdf','정비지침서 하','등록만: BSD·에어백·오디오 등은 이번 범위에서 제외'),
    ('service-upper','6. 2023 렉스턴스포츠-정비지침서-상.pdf','정비지침서 상','헤드 램프·와이퍼·퓨즈 및 전기장치 주의사항 선별'),
    ('wiring','7. 2023 렉스턴스포츠-전기배선도.pdf','전기배선도','텍스트 글자 깨짐 확인: 자동 답변 제외, 원문 확인 전용'),
    ('catalog','8. 2023 렉스턴스포츠-부품카다로그.pdf','부품 카탈로그','대상 부품의 그룹 제목을 찾아 참조만 연결; 품번·옵션 자동 확정 안 함'),
    ('body-hvac','9. 2023 렉스턴스포츠-공조 및 바디.pdf','공조 및 바디','에어컨 필터·블로워 모터 선별'),
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    parts=json.loads((ROOT/'data/parts.json').read_text(encoding='utf-8'))
    manuals=[]; records=[]; catalog_refs={p['id']:[] for p in parts}
    for doc_id,filename,title,scope in SPECS:
        path=(args.directory/filename).resolve()
        if not path.is_file():
            raise SystemExit(f'Missing PDF: {path}')
        reader=PdfReader(path)
        # Fingerprints allow a later import to identify source changes.
        fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
        doc={'id':doc_id,'name':filename,'title':title,'path':str(path),'pages':len(reader.pages),'sha256':fingerprint,'scope':scope}
        manuals.append(doc)
        wanted=set()
        for part in parts:
            if part['docId']==doc_id:
                wanted.update(range(part['pages'][0],part['pages'][1]+1))
                if part['diagnosis']:
                    wanted.update(range(part['diagnosis'][0],part['diagnosis'][1]+1))
        # Preserve shared precautions along with the selected procedures.
        extra={'engine':[(13,17),(289,290),(363,363),(463,464),(503,504)], 'service-upper':[(135,137)]}
        for start,end in extra.get(doc_id,[]):
            wanted.update(range(start,end+1))
        for number in sorted(wanted):
            text=reader.pages[number-1].extract_text() or ''
            text=text.replace('\x00','').strip()
            if len(text)<35:
                continue
            label=re.search(r'(?m)^\s*(\d{2}[-–]\d+)\s*$',text)
            linked=[p['id'] for p in parts if p['docId']==doc_id and (p['pages'][0]<=number<=p['pages'][1] or (p['diagnosis'] and p['diagnosis'][0]<=number<=p['diagnosis'][1]))]
            records.append({'docId':doc_id,'document':filename,'page':number,'printedPage':label.group(1) if label else None,'text':text,'partIds':linked,'kind':'manual'})
        if doc_id=='catalog':
            pdf=pdfium.PdfDocument(str(path))
            for i in range(len(pdf)):
                page=pdf[i]; tp=page.get_textpage(); text=tp.get_text_range(); tp.close(); page.close()
                heading=' '.join(text.splitlines()[:3])
                compact=re.sub(r'\s+','',heading).lower()
                for part in parts:
                    names=[part['name']]+part['aliases']
                    if any(re.sub(r'\s+','',n).lower() in compact for n in names):
                        catalog_refs[part['id']].append({'docId':doc_id,'page':i+1,'title':heading[:150]})
            pdf.close()
        print(f'{doc_id}: {len(reader.pages)} pages; {len(wanted)} selected',flush=True)
    for part in parts:
        part['catalogRefs']=catalog_refs[part['id']]
    result={'vehicle':'렉스턴 스포츠 2023','parts':parts,'pages':records}
    out=ROOT/'data'
    # All generated files contain local paths or manual excerpts; Git ignores them.
    for name,value in [('manuals.local.json',manuals),('manual-index.local.json',result),('manual-import-report.local.json',{'documents':len(manuals),'totalPages':sum(d['pages'] for d in manuals),'selectedPages':len(records),'catalogMatches':{k:len(v) for k,v in catalog_refs.items()}})]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'selectedPages':len(records),'catalogMatches':{k:len(v) for k,v in catalog_refs.items()}},ensure_ascii=False),flush=True)
    from index_full_manuals import main as index_all
    index_all()

if __name__=='__main__':
    main()
