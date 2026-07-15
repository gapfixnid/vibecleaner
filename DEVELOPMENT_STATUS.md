# VibeCleaner v0.2 개발 backlog

최종 갱신: 2026-07-15
브랜치: `codex/v0.2-phase-a`

이 문서는 완료 이력 대신, 현재 기준으로 품질을 더 높일 수 있는 작업만 관리한다.
v2 페이지 번역 파이프라인은 현재 유일한 실행 경로이며, 아래 항목은 기능 장애를
고치는 필수 작업이라기보다 정확도·가시성·사용성·운영성을 높이기 위한 개선 과제다.

현재는 외부 배포 사용자와 보존해야 할 운영 데이터가 없는 개발 단계다. 따라서
backward compatibility는 기본 요구사항으로 취급하지 않는다. 프로젝트·설정·API·
telemetry schema를 개선하는 데 필요하면 기존 형식을 깨고 바로 변경할 수 있으며,
기존 데이터 migration이나 호환 adapter를 추가하는 작업은 하지 않는다. 로컬 개발
데이터는 schema 변경 시 초기화·재생성할 수 있다.

## 현재 기준선

- Python 전체 테스트: 로컬 `180 passed`
- 최신 CI 재실행: 통과
- 오류가 발생했던 다중 페이지 이미지 재번역: 통과
- CUDA 환경에서 detection·LaMa ONNX의 `CUDAExecutionProvider` 실추론 확인
- v1 페이지 번역 runtime, rollout, shadow, fallback 경로: 제거 완료
- 프로젝트/API/일반 엔진 호환성 adapter: 개발 편의를 위해 남아 있으나 제거 가능

우선순위는 `P0`가 다음 작업, `P1`이 그 다음 품질 개선, `P2`가 구조 정리와
장기 개선이다. 한 번에 모든 항목을 구현하지 않고 각 항목의 완료 기준을 통과한
뒤 다음 항목으로 넘어간다.

## 1. 백엔드 개선 과제

### P0 — 검출 누락 평가 체계와 recall 개선

현재 실제 이미지에서 검출 누락을 보완하는 로직은 있지만, 재현 가능한 평가
기준이 부족하다.

- [완료] 이미지 없이도 실행되는 box-only detection evaluator와 IoU one-to-one matching 구현
- [완료] baseline·miss·false positive·split·merge를 포함한 합성 corpus와 benchmark 명령 추가
- [완료] 로컬 이미지 corpus에서 RT-DETR box·raw confidence를 수집하는 capture 명령 추가
- [완료] 정답 좌표를 마우스로 작성하는 임시 local annotation 도구 추가
- 합법적으로 사용할 수 있는 샘플과 합성 이미지로 실제 모델 검출 평가 corpus 확장
- 다음 유형을 별도 그룹으로 관리
  - 겹친 말풍선과 긴 문장
  - 말풍선 안에 일부만 고신뢰로 검출된 경우
  - 세로쓰기·작은 글자·저대비 글자
  - 효과음, 패널 경계, 인물 윤곽을 텍스트로 잘못 잡는 경우
- [완료] bubble recall/precision, split/merge 오류를 benchmark로 집계
- text-region recall, OCR 비어 있음 비율과 실제 licensed 모델 prediction 수집을 benchmark에 연결
- [완료] RT-DETR 모델 원시 confidence를 TextBlock·BubbleAnalysis·API `detection_confidence`까지 전달
- heuristic/layout confidence와 모델 confidence를 분리
- 기존 debug overlay를 평가 corpus 결과와 연결해 누락·오검출 원인을 확인

완료 기준: 샘플 그룹별 지표와 대표 실패 이미지가 자동으로 남고, 수정 전후
recall 변화가 한 명령으로 비교된다.

### P0 — telemetry를 v2 운영 정보로 정리 (진행 중)

v1 제거 후에도 `pipeline_rollout_telemetry.jsonl`과 fallback/shadow 필드가 남아
있어 현재 runtime 의미와 문서가 어긋난다.

- [완료] telemetry schema를 v2 실행 정보에 맞게 재정의
- [완료] primary/fallback/shadow 명칭과 사용하지 않는 집계 필드 정리
- [완료] 기존 rollout telemetry JSONL 호환 reader는 추가하지 않고 새 파일로 시작
- [완료] 파일명과 API 응답을 일반적인 pipeline telemetry 명칭으로 정리
- [완료] stage별 duration, quality score, replan, 오류를 집계
- [남음] 파일 크기 제한·기간별 보관·손상 행 처리 정책 추가
- [남음] stage retry·cache hit/miss·실제 GPU provider 집계 추가

완료 기준: `/api/pipeline/telemetry`가 현재 v2 실행 의미만 반환하고, 오래된
telemetry 파일을 읽어도 앱 시작이나 endpoint가 실패하지 않는다.

### P1 — OCR 품질과 provenance 강화

- [완료] OCR 엔진이 제공하는 원시 confidence를 `ocr_confidence`로 블록 단위 보존
  하고 분석 confidence와 구분
- 문자 영역을 읽기 순서와 줄 단위로 안정적으로 그룹핑
- [완료] 원본 언어·엔진·전처리·retry 여부와 cache 전후 hit/miss를 결과 provenance에 기록
- [완료] 일본어·영어·한국어별 OCR 품질 threshold 적용
- [완료] 언어·엔진별 OCR preprocessing profile 적용; 사용자가 지정한 값은 profile보다 우선
- [완료] OCR cache hit/miss와 cache 용량을 확인할 수 있는 진단 정보 추가
- 오래된 cache, 손상된 SQLite, 설정 변경 cache의 정리·복구 테스트 추가

완료 기준: 사용자가 특정 말풍선의 OCR 결과가 왜 채택됐는지 엔진·confidence·retry
정보로 설명할 수 있고, cache 오염이 전체 번역을 중단시키지 않는다.

### P1 — 렌더링·인페인팅 최종 품질 검증 강화

- 최종 raster를 기준으로 텍스트 clipping, bubble 밖 침범, 최소 폰트, 줄 겹침,
  원본 글자 잔여를 자동 검사
- overflow가 남으면 자동 재배치·폰트 조정 후에도 실패한 항목만 `needs_review`로 표시
- 좁거나 비정형인 말풍선에서 padding, 줄 간격, 세로쓰기 방향을 shape mask에 맞춰 조정
- 인페인팅 결과의 경계 이음새와 원본 보존 영역을 정량 검사
- 번역문이 지나치게 길어졌을 때 렌더링 실패와 번역 품질 문제를 구분해 기록

완료 기준: export 직전에 사람이 확인해야 하는 bubble 목록이 생성되고, 정상
항목은 기존 결과와 시각적으로 동일하게 유지된다.

### P1 — GPU/CPU runtime 진단과 설치 안정성

- detection, OCR, inpainting별 실제 execution provider를 startup health 정보로 노출
- CUDA/cuDNN DLL 누락, 버전 불일치, GPU 미지원의 원인을 사용자용 메시지로 변환
- CUDA 초기화 실패 시 CPU fallback을 명시적으로 기록하되 반복되는 ONNX 경고는 정리
- CPU/GPU별 대표 이미지 처리 시간과 메모리 사용량 benchmark 추가
- 모델 다운로드 상태, checksum, 필요한 runtime 버전을 한 번에 점검하는 진단 명령 제공

완료 기준: 사용자가 로그를 해석하지 않아도 현재 각 stage가 CPU인지 GPU인지와
설치 문제의 다음 조치를 확인할 수 있다.

### P1 — job/API lifecycle 안정화

- job 상태·오류·취소 응답을 공통 schema로 통일
- 앱 재시작·backend 재연결·중복 요청 중에도 stale job이 UI를 잠그지 않도록 정리
- 페이지별 batch 결과를 API에서 성공/실패/취소/미실행으로 구분
- 취소가 현재 stage와 provider queue에 실제로 전파되는지 검증
- 완료된 job과 오래된 artifact/checkpoint의 보관 기간 및 정리 정책 추가

완료 기준: 중단·재시작·부분 실패 후에도 재실행 대상과 결과가 일관되며, 같은
요청을 실수로 두 번 보내도 결과가 중복 생성되지 않는다.

### P2 — 불필요한 adapter와 provider 구조 정리

- `legacy_adapter`로 표시된 provider를 목록화하고 실제 의존 관계 확인
- typed port로 직접 이전 가능한 adapter부터 단계적으로 제거
- 프로젝트/API/엔진의 구형 형식을 위한 adapter를 우선 제거
- schema 변경이 필요하면 모델·API·frontend 타입·fixture를 한 번에 갱신
- adapter 제거 후 contract fixture와 sidecar packaging 검증을 통과

이 작업은 v1 페이지 번역 runtime을 다시 도입하지 않는다. 호환성을 위해 남겨 둔
구형 wrapper를 유지하는 것보다 현재 v2 구조를 단순하게 만드는 것을 우선한다.

## 2. 프론트엔드 개선 과제

### P0 — 검토 대상 작업 큐

현재는 canvas overlay와 선택된 bubble inspector를 통해 문제를 확인한다. 이를
페이지 전체 검토 흐름으로 확장한다.

- 빈 OCR, 짧은 OCR, 낮은 detection confidence, translation warning, layout overflow를
  한 목록으로 집계
- 항목을 클릭하면 해당 페이지와 bubble로 이동
- `다음 문제`, `이전 문제`, `이 항목만 재검출`, `이 항목만 재번역` 제공
- overlay 색상·confidence·상태의 범례를 표시
- 사용자가 확인한 항목은 reviewed 상태로 기록

완료 기준: 전체 페이지를 확대해 하나씩 찾지 않아도 문제가 있는 bubble만 순서대로
검토할 수 있다.

### P0 — 다중 페이지 진행 상태와 부분 재시도 UI

- batch 작업에서 페이지별 queued/running/succeeded/failed/cancelled 상태 표시
- 전체 진행률과 현재 처리 페이지를 분리해 표시
- 실패한 페이지만 다시 번역하는 action 제공
- 취소 후 이미 완료된 페이지와 미실행 페이지를 명확히 구분
- backend 재연결 시 현재 job을 재조회하고 stale progress를 초기화

완료 기준: 다중 페이지 작업이 중간에 멈춰도 사용자가 어느 페이지가 완료됐고
어느 페이지만 재실행하면 되는지 즉시 알 수 있다.

### P1 — 자동 typesetting 조정 UI

- 자동 배치 결과의 실제 font size, 줄 수, overflow, layout confidence 표시
- 최소 폰트 이하로 축소된 경우 경고하고 사람이 직접 조정할 수 있게 함
- 자동 맞춤 잠금/해제, padding, 줄 간격, writing mode override 제공
- 변경 전후 canvas preview를 유지하고 export 전 overflow 항목을 다시 알림
- 긴 문장을 무조건 작은 글씨로 줄이는 대신 줄바꿈·배치·문장 축약 선택지를 분리

완료 기준: 사용자가 숫자만 보지 않고 canvas에서 읽기 어려운 결과를 즉시 식별하고,
자동 layout을 보정할 수 있다.

### P1 — canvas 편집 생산성

- bubble 이동·크기·텍스트·스타일 변경에 대한 undo/redo history 확장
- 다중 선택 bubble의 공통 스타일·정렬·padding 일괄 적용
- 고배율에서 좌표 정밀도를 높이는 snapping과 선택 핸들 개선
- zoom/pan/selection/삭제/다음 문제 이동의 keyboard shortcut 안내
- 페이지 전환 시 선택 상태와 viewport 복원 정책 정리

완료 기준: 반복적인 수동 보정이 키보드와 일괄 조작으로 가능하고, 실수한 편집을
안전하게 되돌릴 수 있다.

### P1 — Settings 정보 구조와 runtime 상태 표시

- 기본 설정과 고급 provider/runtime 설정을 분리
- 선택한 provider에 필요한 field만 노출하고 사용하지 않는 설정은 접기
- 원본 언어와 번역 언어의 허용 조합을 선택창에서 일관되게 제한
- GPU provider, 모델 다운로드, 현재 engine 상태를 설정 화면에서 확인
- 설정 저장 실패·provider 연결 실패·모델 누락을 field 단위로 표시

완료 기준: 사용자가 설정 파일이나 backend 로그를 직접 열지 않고도 현재 번역
구성을 이해하고 문제를 수정할 수 있다.

### P1 — 오류 복구·접근성·국제화

- backend 재시작·이미지 로드 실패·export 실패에 재시도와 복구 경로 제공
- modal, select, canvas toolbar, inspector의 focus 이동과 Escape 동작 통일
- 모든 버튼·tooltip·상태 메시지에 한국어/영어 번역 키 적용
- 오류 메시지에 내부 예외 대신 사용자 행동 중심의 설명 제공
- 작은 창, 고배율 DPI, 긴 번역문에서도 sidebar/inspector가 잘리지 않도록 visual regression 추가

완료 기준: 마우스만 사용하지 않아도 주요 작업이 가능하고, 한국어·영어 UI에서
번역되지 않은 내부 key나 잘린 핵심 컨트롤이 없다.

### P2 — 테스트와 시각 회귀 자동화

- 현재 Node mapper/i18n 테스트를 실제 주요 사용자 흐름 테스트로 확장
- import → detect → OCR → translate → edit → export의 최소 smoke flow 자동화
- 저신뢰 검토 큐, 부분 실패 batch, backend 재연결, overflow layout을 fixture로 고정
- 주요 canvas/inspector/settings 화면의 light/dark 및 DPI visual regression 추가

완료 기준: UI 리팩터링 후에도 핵심 작업 흐름과 문제 표시가 자동으로 검증된다.

## 3. 권장 진행 순서

1. Backend P0: telemetry 정리와 검출 평가 corpus 구축
2. Backend P1: OCR provenance·cache 진단 및 최종 raster 품질 검증
3. Frontend P0: 검토 대상 큐와 다중 페이지 부분 재시도 UI
4. Frontend P1: typesetting 조정 UI와 canvas 편집 history
5. GPU 진단, job lifecycle, 설정 구조, visual regression 순서로 확장

검출 평가 corpus와 검토 큐를 먼저 만드는 이유는 이후 OCR·렌더링 개선이 실제로
누락률과 수동 수정 시간을 줄였는지 측정할 수 있게 하기 위해서다.

## 4. 변경 시 지켜야 할 기준

- v1 페이지 번역 runtime을 다시 도입하지 않는다.
- 프로젝트/API/schema 호환성은 release blocker가 아니다. 형식을 바꿀 때는 관련 코드·
  타입·fixture를 함께 갱신하고 필요하면 로컬 개발 데이터를 초기화한다.
- 개선은 합법적으로 사용할 수 있는 샘플 또는 합성 fixture로 재현 가능해야 한다.
- backend stage 변경에는 Python 회귀 테스트와 최소 한 개의 실제 흐름 검증을 추가한다.
- frontend 변경에는 Node 테스트 또는 visual/smoke 테스트를 추가한다.
- CUDA는 선택 기능으로 유지하고 CPU 환경에서도 기본 workflow가 동작해야 한다.
- 품질 개선이 처리 시간을 크게 늘릴 경우 CPU/GPU benchmark와 함께 판단한다.
