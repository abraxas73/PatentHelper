---
name: cicd-cutover-aws-teardown
description: GitHub Actions 재구성(fly/vercel 자동 배포), patent.sncbears.cloud DNS cutover 체크리스트, AWS 자원 teardown 순서/스크립트. 파괴적 명령은 사용자 실행, 스크립트는 드라이런 우선. sam deploy 절대 금지.
---

# CI/CD Cutover & AWS Teardown

`devops-cutover-engineer` 전용. 배포 자동화 + cutover + AWS 비용 제거를 관리한다.

## 핵심 제약
- **`sam deploy` 금지** (CLAUDE.md): CloudFront 설정이 덮어써진다
- **파괴적 명령은 사용자 실행**: 스크립트는 에코/드라이런만, 실제 삭제는 사용자 확인 후
- **Cutover는 한 번에**: blue-green 없음. T-체크리스트로 리스크 완화

## 1. GitHub Actions 재구성

### 제거
- `.github/workflows/deploy-ecs-extractor.yml`
- `.github/workflows/deploy-ecs-ocr.yml`
- (있다면) SAM 배포 워크플로우

### 추가: `.github/workflows/deploy-fly-extractor.yml`
```yaml
name: Deploy Fly Extractor
on:
  push:
    branches: [main]
    paths:
      - 'app/**'
      - 'fly/extractor/**'
      - '.github/workflows/deploy-fly-extractor.yml'
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy -c fly/extractor/fly.toml --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

### 추가: `.github/workflows/deploy-fly-ocr.yml` (동일 패턴, `fly/ocr/` 경로)

### Vercel
- main push 시 자동 배포 (Vercel GitHub 연동). 별도 Action 파일 불필요
- PR → Preview URL 자동 생성. QA가 프리뷰로 검증

## 2. Cutover 체크리스트 (`_workspace/cutover/T-minus_checklist.md`)

### T-7일
- [ ] Vercel 프로덕션 배포 성공, 기본 도메인에서 정상
- [ ] Fly 두 앱(extractor/ocr) 프로덕션 배포
- [ ] Supabase 프로덕션 프로젝트 확정, pgmq 활성
- [ ] DNS TTL을 300초로 단축 (전환 시 빠른 전파)
- [ ] 사용자에게 전환 일자/시간 최종 합의

### T-1일
- [ ] Vercel 대시보드에 `patent.sncbears.cloud` 도메인 추가 (pending)
- [ ] QA E2E 전체 통과 (Vercel 프리뷰 + Fly 프로덕션 워커)
- [ ] 롤백 방법 문서화 (DNS를 CloudFront로 되돌리기)
- [ ] AWS 자원 상태 캡처 (ECS 태스크 수, Lambda invocation, DynamoDB 레코드 수)

### T-0 (전환)
- [ ] DNS 제공자(Route53)에서 `patent.sncbears.cloud`
      - `CNAME → cname.vercel-dns.com` (또는 Vercel 제시 값)
- [ ] Vercel에서 도메인 활성 확인 + SSL 자동 발급 대기 (수분)
- [ ] QA 실도메인 스모크 테스트
- [ ] 사용자에게 완료 보고

### T+1시간
- [ ] Vercel/Fly 대시보드 에러율 확인
- [ ] Supabase 로그 확인
- [ ] 사용자 피드백 채널 모니터

### T+48시간
- [ ] AWS 측 트래픽 거의 0 확인 → teardown 착수 가능 판단

## 3. DNS 전환 구체

기존: `patent.sncbears.cloud → CloudFront → S3/API Gateway`
신규: `patent.sncbears.cloud → Vercel → (api/ 는 Vercel Functions, 정적은 Vercel Edge)`

### Route53 설정
```
Type: CNAME (또는 A + Vercel Anycast)
Value: cname.vercel-dns.com
TTL: 300
```
Vercel 대시보드가 제시하는 정확한 값을 사용할 것.

## 4. AWS Teardown 스크립트 (`_workspace/teardown/aws_teardown.sh`)

**드라이런 우선.** 각 단계는 에코만 하고 사용자가 주석을 풀어 실행.

```bash
#!/usr/bin/env bash
set -euo pipefail
REGION=ap-northeast-2
STACK=patent-helper-prod

echo "=== [DRY RUN] AWS Teardown Plan ==="

echo "1) CloudFront 배포 비활성화 (수동 권장)"
echo "   aws cloudfront get-distribution --id <DIST_ID>"
# aws cloudfront update-distribution ... (비활성화는 수동 편집 권장)

echo "2) API Gateway 삭제"
echo "   aws apigateway get-rest-apis --region $REGION"
# aws apigateway delete-rest-api --rest-api-id <ID>

echo "3) Lambda 함수 6개 삭제"
for fn in extract-mappings process-mappings status result history image-proxy; do
  echo "   aws lambda delete-function --function-name ${STACK}-${fn}"
done

echo "4) ECS 서비스 중지 & 태스크 정의 비활성"
echo "   aws ecs update-service --cluster ... --service ... --desired-count 0"
echo "   aws ecs delete-service --cluster ... --service ... --force"

echo "5) ECR 이미지 리포 삭제"
for r in patent-extractor patent-ocr; do
  echo "   aws ecr delete-repository --repository-name $r --force"
done

echo "6) S3 버킷 비우기 + 삭제 (clean cutover)"
echo "   ⚠️ 사용자 확인 필수"
echo "   aws s3 rm s3://patent-helper-... --recursive"
echo "   aws s3 rb s3://patent-helper-... --force"

echo "7) DynamoDB 테이블 삭제"
echo "   aws dynamodb delete-table --table-name patent-helper-jobs"

echo "8) IAM 역할/정책 정리"
echo "   (ExecutionRole, TaskRole, LambdaRole 확인 후 detach + delete)"

echo "9) Route53 레코드 정리"
echo "   (Vercel로 이미 전환됨, 잔재 확인)"

echo "=== DRY RUN 완료. 실제 실행은 각 라인 주석 해제 후 재실행. ==="
```

## 5. Teardown 순서 (의존 역순)
1. CloudFront 배포 비활성화/삭제
2. API Gateway 삭제
3. Lambda 함수 삭제
4. ECS 서비스/태스크 정의/클러스터 정리
5. ECR 이미지 리포 삭제
6. S3 버킷 정리 (사용자 최종 승인)
7. DynamoDB 테이블 삭제
8. IAM 역할/정책 정리
9. Route53 잔재 레코드 정리
10. SAM 배포용 S3 bucket 정리

## 6. 롤백 시나리오
cutover 후 치명적 장애 발견:
1. DNS를 CloudFront 도메인으로 되돌림 (TTL 300초였으므로 5분 내 전파)
2. Vercel/Fly는 유지 (수정 후 재전환)
3. AWS teardown은 보류

## 검증 체크리스트
- [ ] 새 GitHub Actions 워크플로우가 main push에 올바르게 트리거됨
- [ ] Fly 배포 로그에 이미지 빌드/전송 확인
- [ ] Vercel 프로젝트 설정이 환경변수 포함해 정확
- [ ] teardown 스크립트는 실제 파괴 명령이 모두 주석 처리됨
- [ ] `sam deploy` 문자열이 어떤 스크립트에도 없음

## 출력
- `_workspace/ci/.github/workflows/deploy-fly-extractor.yml`
- `_workspace/ci/.github/workflows/deploy-fly-ocr.yml`
- `_workspace/cutover/T-minus_checklist.md`
- `_workspace/cutover/dns_migration.md`
- `_workspace/teardown/aws_teardown.sh` (실행 권한)
- `_workspace/teardown/README.md`
