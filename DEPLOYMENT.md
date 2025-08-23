# PatentHelper 배포 가이드

## 🚀 OCI 서버 배포

### 사전 요구사항
- OCI 서버 (Ubuntu 20.04 이상 권장)
- Docker 및 Docker Compose 설치
- 도메인 설정 (patent.sncbears.com)

### 서버 초기 설정

1. **Docker 설치** (서버에서 실행)
```bash
# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

2. **방화벽 설정**
```bash
# HTTP/HTTPS 포트 열기
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
```

### 배포 방법

#### 방법 1: 자동 배포 스크립트 사용 (권장)

로컬에서:
```bash
# 배포 스크립트 실행
./deploy.sh
```

#### 방법 2: 수동 배포

1. **코드 업로드**
```bash
# 로컬에서
rsync -avz --exclude 'node_modules' --exclude 'data' --exclude '.git' \
  . ubuntu@patent.sncbears.com:/home/ubuntu/PatentHelper/
```

2. **서버에서 Docker 컨테이너 실행**
```bash
# 서버에 SSH 접속
ssh ubuntu@patent.sncbears.com

# 프로젝트 디렉토리로 이동
cd /home/ubuntu/PatentHelper

# 컨테이너 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f
```

### 유지보수 명령어

#### 컨테이너 상태 확인
```bash
docker-compose ps
```

#### 로그 확인
```bash
# 전체 로그
docker-compose logs -f

# 백엔드 로그만
docker-compose logs -f backend

# 프론트엔드 로그만
docker-compose logs -f frontend
```

#### 재시작
```bash
docker-compose restart
```

#### 중지
```bash
docker-compose down
```

#### 업데이트 배포
```bash
# 코드 업데이트 후
docker-compose down
docker-compose up -d --build
```

### SSL 인증서 설정 (HTTPS)

Certbot을 사용한 Let's Encrypt SSL 설정:

1. **Certbot 설치**
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

2. **SSL 인증서 발급**
```bash
sudo certbot --nginx -d patent.sncbears.com
```

3. **자동 갱신 설정**
```bash
sudo systemctl status snap.certbot.renew.service
```

### 모니터링

#### 리소스 사용량 확인
```bash
docker stats
```

#### 디스크 사용량 확인
```bash
df -h
docker system df
```

#### 불필요한 리소스 정리
```bash
docker system prune -a
```

### 백업

#### 데이터 백업
```bash
# 데이터 디렉토리 백업
tar -czf patent-data-$(date +%Y%m%d).tar.gz data/
```

#### 전체 백업
```bash
# 전체 프로젝트 백업
tar -czf patent-helper-$(date +%Y%m%d).tar.gz \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='venv' \
  PatentHelper/
```

### 트러블슈팅

#### 포트 충돌
```bash
# 사용 중인 포트 확인
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :8000
```

#### 메모리 부족
```bash
# 메모리 확인
free -h

# 스왑 추가 (필요시)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### Docker 디스크 공간 부족
```bash
# 정리
docker system prune -a --volumes
```

## 📧 문의

문제가 발생하면 다음으로 연락주세요:
- GitHub Issues: [프로젝트 저장소]
- Email: [이메일 주소]