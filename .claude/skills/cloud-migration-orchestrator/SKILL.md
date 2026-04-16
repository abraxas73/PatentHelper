---
name: cloud-migration-orchestrator
description: PatentHelper의 AWS → Vercel/Fly.io/Supabase 이관을 오케스트레이션한다. Lambda 이관, ECS 컨테이너의 Fly.io 상주 워커 전환, DynamoDB/S3 → Supabase 전환, patent.sncbears.cloud DNS cutover, AWS 비용 정리(teardown)까지 전 과정을 진행한다. "이관/마이그레이션/Vercel/Fly.io/Supabase/cutover/AWS 정리/DNS 전환/재실행/업데이트/부분 수정" 등 클라우드 이전 관련 요청이 오면 반드시 이 스킬을 사용하라. 부분 재실행(예: 스키마만 수정)이나 후속 보완도 이 스킬로 처리한다.
---

# Cloud Migration Orchestrator

PatentHelper를 AWS에서 Vercel + Fly.io + Supabase 조합으로 이관하는 전체 워크플로우를 관리한다. 7명의 전문가 팀을 구성·조율하여 단계별로 진행하며, cutover는 한 번에, 기존 파일은 clean, DNS는 `patent.sncbears.cloud` → Vercel로 전환한다.

## 실행 모드: 에이전트 팀 (기본) — Phase별 하이브리드 허용

기본은 `TeamCreate`로 7명 팀을 구성하고 `TaskCreate` + `SendMessage`로 자체 조율. Phase 1(디스커버리)과 Phase 5(점진적 QA)만 서브 에이전트 병렬 호출 방식이 더 효율적이므로 하이브리드로 전환한다.

## 팀 구성
| 에이전트 | 타입 | 역할 |
|---------|------|------|
| `migration-architect` | general-purpose | 리더. 계획·의존성·cutover·teardown 조율 |
| `supabase-data-engineer` | general-purpose | Postgres 스키마, Storage 버킷, pgmq 큐, RLS |
| `vercel-api-engineer` | general-purpose | Lambda → Vercel Functions 포팅 |
| `flyio-worker-engineer` | general-purpose | ECS → Fly.io Machines 상주 워커 |
| `frontend-migration-engineer` | general-purpose | Vue 프론트 Vercel 배포 |
| `devops-cutover-engineer` | general-purpose | CI/CD 재구성, DNS 전환, AWS teardown |
| `qa-migration-tester` | general-purpose | 경계면 교차 검증, 3환경 동등성, E2E |

모든 Agent 호출에는 `model: "opus"` 파라미터를 명시한다.

## 작업 디렉토리
`_workspace/` 하위에 모든 중간 산출물을 저장한다. 최종 산출물은 실제 저장 위치(예: `front/vercel.json`, `fly/*/fly.toml`)로 복사한다. `_workspace/`는 감사 추적을 위해 삭제하지 않는다.

## Phase 0: 컨텍스트 확인 (필수)

워크플로우 시작 시 반드시 이 단계를 먼저 수행한다.

1. `_workspace/` 존재 여부 확인
2. 사용자 요청 분류:
   - **초기 실행**: `_workspace/` 없음 → Phase 1부터 전체 실행
   - **부분 재실행**: `_workspace/` 있음 + 특정 모듈 수정 요청 → 해당 팀원만 재호출, 계획 문서를 patch 형태로 갱신
   - **새 실행**: `_workspace/` 있음 + 처음부터 다시 요청 → 기존 디렉토리를 `_workspace_prev_{timestamp}/`로 이동
   - **후속 보완**: QA 피드백 반영 → architect가 라우팅하여 해당 팀원 재호출
3. `_workspace/checkpoint.md`가 있으면 읽고 재개 지점 결정

## Phase 1: 디스커버리 (서브 에이전트 병렬)

**실행 모드: 서브 에이전트 (독립 수집)**

architect가 `Agent` 도구로 서브 에이전트 3개를 병렬(`run_in_background=true`) 호출하여 현 구조를 수집한다. 결과는 architect에게만 반환되므로 팀 통신 오버헤드 없이 빠르게 완료.

- Explore 서브: `app/services/`, `app/core/`, `app/config/` 핵심 로직 파악
- Explore 서브: `deploy_aws/lambda/*/handler.py` 6개 함수의 입출력·트리거
- Explore 서브: `deploy_aws/ecs-extractor/`, `deploy_aws/ecs-ocr/` 래퍼 + `front/src/config.js`

architect가 결과를 통합해 `_workspace/01_current_architecture.md` 작성.

## Phase 2: 아키텍처 설계 및 데이터 계약 (팀)

**실행 모드: 에이전트 팀**

`TeamCreate`로 팀을 구성하고 architect 주도로 설계 합의.

1. architect가 `_workspace/02_migration_plan.md` 초안 작성
2. `supabase-data-engineer`에게 스키마 초안 요청 → `_workspace/supabase/schema.sql` 생성
3. 팀이 `SendMessage`로 계약 합의:
   - jobs 테이블 필드 확정
   - pgmq 큐 메시지 포맷 확정
   - Storage 경로 컨벤션 확정
   - 엔드포인트 URL/응답 shape 확정
4. architect가 `_workspace/03_data_contracts.md`를 단일 진실 출처로 확정

**게이트**: 사용자에게 `02_migration_plan.md` + `03_data_contracts.md`를 요약 보고하고 승인을 받는다. 승인 전 Phase 3 진입 금지.

## Phase 3: 기반 구축 — 병렬 팀 작업

**실행 모드: 에이전트 팀 (병렬 작업 분담)**

`TaskCreate`로 독립 작업을 병렬 할당.

- `supabase-data-engineer` → Supabase 프로젝트 스키마/RLS/pgmq 구축 (MCP `mcp__plugin_supabase_supabase__*` 우선, 미연결 시 마이그레이션 파일로 폴백)
- `vercel-api-engineer` → `_workspace/vercel/api/*.py` 뼈대 + `vercel.json`
- `flyio-worker-engineer` → `_workspace/fly/extractor/`, `_workspace/fly/ocr/` 뼈대 + fly.toml
- `frontend-migration-engineer` → `config.js` 수정안 + `vercel.json`
- `devops-cutover-engineer` → GitHub Actions 워크플로우 초안

**게이트**: 모든 팀원의 모듈이 "빌드 가능" 상태에 도달. QA 1차 실행.

## Phase 4: 포팅 완료 및 통합 (팀)

**실행 모드: 에이전트 팀**

- 각 팀원이 모듈별 기능 완성 (핸들러 본문, 워커 폴링 루프, 프론트 엔드포인트 전환)
- `/app/services` 재사용 경로 검증 (로컬 import와 Vercel/Fly import 일관성)
- architect가 팀원 간 계약 준수 여부 교차 확인

## Phase 5: 점진적 QA (하이브리드)

**실행 모드: 팀 내 QA + 필요 시 서브 에이전트**

`qa-migration-tester`가 각 모듈 완성 직후 즉시 검증. 전체 대기 금지. 큰 경계면 검증마다 Playwright 서브 에이전트 호출 가능.

검증 라운드:
1. **계약 테스트**: jobs 스키마 ↔ API 응답 JSON 필드 매칭
2. **큐 왕복 테스트**: Vercel 발행 → Fly 소비 → DB 상태 업데이트
3. **E2E (프리뷰)**: Vercel 프리뷰 URL + Fly 프리뷰 앱으로 전체 플로우 실행
4. **퇴행 체크**: 한글 파일명 다운로드, 이미지 회전, OCR 번호 인식

QA 결과는 architect가 라우팅하여 해당 팀원에게 재작업 요청.

## Phase 6: Cutover 준비 (팀)

**실행 모드: 에이전트 팀**

- devops-cutover-engineer가 `_workspace/cutover/T-minus_checklist.md` 최종화
- Fly 프로덕션 앱 배포, Vercel 프로덕션 배포 (프리뷰 → 프로덕션 승격)
- DNS 전환 준비 (TTL 단축, Vercel 도메인 추가)
- QA가 프로덕션 URL(Vercel 기본 도메인)로 최종 스모크 테스트

**게이트**: 사용자에게 "cutover 준비 완료" 보고. 사용자가 DNS 전환일 확정.

## Phase 7: Cutover 실행 (팀 + 사용자)

**실행 모드: 에이전트 팀 + 사용자 액션**

1. 사용자: Route53/DNS 제공자에서 `patent.sncbears.cloud` → Vercel로 전환
2. devops-cutover-engineer: Vercel 측 도메인 바인딩 확인, SSL 발급 대기
3. qa-migration-tester: 실도메인 기반 전체 플로우 재검증
4. architect: T+1시간 / T+24시간 모니터링 포인트 제시

**게이트**: QA가 "실도메인 정상" 사인 → architect가 사용자에 최종 보고 → 48시간 모니터링 권고.

## Phase 8: AWS Teardown (devops + 사용자)

**실행 모드: devops 서브 에이전트 + 사용자 승인**

48시간 트래픽 모니터링 후 AWS 정리 착수. 파괴적 명령은 **사용자가 직접 실행**하고 devops는 체크리스트만 제공한다.

제거 순서 (의존 역순):
1. CloudFront 배포 비활성화 → 삭제 (CLAUDE.md 경고: `sam deploy` 절대 금지. 콘솔 또는 CLI 직접)
2. API Gateway 삭제
3. Lambda 함수 6개 삭제
4. ECS 서비스/태스크 정의 중지 및 삭제
5. ECR 이미지 리포 삭제
6. S3 버킷: 사용자에게 백업 여부 최종 확인 후 삭제 (clean cutover이므로 기본 삭제)
7. DynamoDB 테이블: 이력 이전 완료 여부 확인 후 삭제
8. IAM 역할/정책 정리
9. Route53 레코드 잔재 정리

devops가 `_workspace/teardown/aws_teardown.sh` 드라이런 스크립트 제공. 사용자가 각 단계를 승인하며 실행.

## 데이터 전달 프로토콜

| 전략 | 용도 |
|------|------|
| 파일 기반 (`_workspace/`) | 스키마·설계문서·코드 스니펫·체크리스트 |
| 태스크 기반 (`TaskCreate`) | Phase별 작업 분배, 의존성, 진행 상태 |
| 메시지 기반 (`SendMessage`) | 계약 합의, 피드백, 블로커 신고 |

파일명 컨벤션: `_workspace/{영역}/{순번}_{내용}.{확장자}`
- 예: `_workspace/vercel/api/extract-mappings.py`, `_workspace/supabase/01_schema.sql`

## 에러 핸들링

| 상황 | 대응 |
|------|------|
| 팀원 1회 실패 | 재호출 1회 → 실패 시 architect가 대안 제시·사용자 보고 |
| 계약 충돌 (팀원 간) | architect 중재 → `03_data_contracts.md`에 결정 기록 |
| 플랫폼 제약 (Vercel 10s 등) | 즉시 사용자 보고 + 우회안 (워커로 위임 등) |
| pgmq extension 불가 | Postgres 폴링 테이블로 폴백 |
| DNS 전환 후 SSL 미발급 | Vercel 자동 발급 대기 안내 (수분~1시간) |
| cutover 후 오류 발견 | architect 판단 — 핫픽스 or DNS 롤백 (TTL 고려) |

## 테스트 시나리오

**정상 흐름**
1. 사용자: "AWS → Vercel/Fly/Supabase 이관 진행"
2. Phase 0~2 진행, 계약 합의 후 사용자 승인
3. Phase 3~5 병렬 구축 + QA
4. Phase 6 cutover 준비 보고
5. 사용자 DNS 전환 → Phase 7 검증
6. 48시간 후 Phase 8 teardown

**에러 흐름 (재실행)**
1. 사용자: "매핑 API 응답에 필드가 하나 빠졌어, 다시 해줘"
2. Phase 0에서 `_workspace/` 감지 → 부분 재실행 모드
3. architect가 vercel-api-engineer + qa-migration-tester만 재호출
4. `02_migration_plan.md`에 변경 이력 추가
5. QA 검증 후 보고

**에러 흐름 (계약 충돌)**
1. vercel-api-engineer가 `extracted_images`를 `list[str]`로 해석, flyio-worker가 `list[dict]` 기대
2. qa-migration-tester가 계약 테스트에서 감지 → architect에 보고
3. architect가 `03_data_contracts.md`에 `list[dict{page, path}]` 확정
4. 양쪽 팀원 수정

## 후속 작업 키워드

이 스킬은 다음 표현이 포함되면 반드시 트리거된다:
- 이관, 마이그레이션, 마이그레이트, Vercel, Fly.io, Fly, Supabase, cutover, DNS 전환
- AWS 정리, AWS teardown, Lambda 정리, ECS 정리, CloudFront 정리
- 재실행, 다시 실행, 업데이트, 수정, 보완, 부분 수정
- "스키마만 다시", "워커만 다시", "API만 다시", "프론트만 다시"

단순 질문(개념 설명)은 트리거하지 않고 직접 답변한다.

## 참조
- 팀원 상세 정의: `.claude/agents/{name}.md`
- 개별 스킬: `.claude/skills/{migration-plan, supabase-schema-storage, vercel-api-port, flyio-worker-setup, frontend-vercel-deploy, cicd-cutover-aws-teardown, migration-qa-verify}/`
