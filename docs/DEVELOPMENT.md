# 구조·API

## 구성

| 파일 | 역할 |
| --- | --- |
| server.py | 입력 검증·교범/차량 가격/부품 가격 라우팅 |
| maintenance.py | 부품 추론·복수 항목·상세 안내/원문 참고·PDF 렌더링 |
| manual_search.py | 부품 범위 또는 전체 색인에서 검색하고 출처 발췌 제공 |
| part_matching.py | 이름 구간만 보정, 불명확한 후보 구분 |
| service_guides.py | 검토된 13종 상세 안내의 버전·페이지 근거 검사 |
| wiring_ocr.py | OCR 버전·원본 해시 검사, 글꼴 보정, 검토된 핀 맵과 원문 검색 |
| scripts/ocr_wiring.py, scripts/ocr_windows.ps1 | Windows 한국어 OCR·페이지별 재개 캐시 |
| scripts/check_wiring_glyphs.py | 내장·시스템 글꼴의 윤곽 일치 검사, 페이지 밖 숨은 텍스트 제외 |
| scripts/validate_wiring_ocr.py | 원본 대조 표본 76개 검증 보고서 |
| live_prices.py | 고정 KGM 공개 API·차종 U·품명/품번 조회·캐시 |
| part_prices.py | 검토된 저장 가격 및 공통 가격 출처 형식 |
| official_info.py | 검토된 차량 판매 가격 자료 |
| scripts/index_full_manuals.py | 전체 PDF 추출·해시 검사·색인 |
| scripts/review_manual_registry.py | 목차/본문/수동 대조 anchor로 목록 재생성 |
| web/app.js | 안내 구분·출처 모달·부품 목록 검색 |

## API

- `POST /api/chat`: question, history, 선택적 partId. 응답의 presentation은 `service-guide`, `manual-reference`, `wiring-reference`; 가격은 mode `official`.
- `GET /api/parts`: 부품·시스템 목록과 indexedPages.
- `GET /api/part?id=...`: 해당 부품의 연결 원문과 공통 주의사항.
- `GET /api/manuals`: 교범 목록·쪽수·가용 여부. 로컬 경로 제외.
- `GET /api/official-sources`: 검토된 저장 자료. 실시간 응답은 개별 채팅 출처에 포함.
- `GET /api/status`: 저장된 공식 자료 수.
- `GET /document?doc=...`, `/manual-page?doc=...&page=...`, `/manual-figure?part=...&figure=...`: 검증된 문서·페이지·그림 ID만 허용.

## 검색·가격의 경계

일반 설명·정비 요청은 기존 상세 안내를 우선하며, 그 외는 원문 참고로 연결합니다. 원문 참고는 검색어 기반 발췌이며 생성형 의미 추론이나 확정 진단이 아닙니다. 상세 안내와 원문 참고를 화면에 구분합니다. 출처가 없거나 버전이 다르면 내용을 만들어 내지 않습니다.

가격은 PDF 부품 추론보다 앞에서 처리하여 미등록 부품도 검색합니다. 검색어는 고정 호스트 API의 쿼리 값으로 인코딩합니다. 차종 U, 응답 코드, 품번·품명·양수 정수 금액, 요청 검색어와의 일치를 검사합니다. 복합 이름은 공식 품명의 단어 순서가 달라도 모든 단어가 일치해야 합니다. 좌우 요청은 끝의 좌/우 표기를 추가 확인합니다.

호출당 6초, 최대 3페이지·페이지당 20개·응답 크기 500KB 제한, 일치 후보 20개 표시, 15분 캐시입니다. 실패 응답은 캐시하지 않습니다. 캐시에는 실제 조회 시각이 유지됩니다. 네트워크 실패/검색 결과 없음은 검토된 저장 가격으로만 대체하며 저장 시점을 명시합니다. 차대번호별 호환, 공임, 배송비, 재고는 조회하지 않습니다.

전체 PDF/로컬 색인은 Git ignore 대상입니다. 테스트는 `python scripts/run_tests.py`로 외부 연결 없이 실행합니다.

배선·회로·핀 맵 요청은 정비 가이드보다 먼저 배선도 검색으로 보냅니다. 가격 요청은 기존 가격 경로를 우선합니다. `wiringReviewed`는 직접 검토한 요약의 사용 여부이며, 출처의 `textMethod`는 OCR/전체 텍스트 글꼴 대조/일부 문구 글꼴 대조를 구분합니다. 전체 텍스트 글꼴 대조도 도면의 연결 관계나 그림 안 숫자 검증을 뜻하지 않습니다. 원문 이미지와 OCR을 출처 모달에서 함께 확인합니다.
