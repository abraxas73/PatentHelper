# 배포 가이드

> 이관 기준일: 2026-04-17. AWS Lambda/ECS/CloudFront 운영은 종료, Vercel + Fly.io + Supabase 스택으로 전환 완료. 이 문서는 **이관 이후 운영/개발자용** 가이드입니다.
>
> AWS 시절 가이드는 `deploy_aws/DEPLOYMENT.md`에 보존 (teardown 완료되어 실행 불가, 레퍼런스 전용).

---

## 1. 아키텍처 한눈에

```
사용자 브라우저
     │  https://patent.sncbears.cloud
     ▼
┌──────────────────────────────────────────────┐
│  Vercel                                       │
│  ─ Vite 정적(front/dist) + Python Functions   │
│  ─ /api/* (8개 엔드포인트)                    │
└───────────┬──────────────────────────────────┘
            │ service_role
            ▼
┌──────────────────────────────────────────────┐
│  Supabase (ap-northeast-2)                   │
│  ─ Postgres: jobs, job_events                │
│  ─ Storage: uploads, results (비공개)         │
│  ─ pgmq: extract_jobs, ocr_jobs, regenerate  │
└───────────┬──────────────────────────────────┘
            │ 큐 폴링
            ▼
┌──────────────────────────────────────────────┐
│  Fly.io Machines (nrt)                       │
│  ─ patent-extractor (shared-cpu-2x / 2GB)    │
│  ─ patent-ocr       (performance-4x / 8GB)   │
│     · PyTorch CPU + EasyOCR 모델 사전 캐시   │
└──────────────────────────────────────────────┘
```

### 주요 리소스
| 구성 | 이름/ID | 비고 |
|------|--------|------|
| 도메인 | `patent.sncbears.cloud` | Gabia DNS, CNAME → `cname.vercel-dns.com` |
| Vercel 프로젝트 | `patent-helper` | `seunguk-kangs-projects` 팀 |
| Supabase 프로젝트 | `tvqnnlovlxhwdtosrzky` (PatentHelper) | Postgres 17, ap-northeast-2 |
| Fly 앱 | `patent-extractor`, `patent-ocr` | personal org |

---

## 2. 최초 환경 설정 (신규 작업자)

### 2.1 계정 / CLI

```bash
# 필수 CLI (macOS 기준)
brew install flyctl
npm i -g vercel

# 로그인
flyctl auth login                 # 또는 FLY_API_TOKEN 환경변수
vercel login                      # GitHub/이메일 OAuth

# 프로젝트 로컬 링크
cd PatentHelper
vercel link --yes --project patent-helper
```

### 2.2 `.env` (로컬)

프로젝트 루트에 `.env`(gitignored) 생성:

```env
# Fly 배포용
FLY_API_TOKEN='FlyV1 fm2_xxx,fm2_yyy'    # 반드시 작은따옴표 — 공백/쉼표 포함

# Supabase 서버용 (로컬에서도 production DB 에 접근하려면)
SUPABASE_URL=https://tvqnnlovlxhwdtosrzky.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...    # 절대 공개 금지
SUPABASE_ANON_KEY=eyJhbGciOi...            # 공개 가능

# 마이그레이션용 (선택)
SUPABASE_DB_URL=postgresql://postgres:<pw>@db.tvqnnlovlxhwdtosrzky.supabase.co:5432/postgres
```

### 2.3 프론트 `.env.production` 의 `VITE_*` 값

`front/.env.production`은 공개 가능한 `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`만 둡니다. 서버 전용 키는 **절대** 넣지 말 것.

### 2.4 Vercel Env Vars (대시보드)

https://vercel.com/seunguk-kangs-projects/patent-helper/settings/environment-variables

| Key | Value | Env |
|-----|-------|-----|
| `PLATFORM` | `vercel` | Production, Preview, Development |
| `SUPABASE_URL` | (URL) | 전부 |
| `SUPABASE_SERVICE_ROLE_KEY` | (service_role) | 전부 |
| `VITE_SUPABASE_URL` | (URL) | 전부 |
| `VITE_SUPABASE_ANON_KEY` | (anon) | 전부 |
| `VITE_API_BASE` | `/api` | 전부 |

### 2.5 Fly Secrets (앱별)

```bash
flyctl secrets set \
  SUPABASE_URL=https://tvqnnlovlxhwdtosrzky.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=<service-role> \
  IDLE_EXIT_AFTER=0 \
  -a patent-extractor

# patent-ocr 도 동일하게
```

### 2.6 GitHub Secrets (CI 자동 배포용)

Repo → Settings → Secrets and variables → Actions:
- `FLY_API_TOKEN` — `flyctl auth token` 값

---

## 3. 로컬 개발

`app/config/settings.py`에 `PLATFORM` 분기가 도입되어 **기존 로컬 동작은 그대로 유지**됩니다.

```bash
# 백엔드 (FastAPI)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py > api.log 2>&1 &
# → http://localhost:8000

# 프론트
cd front && npm install && npm run dev
# → http://localhost:3000
```

`PLATFORM=local`(기본)이면 Supabase 접속 없이 로컬 파일시스템만 사용. Vercel 함수 로컬 실행은 `vercel dev` 참조.

---

## 4. 배포

### 4.1 일반 (Git push)

`main` 브랜치 푸시 한 번으로 자동 배포:

| 변경 경로 | 자동 배포 대상 |
|----------|-------------|
| `front/**`, `vercel.json`, `api/**`, `app/**` | **Vercel** (GitHub Integration) |
| `app/**`, `fly/extractor/**`, 해당 workflow | **Fly Extractor** (GitHub Actions) |
| `app/**`, `fly/ocr/**`, 해당 workflow | **Fly OCR** (GitHub Actions) |

확인:
```bash
gh run list --limit 5                           # CI 상태
vercel ls patent-helper | head -10              # Vercel 배포 목록
```

### 4.2 수동 (로컬 스크립트)

```bash
./scripts/deploy.sh                 # 전체 (vercel + fly 2개)
./scripts/deploy.sh vercel
./scripts/deploy.sh fly              # extractor + ocr
./scripts/deploy.sh fly-extractor
./scripts/deploy.sh fly-ocr

# 옵션
./scripts/deploy.sh --dry-run
./scripts/deploy.sh --skip-verify
./scripts/deploy.sh --skip-git
```

### 4.3 긴급 (CI 없이)

```bash
# Vercel
vercel --prod --yes

# Fly
flyctl deploy --config fly/extractor/fly.toml --dockerfile fly/extractor/Dockerfile --remote-only
flyctl deploy --config fly/ocr/fly.toml --dockerfile fly/ocr/Dockerfile --remote-only
```

---

## 5. Supabase 마이그레이션

### 5.1 Claude Code 세션 내 (권장)

MCP 도구 사용이 가장 안전:
```
mcp__plugin_supabase_supabase__apply_migration(
  project_id="tvqnnlovlxhwdtosrzky",
  name="0003_add_X",
  query="<SQL>"
)
```

### 5.2 CLI

```bash
# 사전: .env 에 SUPABASE_DB_URL 설정
./scripts/migrate.sh --dry-run        # 실행 전 확인
./scripts/migrate.sh                   # 모든 대기 마이그레이션 적용
./scripts/migrate.sh --file supabase/migrations/0003_foo.sql
```

### 5.3 마이그레이션 파일 규칙
- 위치: `supabase/migrations/<NNNN>_<snake_case>.sql`
- 멱등 작성 (`create ... if not exists`, `or replace`, `on conflict`)
- RLS 활성화된 테이블에는 적절한 정책 추가
- 보안 advisor 수시 확인: `mcp__plugin_supabase_supabase__get_advisors(type="security")`

---

## 6. 모니터링 & 로그

### 6.1 대시보드
- Vercel: https://vercel.com/seunguk-kangs-projects/patent-helper
- Fly: https://fly.io/apps/patent-extractor / patent-ocr
- Supabase: https://supabase.com/dashboard/project/tvqnnlovlxhwdtosrzky

### 6.2 CLI 로그

```bash
# Vercel
vercel logs --limit 50                          # 최근 요청
vercel logs --limit 20 --level error            # 에러만
vercel logs --follow                            # 실시간 스트리밍

# Fly
flyctl logs -a patent-extractor                 # 실시간
flyctl logs -a patent-ocr --no-tail | tail -50  # 최근
flyctl status -a patent-extractor               # 머신 상태

# Supabase (작업 상태 조회)
# MCP: execute_sql("select status, count(*) from jobs group by 1")
```

### 6.3 헬스체크
```bash
curl -sI https://patent.sncbears.cloud/

curl -sS -X POST https://patent.sncbears.cloud/api/get-upload-url \
  -H "Content-Type: application/json" \
  -d '{"filename":"ping.pdf","content_type":"application/pdf"}'
```

### 6.4 큐 상태

```sql
-- Supabase SQL Editor 에서
select queue_name,
       (select count(*) from pgmq.q_extract_jobs) as extract_pending,
       (select count(*) from pgmq.q_ocr_jobs)     as ocr_pending,
       (select count(*) from pgmq.q_regenerate_jobs) as regenerate_pending
from pgmq.list_queues() limit 1;

-- 아카이브 (실패 3회 메시지)
select count(*) from pgmq.a_extract_jobs;
```

---

## 7. 롤백

### 7.1 Vercel
```bash
# Deployment URL 확인
vercel ls patent-helper

# 이전 배포로 되돌리기
vercel rollback https://patent-helper-<prev>-seunguk-kangs-projects.vercel.app

# 또는 Dashboard → Deployments → 이전 배포 → "Promote to Production"
```

### 7.2 Fly
```bash
flyctl releases -a patent-extractor             # 릴리스 이력
flyctl deploy -a patent-extractor --image <prev-sha>   # 특정 이미지로

# Git 기반 롤백 (GitHub Actions 가 재빌드)
git revert <bad-commit> && git push
```

### 7.3 Supabase
- **데이터 변경은 되돌릴 수 없음** (pg_dump 백업이 없으면)
- 스키마 변경 롤백은 역 마이그레이션(`0003_rollback_foo.sql`) 작성 후 `./scripts/migrate.sh`

### 7.4 DNS 롤백 (cutover 직후만)
Gabia → sncbears.cloud DNS 관리 → `patent` CNAME 원복. **주의**: AWS 리소스는 teardown 완료되어 완전 롤백 불가.

---

## 8. 비용 관리

### 현재 월 비용 (추정)
| 항목 | 비용 |
|------|------|
| Fly `patent-extractor` (shared-cpu-2x, 2GB, 24/7) | ~$8 |
| Fly `patent-ocr` (performance-4x, 8GB, 24/7) | ~$60 |
| Vercel Hobby 또는 Pro | $0 또는 $20 |
| Supabase Free 또는 Pro | $0 또는 $25 |
| **합계** | **~$68 ~ $113** |

### 최적화 포인트
1. **OCR 스케일 투 제로**: 현재 `IDLE_EXIT_AFTER=0`(상시 실행). 트래픽 적으면 `300`(5분 idle 후 종료)로 되돌리고, Vercel 함수에서 Fly Machines REST API(`POST /v1/apps/{app}/machines/{id}/start`)로 큐 발행 시 기동 — 월 $40+ 절감 가능
2. **Extractor 리전 축소**: nrt 말고 경량 리전 (fly.io는 자동)
3. **Supabase Storage 정리**: 오래된 `results/{job_id}/`를 주기적으로 비우는 크론 (pg_cron + pgmq_archive 참고)

---

## 9. 트러블슈팅 (이관 시 겪은 이슈 기록)

### 9.1 Vercel: `ModuleNotFoundError: No module named '_lib'`
**원인**: `_` prefix 디렉토리는 함수 번들에서 제외됨.
**대응**: 공통 코드를 각 함수에 인라인하거나, `includeFiles` 로 명시 포함 + `sys.path` 조정.

### 9.2 Vercel: `Function Runtimes must have a valid version`
**원인**: 최신 Vercel이 `"runtime": "python3.12"` 문자열 거부.
**대응**: `runtime` 필드 제거하고 `api/runtime.txt` 에 `python-3.12` 로 힌트.

### 9.3 Vercel: Root Directory `front/` 설정 시 `api/` 404
**원인**: Root Directory 가 `front/` 면 레포 루트의 `api/` 무시.
**대응**: Dashboard → Settings → General → Root Directory = `./`.

### 9.4 Fly OCR: `numpy.core.multiarray failed to import`
**원인**: `numpy>=1.26.0`이 2.x를 끌어오는데 OpenCV/EasyOCR/PyTorch 2.3은 numpy 1.x 빌드.
**대응**: `fly/ocr/requirements.txt`에 `numpy>=1.26.0,<2.0` pin.

### 9.5 Fly: `JSONDecodeError: Expecting value` on Storage download
**원인**: `storage3` 라이브러리가 HTTP 에러 응답의 empty body를 JSON으로 파싱.
**대응**: `sb.storage.from_().download()` 대신 `httpx`로 직접 GET.

### 9.6 Fly: 머신이 `idle exit after 300s`로 자가 종료 후 큐 정체
**원인**: Fly Machines는 HTTP service 없는 워커를 자동 기동하지 않음.
**대응**: `IDLE_EXIT_AFTER=0` secret + 상시 실행. 또는 Vercel 함수가 `fly machine start` API 호출.

### 9.7 S3 버킷 비우기 `MalformedXML` (teardown 시)
**원인**: Key 이름에 XML 제어문자 포함되어 `delete-objects` 실패.
**대응**: `boto3`로 `bucket.object_versions.pages()` 사용.

---

## 10. 권장 운영 체크리스트

### 주간
- [ ] Vercel 에러율 대시보드 확인 (`vercel logs --level error --limit 100`)
- [ ] Supabase `get_advisors(security)` 실행
- [ ] Fly 머신 `started` 상태 + 재시작 횟수 확인

### 월간
- [ ] Supabase Storage 크기 확인 + 오래된 결과물 정리
- [ ] Fly 요금 청구서 확인 (`flyctl billing info`는 없으므로 대시보드)
- [ ] 의존성 업데이트 (`api/requirements.txt`, `fly/*/requirements.txt`)
- [ ] DB 백업 스냅샷 (Supabase Dashboard → Database → Backups)

### 분기
- [ ] `FLY_API_TOKEN`, `SUPABASE_SERVICE_ROLE_KEY` rotate
- [ ] 보안 advisor 잔여 WARN 정리

---

## 11. 레퍼런스

- `scripts/README.md` — 스크립트 상세
- `_workspace/checkpoint.md` — 이관 진행 이력 (로컬, gitignored)
- `CLAUDE.md` — 프로젝트 개요 및 하네스 변경 이력
- `deploy_aws/DEPLOYMENT.md` — **구 AWS 가이드 (이관 완료되어 실행 불가, 이력용)**

### 공식 문서
- Vercel Python Functions: https://vercel.com/docs/functions/runtimes/python
- Fly.io Machines: https://fly.io/docs/machines/
- Supabase pgmq: https://supabase.com/docs/guides/queues
- supabase-py: https://github.com/supabase/supabase-py
