"""Reviewed paraphrases with claim-level page references; no generated repair claims."""
import copy
import json
import re
import question_scope as scope
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'data/service-guides.json').read_text(encoding='utf-8'))

def build_guide(part,question,records,manuals):
    spec=DATA['parts'].get(part['id'])
    manifest=next((m for m in manuals if m['id']==part['docId']),None)
    if not spec or not manifest or DATA['sourceHashes'].get(part['docId'])!=manifest.get('sha256'):
        return None
    spec=copy.deepcopy(spec)
    generic_failure=scope.malfunction(question)
    label='작동 이상 · 기본 점검·정비 안내' if generic_failure else '점검·정비 안내'
    for variant in spec.get('variants',[]):
        if any(word in question for word in variant['keywords']):
            label=variant['label']
            for field in ('checks','steps','warnings'):
                if field in variant:spec[field]=variant[field]
            if variant.get('figure'):spec['figures']=[f for f in spec['figures'] if f['placement']=='description']+[variant['figure']]
            break
    available={r['page']:r for r in records if r['docId']==part['docId']}
    used=set()
    def claim(item):
        text,pages=item
        if not pages or any(p not in available for p in pages):raise ValueError('Missing source')
        used.update(pages)
        return {'text':text,'refs':[f"{part['docId']}:{p}" for p in pages]}
    try:
        description=claim(spec['description'])
        sections=[{'id':'checks','title':'먼저 확인할 사항','ordered':False,'items':[claim(c) for c in spec['checks']]},
                  {'id':'steps','title':'점검 후 필요 시 진행하는 정비 작업' if generic_failure else '정비 작업 흐름','ordered':True,'items':[claim(c) for c in spec['steps']]}]
        warnings=[claim(c) for c in spec['warnings']]
        if re.search(r'토크|토오크|규정값|전압|몇\s*(V|볼트|Nm)',question,re.I):
            warnings.insert(0,{'text':'질문한 수치는 이 요약에서 단정하지 않습니다. 측정 조건·부위·차량 사양이 맞는 원문 규정값을 확인하세요.','refs':[]})
        figures=[]
        for fig in spec['figures']:
            if fig['page'] not in available:raise ValueError('Missing figure page')
            used.add(fig['page'])
            figures.append({'id':fig['id'],'caption':fig['caption'],'placement':fig['placement'],
                            'ref':f"{part['docId']}:{fig['page']}",'src':f"/manual-figure?part={part['id']}&figure={fig['id']}"})
    except ValueError:
        return None
    follow_up=part['questions']
    if re.search(r'교환|교체|정기|탈거|장착',question):
        follow_up=[q for q in follow_up if not re.search(r'어떤 (작업|증상)',q)]
    guide={'title':part['name'],'subtitle':label,'question':question,'description':description,'sections':sections,
           'warnings':warnings,'figures':figures,'followUp':follow_up,
           'scope':'교범을 검토해 쉽게 풀어 쓴 작업 개요입니다. 고장 확정이나 모든 선행·후속 작업을 포함한 전체 절차가 아닙니다.'}
    if generic_failure:
        guide['scope']='상세 증상 없이 참고할 수 있는 기본 점검과 관련 정비 개요입니다. 원인을 확정한 진단이 아니며 탈거·교환은 점검 후 필요성이 확인된 경우에 진행합니다.'
    plain=part['name']+' · '+label+'\n'+description['text']+'\n\n'
    if generic_failure:
        plain+=guide['scope']+'\n\n'
    plain+='\n\n'.join(s['title']+'\n'+'\n'.join(f"{i+1}. {c['text']}" for i,c in enumerate(s['items'])) for s in sections)
    plain+='\n\n주의사항\n'+'\n'.join(c['text'] for c in warnings)
    return guide,plain,[available[p] for p in sorted(used)]

def figure_spec(part_id,figure_id):
    spec=DATA['parts'].get(part_id,{})
    figures=list(spec.get('figures',[]))
    figures.extend(v['figure'] for v in spec.get('variants',[]) if v.get('figure'))
    return next((f for f in figures if f['id']==figure_id),None)
