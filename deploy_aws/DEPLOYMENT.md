# AWS Deployment Guide

## 배포 스크립트 가이드

### 🚀 전체 배포 (초기 설정)
```bash
cd deploy_aws
./deploy.sh
```
- 전체 인프라 구성 (SAM Stack, ECS, Lambda, S3, CloudFront)
- 처음 배포할 때 사용

### ⚡ 빠른 배포 (Lambda + Frontend)
```bash
cd deploy_aws
./deploy-quick.sh
```
- Lambda 함수와 프론트엔드만 배포
- ECS는 GitHub Actions가 자동으로 처리

### 🎨 프론트엔드만 업데이트
```bash
cd deploy_aws
./update-frontend.sh
```
- 프론트엔드 코드만 빌드하고 배포
- CloudFront 캐시 자동 무효화

### 📦 Lambda 함수만 업데이트
```bash
cd deploy_aws
./update-lambda.sh
```
- Lambda 함수 코드만 빠르게 업데이트
- SAM 재배포 없이 함수 코드만 갱신

### 🐳 ECS 컨테이너 업데이트
ECS 컨테이너는 GitHub Actions를 통해 자동으로 배포됩니다:
1. 코드를 `main` 브랜치에 푸시
2. GitHub Actions가 자동으로 Docker 이미지 빌드
3. ECR에 푸시 후 ECS 태스크 정의 업데이트

수동으로 ECS만 빌드하려면:
```bash
cd deploy_aws
./build-and-push.sh  # EC2 인스턴스에서 실행
```

## 환경 변수

배포 시 환경을 지정할 수 있습니다:
```bash
ENV=dev ./deploy-quick.sh    # 개발 환경
ENV=staging ./deploy-quick.sh # 스테이징 환경
ENV=prod ./deploy-quick.sh   # 프로덕션 환경 (기본값)
```

## GitHub Actions 설정

GitHub 저장소 Settings → Secrets에 다음 값들을 추가해야 합니다:
- `AWS_ACCESS_KEY_ID`: AWS 액세스 키
- `AWS_SECRET_ACCESS_KEY`: AWS 시크릿 키

## 배포 순서 권장사항

### 프론트엔드 변경 시
```bash
./update-frontend.sh
```

### Lambda 함수 변경 시
```bash
./update-lambda.sh
```

### ECS 프로세서 변경 시
```bash
git add .
git commit -m "feat: Update processor"
git push origin main
# GitHub Actions가 자동으로 배포
```

### 인프라 변경 시 (새 리소스 추가 등)
```bash
./deploy.sh  # 또는 ./deploy-quick.sh
```

## 서비스 URL 확인

배포 완료 후 출력되는 URL들:
- **Frontend URL**: CloudFront 배포 URL (https://xxxx.cloudfront.net)
- **API URL**: API Gateway URL (https://xxxx.execute-api.region.amazonaws.com/prod)

## 문제 해결

### CloudFront 캐시 문제
```bash
# 수동으로 캐시 무효화
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"
```

### Lambda 함수 로그 확인
```bash
# 특정 Lambda 함수 로그 보기
aws logs tail /aws/lambda/patent-helper-upload-prod --follow
```

### ECS 태스크 로그 확인
```bash
# ECS 태스크 로그 보기
aws logs tail /ecs/patent-helper-ocr-prod --follow
```

## 비용 관리

- ECS Fargate: 실행 시간에 따라 과금
- Lambda: 실행 횟수와 시간에 따라 과금
- S3: 저장 용량과 전송량에 따라 과금
- CloudFront: 전송량에 따라 과금

비용 절감 팁:
1. 개발 환경은 사용 후 리소스 삭제
2. CloudWatch 로그 보관 기간 설정
3. S3 라이프사이클 정책으로 오래된 파일 자동 삭제