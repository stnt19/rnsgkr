"""Local, dependency-free document assistant. Python 3.10+."""
import json
import os
import re
from urllib.parse import urlparse, parse_qs
import maintenance
import official_info
import part_matching
import question_scope as scope
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def answer(question, history=None, part_id=None):
    followup = bool(re.fullmatch(scope.FOLLOWUP, question))
    previous = next((m['content'] for m in reversed(history or []) if m.get('role') == 'user'), '')
    request = previous if followup else question
    if re.search(scope.OFF_TOPIC, question, re.I) or re.search(scope.OFF_TOPIC, request, re.I):
        return scope.refusal('out-of-scope')
    part = maintenance.infer_part(request)
    correction = None
    if not part:
        resolved = part_matching.resolve(request, maintenance.PARTS)
        correction = resolved['match']
        if correction:
            part = correction['part']
            request = correction['normalizedQuestion']
        elif resolved['candidates']:
            candidates = [{'id': p['id'], 'name': p['name']} for p in resolved['candidates']]
            return {'answer': '부품을 하나로 특정하기 어렵습니다. ' + ', '.join(p['name'] for p in candidates) + ' 중 어느 부품인지 이름을 포함해 다시 질문해 주세요.',
                    'sources': [], 'mode': 'scope', 'reason': 'ambiguous-part', 'candidates': candidates}
    if part_id:
        if part and part['id'] != part_id:
            return scope.refusal('missing-evidence')
        part = maintenance.find_part(part_id)
    official = official_info.answer(previous if followup else question) if not part else None
    if official:
        return official
    if part:
        if not scope.supported(part, request):
            return scope.refusal('missing-evidence')
        result = maintenance.answer_manual(request, part['id'])
        if correction:
            result['partMatch'] = {k: correction[k] for k in ('inputName', 'matchedName', 'normalizedQuestion')}
            result['partMatch']['partId'] = part['id']
            message = f"부품명 ‘{correction['inputName']}’을(를) ‘{part['name']}’으로 해석했습니다."
            result['notice'] = message + ' ' + (result.get('notice') or '')
        return result
    if re.fullmatch(r'(안녕|안녕하세요|반가워|안녕하십니까)[!?.~\s]*', question):
        return {'answer':'안녕하세요. 렉스턴 스포츠 2023의 부품 설명·점검·정비 방법과 검토된 제작사 공식 가격 정보를 안내합니다. 무엇이 궁금하신가요?', 'sources':[], 'mode':'document'}
    return scope.refusal('missing-evidence' if re.search(scope.VEHICLE, question) else 'out-of-scope')

class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, mime='application/json; charset=utf-8'):
        raw = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict,list)) else data
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        if path == '/api/parts':
            return self.send(200, {'parts':maintenance.PARTS,'indexedPages':len(maintenance.RECORDS)})
        if path == '/api/manuals':
            return self.send(200, maintenance.public_manuals())
        if path == '/api/part':
            part = maintenance.find_part(params.get('id',[''])[0])
            return self.send(200,maintenance.part_detail(part)) if part else self.send(404,{'error':'등록되지 않은 부품입니다.'})
        if path == '/manual-figure':
            try:
                return self.send(200,maintenance.render_figure(params.get('part',[''])[0],params.get('figure',[''])[0]),'image/png')
            except (ValueError,TypeError):
                return self.send(404,{'error':'해당 교범 그림을 사용할 수 없습니다. 원문 페이지를 확인해 주세요.'})
            except (ImportError,OSError):
                return self.send(503,{'error':'그림을 불러오지 못했습니다. 로컬 원본과 패키지를 확인해 주세요.'})
        if path == '/manual-page':
            try:
                return self.send(200,maintenance.render_page(params.get('doc',[''])[0],int(params.get('page',['0'])[0])),'image/png')
            except (ValueError,TypeError):
                return self.send(404,{'error':'페이지를 찾을 수 없습니다.'})
            except ImportError:
                return self.send(503,{'error':'원문 렌더링에는 requirements.txt 패키지가 필요합니다.'})
        if path == '/document' and 'doc' in params:
            doc = next((d for d in maintenance.MANUALS if d['id']==params['doc'][0]),None)
            if not doc or not Path(doc['path']).is_file():
                return self.send(404,{'error':'로컬 원본을 찾을 수 없습니다.'})
            return self.send(200,Path(doc['path']).read_bytes(),'application/pdf')
        if path == '/api/status':
            return self.send(200, {'officialSources':len(official_info.sources())})
        if path == '/api/official-sources':
            return self.send(200, official_info.sources())
        files = {'/':('web/index.html','text/html; charset=utf-8'),'/style.css':('web/style.css','text/css; charset=utf-8'),'/app.js':('web/app.js','text/javascript; charset=utf-8'),'/guides.css':('web/guides.css','text/css; charset=utf-8')}
        if path not in files:
            return self.send(404, {'error':'찾을 수 없습니다.'})
        filename, mime = files[path]
        file = ROOT/filename
        if not file.exists():
            return self.send(404, {'error':'요청한 파일을 찾을 수 없습니다.'})
        return self.send(200,file.read_bytes(),mime)

    def do_POST(self):
        if self.path != '/api/chat':
            return self.send(404, {'error':'찾을 수 없습니다.'})
        # Only same-origin browser writes are accepted; never enable wildcard CORS.
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.send(403, {'error':'허용되지 않은 요청입니다.'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 24000:
                return self.send(413, {'error':'요청이 너무 큽니다.'})
            data = json.loads(self.rfile.read(length))
            question = data.get('question')
            if not isinstance(question,str) or not 1 <= len(question.strip()) <= 2000:
                return self.send(400, {'error':'질문을 1~2,000자로 입력해 주세요.'})
            history = data.get('history',[])
            if not isinstance(history,list) or len(history)>12 or any(not isinstance(m,dict) or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str) or len(m['content'])>4000 for m in history):
                return self.send(400, {'error':'대화 형식이 올바르지 않습니다.'})
            part_id = data.get('partId')
            if part_id is not None and (not isinstance(part_id,str) or not maintenance.find_part(part_id)):
                return self.send(400,{'error':'등록되지 않은 부품입니다.'})
            return self.send(200, answer(question.strip(),history,part_id))
        except (ValueError,TypeError,AttributeError):
            return self.send(400, {'error':'요청 형식을 확인해 주세요.'})

if __name__ == '__main__':
    port = int(os.getenv('PORT','8000'))
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
