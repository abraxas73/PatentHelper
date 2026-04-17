# scripts/ — 배포 자동화

이관 이후(2026-04-17~) 일상 운영 명령 모음.

## 배포: `deploy.sh`

통합 배포 스크립트. Vercel + Fly 두 워커를 한 번에 또는 선택적으로 배포.

```bash
# 전체 배포 (vercel + fly-extractor + fly-ocr)
./scripts/deploy.sh

# 특정 대상만
./scripts/deploy.sh vercel
./scripts/deploy.sh fly                  # 두 워커 모두
./scripts/deploy.sh fly-extractor
./scripts/deploy.sh fly-ocr

# dry-run (명령만 출력, 실제 실행 안 함)
./scripts/deploy.sh --dry-run

# 헬스체크 스킵 / git dirty 경고 무시
./scripts/deploy.sh --skip-verify
./scripts/deploy.sh --skip-git
```

### 동작
1. **사전 점검**: git dirty 경고 (커밋 안 된 변경은 Fly 배포에 포함 안 됨), FLY_API_TOKEN 로드
2. **Vercel**: `vercel --prod --yes` — 로컬 상태로 프로덕션 배포. 또는 main push 로도 자동 트리거 (GitHub Actions 불필요, Vercel Git integration 사용)
3. **Fly**: `flyctl deploy --config fly/{extractor,ocr}/fly.toml --remote-only --yes`
4. **검증**: `/api/get-upload-url` HTTP 200 + Fly machine `started` 상태 확인

### 주의
- **`app/config/settings.py` 수정 시**: PLATFORM 분기 유지 확인. 로컬 퇴행 없는지 `PLATFORM=local python main.py` 로 테스트
- **Fly OCR 재배포**: 이미지 681MB 빌드. 5~15분 소요 (remote builder). 최초 실행은 캐시 없어 더 오래
- **Vercel `_` prefix 금지**: 새 `api/` 모듈 추가 시 `_lib/` 같은 디렉토리 만들지 말 것 (번들 제외됨)

## 마이그레이션: `migrate.sh`

Supabase 스키마 변경 배포.

```bash
# 모든 대기 마이그레이션 적용
./scripts/migrate.sh

# dry-run
./scripts/migrate.sh --dry-run

# 특정 파일만
./scripts/migrate.sh --file supabase/migrations/0003_foo.sql
```

### 환경
- `.env` 에 `SUPABASE_DB_URL`(postgres connection string) 필요. Supabase Dashboard → Settings → Database → Connection string 복사
- 또는 Claude Code 세션 내에서는 MCP `mcp__plugin_supabase_supabase__apply_migration` 사용이 훨씬 안전 (이관 시 실제로 이 방식 사용)

### 파일 위치
- `supabase/migrations/*.sql` (정식)
- `_workspace/supabase/migrations/*.sql` (초안, gitignored)

## GitHub Actions 자동 배포 (선택)

현재 `.github/workflows/deploy-fly-*.yml` 은 `workflow_dispatch` 만 활성. 자동 푸시 트리거로 전환하려면:

```yaml
# .github/workflows/deploy-fly-extractor.yml 상단 on: 섹션 주석 해제
on:
  push:
    branches: [main]
    paths:
      - 'app/**'
      - 'fly/extractor/**'
      - '.github/workflows/deploy-fly-extractor.yml'
  workflow_dispatch:
```

Vercel 은 GitHub integration 으로 main push 시 자동 배포. 별도 워크플로우 불필요.

## 자주 쓰는 검증 명령

```bash
# 실도메인 API 헬스
curl -sS -X POST https://patent.sncbears.cloud/api/get-upload-url \
  -H "Content-Type: application/json" \
  -d '{"filename":"ping.pdf","content_type":"application/pdf"}'

# Fly 상태
flyctl status -a patent-extractor
flyctl status -a patent-ocr

# Fly 로그
flyctl logs -a patent-extractor --no-tail | tail -30
flyctl logs -a patent-ocr --no-tail | tail -30

# Vercel 에러 로그
vercel logs --limit 20 --level error

# Supabase 잡 테이블
# (MCP 있으면) mcp__plugin_supabase_supabase__execute_sql
#   "select status, count(*) from jobs group by 1;"
```

## 롤백

### Vercel
```bash
vercel rollback https://patent-helper-<prev-deployment>.vercel.app
# 또는 Dashboard → Deployments → Promote to Production
```

### Fly
```bash
flyctl releases -a patent-extractor         # 이전 릴리스 확인
flyctl deploy -a patent-extractor --image <prev-image-tag> --strategy immediate
# 또는 이미지 태그 없이 이전 커밋으로 되돌려 재배포
git revert HEAD && git push
./scripts/deploy.sh fly-extractor
```

### DNS (cutover 직후 긴급 롤백)
Gabia DNS 관리 → `patent` CNAME 을 기존 CloudFront 타겟으로 원복.
단 AWS 리소스는 이미 teardown 되어 서비스 복구 불가. 완전 롤백은 Supabase/Fly/Vercel 범위 내에서만.
