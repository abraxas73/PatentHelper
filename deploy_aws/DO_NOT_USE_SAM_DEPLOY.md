# ⚠️ 절대 SAM DEPLOY 사용 금지 ⚠️

## 문제점
`sam deploy` 또는 `deploy-quick.sh`를 사용하면 IAM 권한이 초기화됩니다!

## 발생하는 문제들
1. **S3 권한 손실**: ECS 태스크가 S3에 접근할 수 없게 됨
2. **PDF 병합 실패**: "원본 PDF 병합 실패" 오류 발생
3. **수동 설정 초기화**: AWS Console에서 수동으로 추가한 설정이 모두 사라짐

## 올바른 배포 방법

### Lambda 함수만 업데이트 (권장) ✅
```bash
./update-lambda.sh
```

### 프론트엔드만 업데이트 ✅
```bash
./update-frontend.sh
```

### ECS 컨테이너 업데이트 ✅
GitHub에 푸시하면 GitHub Actions가 자동으로 처리

### 권한 문제 발생 시 ✅
```bash
./fix-ecs-permissions.sh
```

## 절대 사용하지 마세요 ❌
- `sam deploy`
- `./deploy-quick.sh`
- CloudFormation 스택 업데이트

## 이유
CloudFormation/SAM은 선언적 방식으로 작동하여:
- template.yaml에 없는 설정은 삭제됨
- AWS Console에서 수동 추가한 설정이 덮어써짐
- IAM 정책이 이전 버전으로 롤백될 수 있음

## 현재 상태
- ECS Task Role에 `s3:ListBucket` 권한이 수동으로 추가됨
- 이 권한이 없으면 PDF 병합이 실패함
- `sam deploy`를 실행하면 이 권한이 사라짐

---
최종 업데이트: 2025-09-19