# PatentHelper

특허 문서 PDF에서 도면을 추출하고 각 부품 번호에 명칭을 자동으로 추가하는 시스템

## 주요 기능

- PDF 파일에서 도면 이미지 자동 추출
- 도면 번호 자동 인식
- PDF 텍스트에서 부품 번호-명칭 매핑 추출
- 도면 내 번호 위치에 명칭 자동 어노테이션
- 원본과 어노테이션된 이미지 저장

## 설치 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 변경
```

## 실행 방법

### 서버 시작

```bash
python main.py
```

서버는 기본적으로 http://localhost:8000 에서 실행됩니다.

### API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 엔드포인트

### PDF 처리

```
POST /api/v1/process
```

특허 PDF 파일을 업로드하여 처리합니다.

### 상태 확인

```
GET /api/v1/status
```

### 이미지 조회

```
GET /api/v1/images/{filename}
```

### 이미지 목록

```
GET /api/v1/list-images
```

### 파일 정리

```
DELETE /api/v1/cleanup
```

## 폴더 구조

```
PatentHelper/
├── app/
│   ├── api/          # API 엔드포인트
│   ├── core/         # 핵심 처리 모듈
│   ├── services/     # 비즈니스 로직
│   ├── models/       # 데이터 모델
│   └── config/       # 설정
├── data/
│   ├── input/        # 업로드된 PDF
│   └── output/
│       ├── images/   # 추출된 도면
│       └── annotated/# 어노테이션된 도면
├── logs/             # 로그 파일
└── tests/            # 테스트
```

## 사용 예시

```python
import requests

# PDF 업로드 및 처리
with open("patent.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/process",
        files={"file": f}
    )
    
result = response.json()
print(f"추출된 이미지: {len(result['extracted_images'])}개")
print(f"발견된 번호-명칭 매핑: {len(result['number_mappings'])}개")
```

## 배포 (Deployment)

### 서버 배포
소스 코드 변경 후 OCI 서버에 배포하려면:

```bash
./deploy.sh
```

이 스크립트는 다음 작업을 수행합니다:
- 프론트엔드 빌드 (npm run build)
- 필요한 파일들을 서버로 업로드
- Docker 컨테이너 재빌드 및 재시작
- 서비스 상태 확인

### SSL 인증서 설정
HTTPS를 위한 SSL 인증서 설정 (최초 1회만):

```bash
./init-letsencrypt.sh
```

### 배포 관련 스크립트 설명

| 스크립트 | 설명 | 사용 시기 |
|---------|------|----------|
| `deploy.sh` | 메인 배포 스크립트 | 코드 변경 후 서버에 배포할 때 |
| `init-letsencrypt.sh` | SSL 인증서 설정 | 최초 HTTPS 설정 시 |
| `docker-compose.prod.yml` | 프로덕션 Docker 설정 | 서버에서 사용 |
| `nginx-system.conf` | HTTP nginx 설정 | 서버 nginx 설정 |
| `nginx-system-ssl.conf` | HTTPS nginx 설정 | SSL 적용 후 사용 |

### 서버 접속
```bash
ssh -i ~/.ssh/ssh-key-2025-08-19.key ubuntu@patent.sncbears.cloud
```

### 서비스 URL
- HTTP: http://patent.sncbears.cloud (자동으로 HTTPS로 리다이렉트)
- HTTPS: https://patent.sncbears.cloud

## etc
- 서버 IP: 152.67.211.0