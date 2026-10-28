"""Local detector adapter. Never downloads weights or saves camera frames."""
import base64
import importlib.util
import io
import json
import math
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
YOLO_PATH = os.getenv('YOLO_MODEL_PATH','').strip()
CLASS_MAP_PATH = os.getenv('VISION_CLASS_MAP','').strip()
LOCK = threading.Lock()
MODEL = None

def status(ollama_model=''):
    if YOLO_PATH:
        exists = Path(YOLO_PATH).is_file() and Path(YOLO_PATH).suffix.lower() == '.pt'
        installed = importlib.util.find_spec('ultralytics') is not None
        available = exists and installed
        message = ('YOLO 연속 탐지 · 모델 실행 및 인식률 검증 필요' if available else
                   'YOLO .pt 가중치 파일과 requirements-vision.txt 패키지를 확인해 주세요.')
        return {'backend':'yolo','configured':True,'available':available,'message':message,'intervalMs':500,'timeoutMs':30000}
    if ollama_model and 'cloud' not in ollama_model.lower():
        return {'backend':'ollama','configured':True,'available':True,
                'message':'로컬 비전 모델의 연속 프레임 분석 · 탐지 상자 미지원 · 속도는 추론 시간에 따라 달라집니다.',
                'intervalMs':2000,'timeoutMs':85000}
    return {'backend':'none','configured':False,'available':False,
            'message':'인식 모델 미설정 · 카메라 미리보기와 부품 직접 선택을 사용할 수 있습니다.',
            'intervalMs':1000,'timeoutMs':15000}

def decode_image(encoded):
    if not isinstance(encoded,str) or len(encoded)>2800000:
        raise ValueError('Invalid image')
    raw=base64.b64decode(encoded,validate=True)
    if len(raw)>2000000:
        raise ValueError('Image too large')
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in ('JPEG','PNG','WEBP') or image.width*image.height>16000000:
            raise ValueError('Unsupported image')
        image.load()
        return image.convert('RGB')

def normalize_detections(rows,names,parts,class_map=None):
    """Rows: normalized x1,y1,x2,y2,confidence,class index. No guessed class IDs."""
    known={p['id']:p for p in parts}; mapping=class_map or {}; detections=[]
    for row in rows:
        if len(row)!=6 or not all(math.isfinite(float(v)) for v in row):
            continue
        x1,y1,x2,y2,confidence,cls=map(float,row)
        label=names.get(int(cls),'') if isinstance(names,dict) else names[int(cls)] if 0<=int(cls)<len(names) else ''
        part_id=mapping.get(str(int(cls)),mapping.get(str(label),str(label)))
        if part_id not in known or not 0.5<=confidence<=1:
            continue
        x1,y1,x2,y2=[min(1,max(0,v)) for v in (x1,y1,x2,y2)]
        if x2<=x1 or y2<=y1:
            continue
        part=known[part_id]
        detections.append({'id':part_id,'name':part['name'],'score':round(confidence,4),'box':[x1,y1,x2,y2]})
    return sorted(detections,key=lambda d:d['score'],reverse=True)[:20]

def detect_yolo(encoded,parts):
    global MODEL
    info=status()
    if not info['available']:
        return 503,{'error':info['message'],'candidates':[],'detections':[]}
    try:
        image=decode_image(encoded)
    except Exception:
        return 400,{'error':'2MB 이하의 유효한 JPEG·PNG·WebP 프레임이 필요합니다.','candidates':[],'detections':[]}
    started=time.monotonic()
    try:
        if MODEL is None:
            from ultralytics import YOLO
            # Existing local .pt paths only; a missing model must never trigger a download.
            MODEL=YOLO(str(Path(YOLO_PATH).resolve()))
        mapping={}
        if CLASS_MAP_PATH:
            mapping=json.loads(Path(CLASS_MAP_PATH).read_text(encoding='utf-8'))
            if not isinstance(mapping,dict) or any(not isinstance(v,str) for v in mapping.values()):
                raise ValueError('Invalid class map')
        result=MODEL.predict(source=image,imgsz=640,conf=0.5,verbose=False,save=False,save_txt=False)[0]
        if result.boxes is None:
            raise ValueError('Detection weights required')
        rows=[list(xy)+[conf,cls] for xy,conf,cls in zip(result.boxes.xyxyn.cpu().tolist(),result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist())]
        detections=normalize_detections(rows,result.names,parts,mapping)
        candidates=[]; seen=set()
        for item in detections:
            if item['id'] not in seen:
                seen.add(item['id']);candidates.append({'id':item['id'],'name':item['name'],'score':item['score'],'reason':'모델의 탐지 결과 · 실제 부품과 대조해 확인하세요.'})
        return 200,{'backend':'yolo','detections':detections,'candidates':candidates[:3],
                    'needsConfirmation':True,'inferenceMs':round((time.monotonic()-started)*1000),
                    'notice':'탐지 점수는 정확도 보증이 아닙니다. 부품을 확인한 뒤 정비자료를 여세요.'}
    except Exception:
        return 502,{'error':'YOLO 실행에 실패했습니다. 탐지용 .pt 가중치와 클래스 매핑을 확인해 주세요.','candidates':[],'detections':[]}
    finally:
        image.close()
