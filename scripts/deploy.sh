#!/usr/bin/env bash
# PatentHelper 통합 배포 스크립트
#
# 사용:
#   ./scripts/deploy.sh [target] [옵션]
#
# target (복수 지정 가능, 공백 구분):
#   vercel          — Vercel 프로덕션 배포 (현재 main 커밋 기준)
#   fly-extractor   — Fly patent-extractor 재배포
#   fly-ocr         — Fly patent-ocr 재배포
#   fly             — fly-extractor + fly-ocr
#   all             — vercel + fly (기본값)
#
# 옵션:
#   --skip-verify   — 배포 후 헬스체크 스킵
#   --skip-git      — dirty 상태 경고 무시
#   --dry-run       — 명령만 출력, 실제 실행 안 함
#
# 환경:
#   .env 파일에서 FLY_API_TOKEN 자동 로드 (Fly 대상에 한정)
#   Vercel 은 `vercel` CLI 가 이미 login 되어 있어야 함

set -euo pipefail

# ---- 경로/색상 ----
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'

log()  { printf "%s[deploy]%s %s\n" "$CYAN" "$RESET" "$*"; }
ok()   { printf "%s✓%s %s\n" "$GREEN" "$RESET" "$*"; }
warn() { printf "%s⚠%s %s\n" "$YELLOW" "$RESET" "$*"; }
die()  { printf "%s✗%s %s\n" "$RED" "$RESET" "$*" >&2; exit 1; }

# ---- 옵션 파싱 ----
SKIP_VERIFY=0; SKIP_GIT=0; DRY_RUN=0
TARGETS=()
for arg in "$@"; do
  case "$arg" in
    --skip-verify) SKIP_VERIFY=1 ;;
    --skip-git)    SKIP_GIT=1 ;;
    --dry-run)     DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,25p' "$0"; exit 0 ;;
    -*)
      die "알 수 없는 옵션: $arg" ;;
    *)
      TARGETS+=("$arg") ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("all")

# "fly" → "fly-extractor fly-ocr" 전개, "all" → 모두
EXPANDED=()
for t in "${TARGETS[@]}"; do
  case "$t" in
    all) EXPANDED+=(vercel fly-extractor fly-ocr) ;;
    fly) EXPANDED+=(fly-extractor fly-ocr) ;;
    vercel|fly-extractor|fly-ocr) EXPANDED+=("$t") ;;
    *)   die "알 수 없는 타겟: $t (vercel|fly-extractor|fly-ocr|fly|all)" ;;
  esac
done
# 중복 제거 + 순서 보존
TARGETS=($(printf '%s\n' "${EXPANDED[@]}" | awk '!seen[$0]++'))

# ---- 실행 헬퍼 ----
run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf "  %s[DRY]%s %s\n" "$YELLOW" "$RESET" "$*"
    return 0
  fi
  "$@"
}

# ---- 사전 점검 ----
log "대상: ${TARGETS[*]} ${DRY_RUN:+(dry-run)}"

if [ "$SKIP_GIT" = "0" ]; then
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "작업 디렉토리가 dirty 입니다. 커밋되지 않은 변경이 배포에 포함되지 않을 수 있습니다."
    warn "(--skip-git 로 무시 가능)"
    git status --short | head -10
    read -p "  계속할까요? [y/N] " yn
    [ "${yn:-N}" = "y" ] || [ "${yn:-N}" = "Y" ] || die "중단"
  fi
fi

need_fly_token=0
for t in "${TARGETS[@]}"; do
  [[ "$t" == fly-* ]] && need_fly_token=1
done

if [ "$need_fly_token" = "1" ]; then
  if [ -z "${FLY_API_TOKEN:-}" ]; then
    if [ -f "$ROOT/.env" ]; then
      FLY_API_TOKEN="$(awk -F= '/^FLY_API_TOKEN=/{sub(/^FLY_API_TOKEN=/, ""); gsub(/^['\''"]|['\''"]$/, ""); print; exit}' "$ROOT/.env")"
      export FLY_API_TOKEN
    fi
  fi
  [ -z "${FLY_API_TOKEN:-}" ] && die ".env 또는 환경에 FLY_API_TOKEN 이 없습니다"
  command -v flyctl >/dev/null || die "flyctl 이 설치되어 있지 않습니다 (brew install flyctl)"
fi

# ---- 배포 루틴 ----
deploy_vercel() {
  log "Vercel 프로덕션 배포 (Git 연동: main push 시 자동이나 수동 트리거 가능)"
  command -v vercel >/dev/null || die "vercel CLI 없음 (npm i -g vercel)"
  # --prod 로 current local 상태를 배포 (Git 상태와 무관하게)
  # Git main 기준으로 배포하려면 main branch push 로 자동 트리거
  run vercel --prod --yes
  ok "Vercel 배포 트리거됨"
}

deploy_fly() {
  local app="$1"   # patent-extractor | patent-ocr
  local dir="$2"   # fly/extractor | fly/ocr
  log "Fly $app 재배포"
  run flyctl deploy \
    --config  "$dir/fly.toml" \
    --dockerfile "$dir/Dockerfile" \
    --remote-only \
    --yes
  ok "Fly $app 배포 완료"
}

verify_vercel() {
  log "Vercel 헬스체크 — https://patent.sncbears.cloud"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" https://patent.sncbears.cloud/ || echo 000)
  [ "$code" = "200" ] && ok "index 200" || warn "index $code"
  code=$(curl -sS -o /tmp/deploy_verify.json -w "%{http_code}" \
    -X POST https://patent.sncbears.cloud/api/get-upload-url \
    -H "Content-Type: application/json" \
    -d '{"filename":"deploy-verify.pdf","content_type":"application/pdf"}' || echo 000)
  [ "$code" = "200" ] && ok "/api/get-upload-url 200" || { warn "/api/get-upload-url $code"; head -c 300 /tmp/deploy_verify.json; }
}

verify_fly() {
  local app="$1"
  local state
  state=$(flyctl status -a "$app" --json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
ms = d.get('Machines') or d.get('machines') or []
for m in ms:
    role = (m.get('role') or '').lower()
    state = m.get('state') or m.get('State')
    if role != 'standby':
        print(state); break
else:
    print('?')
" 2>/dev/null || echo "?")
  [ "$state" = "started" ] && ok "$app primary started" || warn "$app primary state=$state"
}

# ---- 실행 ----
RAN_VERCEL=0; RAN_FLY_EX=0; RAN_FLY_OCR=0
for t in "${TARGETS[@]}"; do
  case "$t" in
    vercel)         deploy_vercel && RAN_VERCEL=1 ;;
    fly-extractor)  deploy_fly patent-extractor "$ROOT/fly/extractor" && RAN_FLY_EX=1 ;;
    fly-ocr)        deploy_fly patent-ocr       "$ROOT/fly/ocr"       && RAN_FLY_OCR=1 ;;
  esac
done

# ---- 검증 ----
if [ "$SKIP_VERIFY" = "0" ] && [ "$DRY_RUN" = "0" ]; then
  echo
  log "사후 검증"
  [ "$RAN_VERCEL" = "1" ] && { sleep 3; verify_vercel; }
  [ "$RAN_FLY_EX" = "1" ]  && verify_fly patent-extractor
  [ "$RAN_FLY_OCR" = "1" ] && verify_fly patent-ocr
fi

echo
ok "완료: ${TARGETS[*]}"
