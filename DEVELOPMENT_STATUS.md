# VibeCleaner v0.2 개발 현황

최종 갱신: 2026-07-13  
워크트리: `vibecleaner-v0.2`  
브랜치: `codex/v0.2-phase-a`

이 문서는 Issue #1 보강 계획과 v0.2 작업에서 실제로 구현·검증된 항목을 기록한다. 완료로 표시된 내용은 코드와 테스트로 확인된 범위만 포함한다.

## 1. 최초 계획

Issue #1의 방향은 다음 원칙을 전제로 했다.

- 기존 제품의 약 70~80%는 유지하고, 성능·품질을 결정하는 pipeline core 20~30%만 교체한다.
- Tauri 셸, React workspace, Canvas/Inspector, 프로젝트·페이지·말풍선 모델, 저장·내보내기 기능은 유지한다.
- Pipeline Scheduler v2, 분리된 detection/OCR stage, resource-aware DAG executor, adaptive quality router, checkpoint/cache, 품질 검증은 신규 core로 구현한다.
- 도메인 로직은 FastAPI/React/Tauri에 의존하지 않는다.
- 엔진은 안정된 port/interface와 provider manifest 뒤에 둔다.
- 프로젝트 파일/API는 버전과 migration 정책을 갖는다.
- v1을 유지한 채 v2를 shadow 검증하고, feature flag·benchmark·fallback을 거쳐 v2를 기본화한다.

## 2. 유지 영역과 교체 영역

### 유지

- Tauri 데스크톱 셸
- React 작업 공간 및 Canvas/Inspector
- 프로젝트·페이지·말풍선 도메인 모델
- 기존 저장·내보내기 흐름
- 기존 엔진 구현체와 legacy adapter

### v2 교체·신규 구현

- Pipeline v1/v2 rollout coordinator
- dependency DAG executor
- CPU/GPU/I/O/Network resource admission
- detection/OCR 독립 실행 port
- provider manifest/catalog 및 동시성 제한
- adaptive quality scoring/replan
- checkpoint, resume, retry, shadow benchmark

## 3. 완료된 구현

### 아키텍처·호환성

- 전체 재작성 금지 및 Strangler migration 원칙 문서화
- settings/project schema version 및 migration/rejection 정책 추가
- atomic settings/project save와 unknown field 보존
- 기존 v1 characterization fixture 및 회귀 테스트 추가
- 기존 API·프로젝트 파일 호환성을 깨지 않는 v2 opt-in 경로 확보

### Provider 확장 계약

- typed `ProviderManifest`, `ProviderRegistry`, lifecycle adapter 추가
- detection/OCR/translation/inpainting catalog 등록
- provider config field를 manifest에서 동적으로 렌더링
- 모델·enum·secret·조건부 field를 UI hardcoding 없이 처리
- manifest에 capability, resource class, max concurrency, queue capacity 선언

### Pipeline v2 실행

- `PipelineRollout`으로 v1/v2 primary 및 shadow 선택
- dependency cycle/missing dependency 검증
- v2 DAG stage resource 및 retry 정책
- OCR 이후 translation과 inpainting 병렬 실행
- provider별 bounded queue 및 resource semaphore
- provider manifest에 model profile별 quality/latency/resource metadata 추가
- quality score 미달 시 catalog 기반 compatible model 자동 선택
- checkpoint manifest 저장과 hydrated artifact resume
- page-level checkpoint payload 저장·복원 및 quality replan 상태 통합
- page translation 완료 시 checkpoint manifest/payload 자동 정리
- stage별 partial retry 및 backoff

### Detection/OCR 분리

- legacy `detect_and_ocr` 유지
- v2에서 `detect_only → ocr_only` 실행
- legacy detection/OCR adapter와 DTO 경계 추가
- detection confidence 부족 시 high precision model로 1회 replan
- OCR quality score 및 detection quality score 기록
- OCR quality 미달 시 cache를 우회한 enhanced preprocessing으로 1회 자동 retry

### 성능·안정성

- LaMa inpainting background warm-up
- inpainting bounded LRU result cache
- inpainting 결과 shape/dtype·target change·outside preservation 품질 검증
- inpainting 품질 미달 시 대체 engine과 확장 dilation profile로 1회 자동 replan
- heuristic line integral-image 경계 좌표 clamp 및 invalid inpainting 결과 fail-fast 검증
- RT-DETR ONNX detection에서 고신뢰 텍스트가 없을 때만 저신뢰 후보를 재검토하는 recall 보강
- OCR 전체 점수가 통과해도 빈 텍스트 블록만 확장 crop으로 개별 재시도
- 자동 말풍선 렌더링의 가독성 최소 폰트 하한(`11px`) 및 overflow 표시 보강
- Qt 자동 레이아웃·API·Pillow export의 폰트 단위를 실제 픽셀(`px`) 기준으로 통일
- 긴 문장 typesetting에서 구두점 고아 줄 억제 및 원본 bubble mask 재시도 경로 추가
- detection/OCR/inpainting/translation provider queue
- provider runtime metrics API
- rollout telemetry JSONL 저장 및 v2 primary failure/fallback 성공률 집계
- `/api/pipeline/telemetry` 운영 요약 endpoint 추가
- shadow context snapshot에서 `RLock` 등 runtime lock 제외
- shadow 실패가 primary 작업을 중단하지 않도록 보호
- v2 primary 실패 시 깨끗한 context에서 v1 fallback

### Benchmark·Rollout

- shadow JSONL benchmark 저장
- primary/shadow duration 및 stage duration 기록
- bubble count, OCR match, translation match, quality score 기록
- execution order 교대(primary-first/shadow-first)
- deterministic parallel scheduler speedup benchmark 추가
- rollout quality gate 스크립트 추가
- 장기 benchmark JSONL 집계 및 self-contained HTML dashboard 생성
- CI에서 benchmark summary/dashboard artifact 업로드 workflow 추가
- 신규 설치 기본값은 v2, 기존 명시 설정은 보존
- Advanced 설정 UI에서 v2/shadow 토글 제공

## 4. 검증 현황

현재 마지막 검증 기준:

- Python 전체 테스트: `177 passed`
- frontend build: 통과
- frontend Node 테스트: 통과
- parallel scheduler smoke benchmark: 약 `1.96x` speedup 확인
- 실제 shadow rollout gate: 10 sample, success/equivalence/OCR/translation 모두 `1.0`
- 실제 페이지 benchmark에서 v1/v2 artifact·bubble·OCR·translation 결과 일치 확인
- NVIDIA CUDA 환경에서 detection·LaMa ONNX 실추론 및 `CUDAExecutionProvider` 사용 확인
- CUDA 실추론 시 GPU 전력 사용량이 약 `48W`에서 `77W`로 증가하는 것을 확인
- 긴 번역문·좁은 말풍선 자동 배치 회귀 테스트 포함, 전체 `182 passed`

## 5. 남은 작업

현재 사용자가 없는 개발 단계이므로 v1 제거는 보류한다. v1 fallback과
backward compatibility 테스트는 유지하고, 실제 운영 기간이 생긴 뒤 다시 판단한다.

향후 운영 단계에서 재검토할 항목:

- 충분한 운영 기간 후 v1 제거 여부 결정 및 migration 공지
- v1 제거 전 프로젝트 파일/API backward compatibility 최종 검증

## 6. 현재 운영 권장 설정

일반 사용:

```json
{
  "pipeline_v2_enabled": true,
  "pipeline_v2_shadow": false
}
```

추가 검증:

```json
{
  "pipeline_v2_enabled": true,
  "pipeline_v2_shadow": true
}
```

shadow는 v1과 v2를 모두 실행하므로 검증 기간에만 사용한다. 결과는 Windows 기준 다음 파일에 저장된다.

```text
%APPDATA%\vibecleaner\pipeline_shadow_benchmark.jsonl
```

rollout gate 실행:

```powershell
.\venv\Scripts\python.exe scripts\evaluate_pipeline_rollout.py `
  "$env:APPDATA\vibecleaner\pipeline_shadow_benchmark.jsonl" `
  --minimum-samples 10
```

## 7. 최근 주요 커밋

- `d282fd8` GPU runtime verification benchmark
- `5b510f9` NVIDIA package DLL directory registration
- `994c5f9` ONNX Runtime CUDA DLL preload
- `4848a55` NVIDIA CUDA runtime setup documentation

- `220ee05` low-confidence detection replan
- `6434760` adaptive stage quality scoring
- `6e1dc4a` new install v2 default and v1 fallback
- `0da6430` parallel stage timing correction
- `599e379` parallel scheduler regression benchmark
- `133c6c8` independent v2 stage parallel execution
- `03c3ab0` manifest-driven provider queue policy
- `4a311cc` actual detection/OCR split in v2
