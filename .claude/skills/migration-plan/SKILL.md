---
name: migration-plan
description: migration-architect가 마이그레이션 계획서·데이터 계약·cutover 체크리스트·AWS teardown 계획을 구조화할 때 사용한다. 의존성 그래프와 리스크 레지스터 템플릿을 제공하여 단일 진실 출처(03_data_contracts.md)를 유지하게 한다.
---

# Migration Plan

architect 전용 스킬. 계획 문서 3종을 일관된 구조로 유지한다.

## 산출 문서 4종

### 1. `_workspace/02_migration_plan.md`
```markdown
# Migration Plan
## 목표
- AWS 비용 제거, 기능 동등성 유지, cutover는 한 번에

## 의존성 그래프
1. Supabase 스키마/Storage/pgmq (선행, 블로커)
2. Fly 워커 포팅 (pgmq 소비) — Supabase 필요
3. Vercel API 포팅 (pgmq 발행, DB 쿼리) — Supabase 필요
4. 프론트 엔드포인트 전환 — Vercel API 필요
5. GitHub Actions·배포 자동화 — 2,3,4 완료 후
6. QA (각 모듈 직후 + 통합) — 지속
7. Cutover (DNS) — 5,6 완료 후
8. AWS teardown — Cutover + 48h 모니터링 후

## Phase 상태
| Phase | 상태 | 담당 | 비고 |
|-------|------|------|------|

## 리스크 레지스터
| # | 리스크 | 영향 | 확률 | 완화 | 상태 |
|---|--------|------|------|------|------|
| 1 | pgmq 활성화 불가 | 높음 | 낮음 | 폴링 테이블 폴백 | 모니터 |
| 2 | OCR 콜드스타트 증가 | 중 | 중 | 모델 사전 캐시 | 모니터 |
| 3 | DNS 전환 후 SSL 지연 | 중 | 중 | TTL 선조정 | 계획됨 |
```

### 2. `_workspace/03_data_contracts.md` — 단일 진실
```markdown
# Data Contracts

## jobs 테이블 스키마
| 필드 | 타입 | null | 설명 |
|------|------|------|------|
| id | uuid | no | ... |

## pgmq 메시지 포맷
### extract_jobs
```json
{"job_id": "uuid", "pdf_path": "uploads/{id}/original.pdf"}
```
### ocr_jobs
```json
{"job_id": "uuid", "mappings": [{"number": "111", "label": "..."}]}
```

## Storage 경로 규칙
- 원본: `uploads/{job_id}/original.pdf`
- 도면: `results/{job_id}/drawings/drawing_{page:03d}.png`
- 어노테이션: `results/{job_id}/annotated/annotated_{page:03d}.png`
- 완성 PDF: `results/{job_id}/completed.pdf`
- 재생성 PDF: `results/{job_id}/regenerated.pdf`

## API 엔드포인트
| 경로 | 메서드 | 요청 | 응답 |
|------|--------|------|------|
```

### 3. `_workspace/04_cutover_checklist.md`
```markdown
# Cutover Checklist (T-schedule)

## T-7일
- [ ] Vercel 프로덕션 배포 완료
- [ ] Fly 프로덕션 앱 배포 완료
- [ ] Supabase 프로덕션 프로젝트 확정
- [ ] DNS TTL 300초로 단축

## T-1일
- [ ] Vercel에 patent.sncbears.cloud 도메인 추가 (pending 상태 확인)
- [ ] 최종 QA 스모크 테스트 통과
- [ ] 롤백 계획 확인

## T-0 (전환일)
- [ ] Route53/DNS에서 CNAME → Vercel 엔드포인트로 변경
- [ ] Vercel 도메인 활성 + SSL 발급 확인
- [ ] QA 실도메인 테스트 실행
- [ ] 모니터링 알림 점검

## T+1시간, T+24시간
- [ ] 에러율/지연시간 모니터링
- [ ] 사용자 피드백 채널 확인

## T+48시간
- [ ] teardown 승인 가능 판단
```

### 4. `_workspace/05_aws_teardown_plan.md`
```markdown
# AWS Teardown Plan

## 제거 순서 (역의존)
1. CloudFront 비활성화 → 삭제 (콘솔 직접)
2. API Gateway 삭제
3. Lambda 함수 6개 삭제 (extract-mappings, process-mappings, status, result, history, image-proxy)
4. ECS 서비스 중지 → 태스크 정의 비활성
5. ECR 이미지 리포 (patent-extractor, patent-ocr) 삭제
6. S3 버킷 비우기 → 삭제 (clean cutover이므로)
7. DynamoDB 테이블 삭제
8. IAM 역할: LambdaExecutionRole, ECSTaskRole 등 정리
9. Route53 레코드 정리
10. SAM S3 bucket (patent-helper-sam-deploy-*) 정리

## 주의
- `sam deploy` 절대 금지 (CLAUDE.md 경고)
- 파괴적 명령은 사용자가 직접 실행
- 비용 모니터링으로 잔재 리소스 확인
```

## 작성 원칙
- **단일 진실 출처**: 계약/스키마는 `03_data_contracts.md`에만. 다른 문서에서는 참조만
- **이력 보존**: 변경 시 해당 섹션 하단 `## 변경 이력`에 날짜+변경 기록
- **가독성**: 표·체크리스트 위주. 긴 산문 지양
- **사용자 보고용**: 각 문서 상단 1줄 요약 필수

## 업데이트 규칙
- architect만 직접 수정. 다른 팀원은 `SendMessage`로 제안 → architect가 반영
- 부분 재실행 시 해당 섹션만 diff, 나머지 보존
- 완전 재실행 시 이전 버전을 `_workspace_prev_{timestamp}/`로 이동
