---
name: migration-qa-verify
description: 마이그레이션 경계면 QA 검증 방법론. 계약 테스트(jobs 스키마 ↔ API 응답 ↔ 프론트 훅), 큐 왕복(Vercel 발행 ↔ Fly 소비), 3환경 동등성(로컬/Vercel/Fly), E2E 시나리오, 과거 이슈 퇴행 체크를 반복 실행. 점진적(incremental) QA 원칙.
---

# Migration QA Verify

`qa-migration-tester` 전용. 전체 완성 후 1회가 아닌, 모듈 완성 직후 즉시 실행.

## 원칙
1. **존재 확인 금지** — "파일 있다/200 떨어진다"로 만족하지 않음. shape·값 교차 비교
2. **증거 중심** — 응답 JSON·스크린샷·로그를 `_workspace/qa/evidence/{date}/`에 보존
3. **우선순위** — 사용자 가시 결과 > API 계약 > 내부 상태
4. **의심부터** — "깨질 가능성이 높은 곳"을 먼저 테스트

## 경계면 목록 (고위험 순)

| # | 경계면 | 양쪽 | 확인 방법 |
|---|-------|------|----------|
| 1 | jobs 스키마 ↔ API 응답 | Supabase ↔ Vercel Functions | SELECT 결과 JSON 스키마와 `/api/status`, `/api/result` 응답 필드 1:1 매칭 |
| 2 | API 응답 ↔ 프론트 훅 | Vercel Functions ↔ Vue 컴포넌트 | 실제 fetch 후 `typeof`/키 존재 검사 |
| 3 | pgmq 메시지 ↔ 워커 파싱 | Vercel 발행 ↔ Fly 워커 | 발행 payload와 `msg['message']` 역직렬화 결과 diff |
| 4 | Storage 경로 규칙 | 발행자 ↔ 소비자 | 버킷/키/확장자 컨벤션 일치 (한글 금지) |
| 5 | /app 핵심 로직 재사용 | local FastAPI ↔ Vercel ↔ Fly | 동일 PDF 입력 → 동일 추출 결과 (해시 비교) |
| 6 | signed URL 만료 | 발급 ↔ 클릭 시점 | 장시간 작업 후 다운로드 버튼 여전히 동작 |

## 계약 테스트 스크립트 (`_workspace/qa/tests/contract_test.py`)
```python
import httpx, json, jsonschema

def test_status_response_matches_job_schema():
    r = httpx.get(f'{BASE}/api/status/{JOB_ID}')
    r.raise_for_status()
    jsonschema.validate(r.json(), JOB_RESPONSE_SCHEMA)

JOB_RESPONSE_SCHEMA = {
  "type": "object",
  "required": ["id", "status", "created_at"],
  "properties": {
    "id": {"type": "string"},
    "status": {"enum": ["pending","extracting","awaiting_mapping","ocr_processing","completed","failed"]},
    "extracted_images": {"type": "array"},
    "mappings": {"type": "array"},
    "result_paths": {"type": "object"},
  }
}
```

## 큐 왕복 테스트 (`_workspace/qa/tests/queue_roundtrip.py`)
```python
# 1. Vercel 함수로 잡 생성
job = httpx.post(f'{BASE}/api/extract-mappings', json={'fileName':'test.pdf', 'size': 1024}).json()

# 2. Storage에 테스트 PDF 업로드
httpx.put(job['uploadUrl'], content=pdf_bytes, headers={'Content-Type': 'application/pdf'})

# 3. Fly 워커가 처리 완료될 때까지 상태 폴링 (최대 5분)
deadline = time.time() + 300
while time.time() < deadline:
    s = httpx.get(f'{BASE}/api/status/{job["jobId"]}').json()
    if s['status'] in ('awaiting_mapping', 'failed'):
        break
    time.sleep(3)

assert s['status'] == 'awaiting_mapping'
assert len(s['extracted_images']) > 0
```

## E2E 플로우 (Playwright)
전체 사용자 플로우:
1. 프론트 로드 → PDF 업로드 → jobId 발급
2. 매핑 추출 완료 → 매핑 편집 UI 동작
3. OCR 시작 → 완료 대기
4. 어노테이션 이미지 표시 확인 (signed URL)
5. 완성 PDF 다운로드 (한글 파일명 확인)
6. 재생성 PDF 다운로드 (일부 매핑 수정 후)
7. 작업 이력에서 과거 작업 조회

Playwright 스크립트 골자는 `_workspace/qa/tests/e2e.spec.js`로. MCP 서버(playwright)가 있으면 활용.

## 퇴행 체크리스트 (CLAUDE.md 과거 이슈)
| # | 이슈 | 확인 방법 |
|---|------|----------|
| 1 | 한글 파일명 403 | 한글 포함 파일명으로 업로드 + 완성 PDF 다운로드 성공 |
| 2 | 이미지 회전 좌표 | 회전된 도면이 포함된 PDF로 OCR 수행 후 라벨 좌표 정확 |
| 3 | DynamoDB 타입 (L/M/S) | 해당 없음 (Postgres로 전환) — 단, 이력 이전 시 변환 정확 |
| 4 | PDF 재생성 페이지 매핑 | drawing_020 → 페이지 20 위치 정확 |
| 5 | CORS (save-edited-image 등) | 같은 도메인 → 자동 해결. 다른 도메인 호출 없음 확인 |
| 6 | 이미지 모달 NaN | width/height 기본값 유지 |
| 7 | pypdfium2 버전 | 4.25.0로 고정되어 환경별 일관성 |

## 3환경 동등성 매트릭스
| 동일 입력 | 로컬 FastAPI | Vercel Functions | Fly Worker | 검증 |
|----------|-------------|------------------|-----------|------|
| 테스트 PDF 5개 | 추출 결과 | 트리거+대기 | 실제 처리 | 추출 이미지 수·해시 일치 |

## 진행 원칙
- `supabase-data-engineer`가 스키마 완료 → 즉시 계약 스키마 검증
- `vercel-api-engineer`가 핸들러 작성 → 즉시 계약 테스트
- `flyio-worker-engineer`가 워커 배포 → 즉시 큐 왕복 테스트
- `frontend-migration-engineer`가 config.js 수정 → 즉시 프리뷰 E2E
- 모든 모듈 통과 → 통합 E2E + 퇴행 체크

## 결과 리포팅 (`_workspace/qa/test_results/{date}.md`)
```markdown
# QA Round YYYY-MM-DD
## 요약
- 총 N 케이스, 통과 X, 실패 Y, 차단 Z

## 실패/블로커
### 1. [P1] status 응답에 `regenerated_pdf_path` 누락
- 경계면: jobs 스키마 ↔ /api/status 응답
- 재현: `curl /api/status/<id>` → `regenerated_pdf_path` 필드 없음
- 기대: null 또는 문자열
- 제안: vercel-api-engineer가 select 컬럼에 포함

## 통과
...

## 증거
- `evidence/20260417/status_response.json`
- `evidence/20260417/e2e_screenshots/`
```

## 출력
- `_workspace/qa/checklist.md`
- `_workspace/qa/tests/*.py|*.spec.js`
- `_workspace/qa/test_results/{date}.md`
- `_workspace/qa/evidence/{date}/`
- `_workspace/qa/regression_log.md`
