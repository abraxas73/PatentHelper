#!/usr/bin/env bash
# Supabase 마이그레이션 적용 스크립트
#
# 사용:
#   ./scripts/migrate.sh [--dry-run] [--file <path>]
#
# 동작:
#   _workspace/supabase/migrations/*.sql 및 supabase/migrations/*.sql 의 모든 .sql 파일을
#   파일명(lexicographic)순으로 Supabase PostgREST RPC 에 적용한다.
#   이미 적용된 마이그레이션은 tracking 테이블(migrations)로 판별.
#
# 환경:
#   .env 에서 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 자동 로드
#
# 주의:
#   프로덕션 DB 변경은 되돌릴 수 없다. --dry-run 먼저 확인 권장.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
log()  { printf "%s[migrate]%s %s\n" "$CYAN" "$RESET" "$*"; }
ok()   { printf "%s✓%s %s\n" "$GREEN" "$RESET" "$*"; }
warn() { printf "%s⚠%s %s\n" "$YELLOW" "$RESET" "$*"; }
die()  { printf "%s✗%s %s\n" "$RED" "$RESET" "$*" >&2; exit 1; }

DRY_RUN=0
SINGLE_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --file)    SINGLE_FILE="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *)         die "알 수 없는 옵션: $1" ;;
  esac
done

# ---- env 로드 ----
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  if [ -f "$ROOT/.env" ]; then
    set -a
    # shell source 시 값에 따옴표/특수문자 있을 수 있어 grep + 개별 처리 권장. 일단 source 시도.
    source "$ROOT/.env" 2>/dev/null || true
    set +a
  fi
fi
[ -z "${SUPABASE_URL:-}" ] && die "SUPABASE_URL 환경변수 없음"
[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && die "SUPABASE_SERVICE_ROLE_KEY 환경변수 없음"

# ---- 마이그레이션 파일 목록 ----
declare -a FILES
if [ -n "$SINGLE_FILE" ]; then
  FILES=("$SINGLE_FILE")
else
  # 우선순위: supabase/migrations/ > _workspace/supabase/migrations/
  for d in "$ROOT/supabase/migrations" "$ROOT/_workspace/supabase/migrations"; do
    [ -d "$d" ] || continue
    while IFS= read -r f; do
      FILES+=("$f")
    done < <(ls -1 "$d"/*.sql 2>/dev/null | sort)
  done
fi

[ ${#FILES[@]} -eq 0 ] && die "적용할 .sql 파일이 없습니다"

log "대상 파일 ${#FILES[@]}개:"
for f in "${FILES[@]}"; do echo "  - $f"; done
echo

# ---- 추적 테이블 준비 (_migrations) ----
python3 - <<PY
import os, urllib.request, urllib.error, json
URL = os.environ['SUPABASE_URL']
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
DRY = "$DRY_RUN" == "1"

sql_init = """
create table if not exists _migrations (
  name text primary key,
  applied_at timestamptz not null default now()
);
"""

def exec_sql(sql):
    if DRY:
        print(f"    [DRY] {sql[:80]}...")
        return
    # Supabase 는 /rpc/ 로 임의 SQL 직접 실행 불가. postgres_meta 나 pg-meta 필요.
    # 대안: service_role 로 PostgREST 의 내장 테이블 접근 어렵. 보편적 해결은 supabase CLI 또는 MCP.
    # 본 스크립트는 MCP 없을 때 폴백용이므로 psql 경유가 더 확실.
    import subprocess
    cmd = ['psql', os.environ.get('SUPABASE_DB_URL', ''), '-v', 'ON_ERROR_STOP=1', '-c', sql]
    if not os.environ.get('SUPABASE_DB_URL'):
        # psql 연결 URL 미설정 시 안내
        raise SystemExit("SUPABASE_DB_URL 미설정 — psql 연결 URL 필요 (Dashboard > Project Settings > Database > Connection string)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"psql 실패: {r.stderr[:500]}")

exec_sql(sql_init)
print("  _migrations 테이블 준비 완료")
PY

log "파일별 적용 시작"
for f in "${FILES[@]}"; do
  name=$(basename "$f" .sql)
  log "• $name"

  # 이미 적용됐는지 확인 (psql 필요)
  if [ -n "${SUPABASE_DB_URL:-}" ]; then
    applied=$(psql "$SUPABASE_DB_URL" -Atc "select 1 from _migrations where name = '$name' limit 1;" 2>/dev/null)
    if [ "$applied" = "1" ]; then
      ok "이미 적용됨, 스킵"
      continue
    fi
  fi

  if [ "$DRY_RUN" = "1" ]; then
    warn "[DRY] $name 적용 (실제 실행 안 됨)"
    continue
  fi

  if [ -z "${SUPABASE_DB_URL:-}" ]; then
    die "SUPABASE_DB_URL 없음 — MCP 사용 권장 또는 Dashboard > Settings > Database 에서 Connection string 복사 후 .env 에 추가"
  fi

  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$f" \
    && psql "$SUPABASE_DB_URL" -c "insert into _migrations(name) values('$name') on conflict do nothing;" \
    && ok "$name 적용 완료"
done

echo
ok "마이그레이션 완료 ${DRY_RUN:+(dry-run)}"
log "권장: MCP 를 쓸 수 있다면 'mcp__plugin_supabase_supabase__apply_migration' 이 더 안전/간편"
