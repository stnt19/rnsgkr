"""Compare selected visible ground-truth phrases against raw and corrected OCR."""
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import wiring_ocr


def main():
    doc=next(d for d in json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8')) if d['id']=='wiring')
    checks=json.loads((ROOT/'data/wiring-ocr-checks.json').read_text(encoding='utf-8'))
    if checks['sourceHash']!=doc['sha256']:raise ValueError('Reviewed original changed')
    records=wiring_ocr.load_records(ROOT/'data',doc);by_page={r['page']:r for r in records}
    outcomes=[]
    for case in checks['cases']:
        record=by_page[case['page']]
        for field in ['phrases','critical']:
            for expected in case.get(field,[]):
                target=wiring_ocr.compact(expected)
                outcomes.append({'page':case['page'],'expected':expected,'critical':field=='critical',
                    'rawMatch':target in wiring_ocr.compact(record['ocrRawText']),
                    'correctedMatch':target in wiring_ocr.compact(record['text'])})
    report={'sourceHash':doc['sha256'],'reviewedPages':len(checks['cases']),
            'ocrProcessedPages':doc['pages'],'searchablePages':len(records),
            'methods':dict(Counter(r['textMethod'] for r in records)),
            'checks':len(outcomes),'rawMatches':sum(r['rawMatch'] for r in outcomes),
            'correctedMatches':sum(r['correctedMatch'] for r in outcomes),
            'criticalChecks':sum(r['critical'] for r in outcomes),
            'criticalPassed':sum(r['critical'] and r['correctedMatch'] for r in outcomes),
            'scope':checks['scope'],'results':outcomes}
    (ROOT/'data/wiring-ocr-validation.local.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','sourceHash')},ensure_ascii=False))
    failures=[r for r in outcomes if not r['correctedMatch']]
    if failures:print(json.dumps(failures,ensure_ascii=False));raise SystemExit(1)


if __name__=='__main__':main()
