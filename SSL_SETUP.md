# 🔒 SSL/HTTPS 설정 가이드

## 빠른 시작

### 1. 첫 배포 (SSL 없이)
```bash
./deploy.sh
```

### 2. SSL 인증서 발급 및 적용
```bash
# init-letsencrypt.sh 파일을 편집하여 이메일 주소 설정
nano init-letsencrypt.sh
# EMAIL="your-email@example.com" 부분을 실제 이메일로 변경

# SSL 인증서 발급 및 설정
./init-letsencrypt.sh
```

### 3. SSL이 적용된 상태로 재배포
```bash
./deploy-ssl.sh
```

## 상세 설명

### SSL 인증서 발급 프로세스

1. **Let's Encrypt 무료 SSL 인증서 사용**
   - 90일마다 자동 갱신
   - 도메인 소유권 검증 필요

2. **발급 과정**
   - HTTP-01 challenge를 통한 도메인 검증
   - 인증서 파일 생성 및 저장
   - Nginx에 SSL 설정 적용

3. **자동 갱신**
   - Certbot 컨테이너가 12시간마다 갱신 체크
   - 만료 30일 전 자동 갱신

### 파일 구조

```
PatentHelper/
├── docker-compose.yml          # 기본 설정 (HTTP only)
├── docker-compose.ssl.yml      # SSL 설정 (HTTP + HTTPS)
├── nginx.conf                  # 기본 Nginx 설정
├── nginx-ssl.conf             # SSL Nginx 설정
├── init-letsencrypt.sh        # SSL 초기 설정 스크립트
├── deploy.sh                  # 기본 배포 스크립트
├── deploy-ssl.sh              # SSL 배포 스크립트
└── certbot/                   # SSL 인증서 저장 디렉토리 (서버에서 생성)
    ├── conf/
    └── www/
```

### 트러블슈팅

#### 인증서 발급 실패
```bash
# 서버에서 로그 확인
ssh -i ~/.ssh/ssh-key-2025-08-19.key ubuntu@patent.sncbears.cloud
cd /home/ubuntu/PatentHelper
docker-compose -f docker-compose.ssl.yml logs certbot
```

#### Rate Limit 문제
Let's Encrypt는 주당 발급 횟수 제한이 있습니다:
- 동일 도메인: 주당 5회
- 테스트 시 `STAGING=1`로 설정하여 테스트 서버 사용

#### 인증서 수동 갱신
```bash
ssh -i ~/.ssh/ssh-key-2025-08-19.key ubuntu@patent.sncbears.cloud
cd /home/ubuntu/PatentHelper
docker-compose -f docker-compose.ssl.yml run --rm certbot renew
docker-compose -f docker-compose.ssl.yml exec nginx nginx -s reload
```

#### SSL 인증서 상태 확인
```bash
# 인증서 만료일 확인
ssh -i ~/.ssh/ssh-key-2025-08-19.key ubuntu@patent.sncbears.cloud
sudo openssl x509 -in /home/ubuntu/PatentHelper/certbot/conf/live/patent.sncbears.cloud/cert.pem -text -noout | grep "Not After"
```

### 보안 헤더

SSL 설정과 함께 다음 보안 헤더가 자동 적용됩니다:
- `Strict-Transport-Security`: HTTPS 강제
- `X-Frame-Options`: Clickjacking 방지
- `X-Content-Type-Options`: MIME 타입 스니핑 방지
- `X-XSS-Protection`: XSS 공격 방지

### HTTP에서 HTTPS로 전환

1. 기존 HTTP 서비스 중지
```bash
ssh -i ~/.ssh/ssh-key-2025-08-19.key ubuntu@patent.sncbears.cloud
cd /home/ubuntu/PatentHelper
docker-compose down
```

2. SSL 인증서 발급
```bash
./init-letsencrypt.sh
```

3. SSL 설정으로 재시작
```bash
docker-compose -f docker-compose.ssl.yml up -d
```

## 🎉 완료!

이제 https://patent.sncbears.cloud 에서 안전하게 서비스에 접속할 수 있습니다.

- 🔒 모든 통신이 암호화됩니다
- ✅ 브라우저에 안전한 사이트로 표시됩니다
- 🔄 인증서가 자동으로 갱신됩니다