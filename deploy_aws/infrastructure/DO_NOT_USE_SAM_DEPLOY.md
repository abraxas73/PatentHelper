# ⚠️ 경고: SAM DEPLOY 사용 금지!

## 절대 `sam deploy`를 실행하지 마세요!

### 문제점
- CloudFront 설정이 완전히 덮어써집니다
- AWS Console에서 수동으로 추가한 behavior들이 삭제됩니다
- 커스텀 도메인 설정이 초기화될 수 있습니다

### 현재 CloudFront에 필요한 Behaviors
1. `results/*` → DocumentsOrigin
2. `edited/*` → DocumentsOrigin
3. `uploads/*` → DocumentsOrigin

### 올바른 배포 방법
```bash
# Lambda 함수만 업데이트 (안전)
cd /Users/seungukkang/Repos/PatentHelper/deploy_aws
./update-lambda.sh

# 프론트엔드만 업데이트 (안전)
./update-frontend.sh
```

### CloudFront 수정이 필요한 경우
1. AWS Console에 로그인
2. CloudFront → 배포 E1OEQMTBUR4JGY
3. Behaviors 탭에서 수동으로 수정
4. 절대 SAM/CloudFormation으로 업데이트하지 말 것

### 이유
- CloudFormation은 선언적(Declarative) 방식
- template.yaml에 정의된 것만 유지하고 나머지는 삭제
- CloudFront는 부분 업데이트 불가능 (전체 교체만 가능)