## 기본 규칙
- 실행 결과는 모두 한글로 알려줘. 
- 중간 진행 사항도 모두 한글로 알려줘.
- Git Push할 때마다. CLAUDE.md,  README.md 파일 내용은 업데이트 해줘

## 핵심 기능
- 특허문서 관련 PDF파일을 입력 받아서, 내용 중에 도면을 추출해 제공합니다.
- 추출된 도면에는 도면 번호가 포함되어 있습니다.
- 추출된 도면은 별도의 이미지 파일로 저장됩니다.
- 추출된 도면에는 각 부위별로 넘버링이되어 있는데, 이 넘버링은 PDF 파일에 설명이 되어 있음.
- 추출된 도면에 넘버링 부분에 "명칭"을 추가하여, 새로운 이미지로 저장합니다.
- **어노테이션된 모든 도면을 하나의 PDF로 생성합니다** ✨ NEW
- 이미지 영역 테두리: 빨간색 → 진한 회색 (#333333)
- "Image Area" 텍스트: 빨간색 → 진한 회색 (#333333)
- 좌우 확장 경계선: 파란색 → 중간 회색 (#666666)
- 상하 확장 경계선: 초록색 → 어두운 회색 (#555555)

## 아키텍처

### 클라우드 서버리스 아키텍처 (AWS Serverless + ECS)
```
┌─────────────────────────────────────────┐
│         Frontend (Vue.js)                │
│  - 2단계 처리 UI (매핑 추출 → OCR)      │
│  - 매핑 편집 인터페이스                 │
│  - 이미지 갤러리 뷰 (탭/그리드 통합)    │
│  - 실시간 진행 상황 모니터링            │
│  - PDF 다운로드 기능                    │
│  - 통합 ImageModal (확대/다운로드)      │
└─────────────────────────────────────────┘
                    ↓ HTTP/REST
┌─────────────────────────────────────────┐
│      AWS Lambda Functions               │
│  - Extract Mappings (매핑 추출 트리거)  │
│  - Process Mappings (OCR 처리 트리거)   │
│  - Status Checker (작업 상태 확인)      │
│  - Result Fetcher (결과 조회)           │
│  - History Manager (작업 이력)          │
└─────────────────────────────────────────┘
                    ↓ 
┌─────────────────────────────────────────┐
│    AWS ECS Fargate (2개 컨테이너)       │
├─────────────────────────────────────────┤
│ 1. Extractor (경량 - 1GB/2GB)           │
│    - PDF 파싱 및 이미지 추출            │
│    - 텍스트 분석 및 매핑 추출           │
│    - 빠른 시작 (PyTorch 없음)          │
├─────────────────────────────────────────┤
│ 2. OCR Processor (무거움 - 4GB/8GB)     │
│    - EasyOCR로 번호 위치 감지           │
│    - 이미지 어노테이션                  │
│    - PDF 생성 (reportlab)               │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       AWS Cloud Storage                 │
│  - S3 (파일 저장소)                    │
│  - DynamoDB (작업 상태/메타데이터)      │
│  - CloudWatch (로깅/모니터링)          │
└─────────────────────────────────────────┘
```

### 2단계 처리 프로세스
1. **1단계: 매핑 추출 (Extractor 컨테이너)**
   - PDF 업로드 → 텍스트/이미지 추출
   - 번호-명칭 매핑 자동 추출
   - 사용자가 매핑 편집 가능
   - DynamoDB에 메타데이터 저장

2. **2단계: OCR 및 PDF 생성 (OCR 컨테이너)**
   - 선택된 매핑으로 OCR 수행
   - 이미지에 어노테이션 추가
   - 어노테이션된 PDF 생성
   - S3에 최종 결과 저장

## 폴더 구조

```
PatentHelper/
├── app/                      # 백엔드 애플리케이션 코드 (로컬 개발용)
│   ├── services/             # 서비스 레이어
│   │   ├── image_extractor.py    # 이미지 추출 및 OCR
│   │   ├── text_analyzer.py      # 텍스트 분석
│   │   ├── image_annotator.py    # 한국어 어노테이션
│   │   └── pdf_generator.py      # PDF 생성
│   └── core/                 # 핵심 비즈니스 로직
│       └── pdf_processor.py  # PDF 처리 모듈
├── front/                    # 프론트엔드 (Vue.js)
│   ├── src/
│   │   ├── views/
│   │   │   ├── MainView.vue        # 메인 페이지 (2단계 처리)
│   │   │   └── JobResultView.vue   # 작업 결과 상세 페이지
│   │   ├── ImageModal.vue          # 통합 이미지 모달
│   │   ├── App.vue                 # 메인 Vue 컴포넌트
│   │   ├── router.js               # Vue Router 설정
│   │   └── config.js               # API 엔드포인트 설정
│   └── dist/                       # 빌드된 정적 파일
├── deploy_aws/               # AWS 서버리스 배포
│   ├── infrastructure/       # CloudFormation 템플릿
│   │   └── template.yaml     # AWS 인프라 정의
│   ├── lambda/               # Lambda Functions
│   │   ├── extract-mappings/ # 매핑 추출 핸들러
│   │   ├── process-mappings/ # OCR 처리 핸들러
│   │   ├── status/           # 작업 상태 확인
│   │   ├── result/           # 결과 조회
│   │   ├── history/          # 작업 이력 관리
│   │   └── image-proxy/      # 이미지 프록시
│   ├── ecs-extractor/        # 매핑 추출 컨테이너
│   │   ├── Dockerfile        # 경량 이미지
│   │   ├── processor/        # 추출 로직
│   │   └── requirements.txt  # 최소 의존성 (4개)
│   ├── ecs-ocr/              # OCR 처리 컨테이너
│   │   ├── Dockerfile        # PyTorch + EasyOCR
│   │   ├── processor/        # OCR 로직
│   │   └── requirements.txt  # OCR 의존성 (6개)
│   └── scripts/              # 배포 스크립트
├── .github/workflows/        # GitHub Actions
│   ├── deploy-ecs-extractor.yml  # Extractor 자동 배포
│   └── deploy-ecs-ocr.yml        # OCR 자동 배포
├── data/                     # 로컬 개발 데이터
├── logs/                     # 로컬 개발 로그
├── tests/                    # 테스트 코드
├── main.py                   # 로컬 개발 서버
├── requirements.txt          # Python 의존성
├── README.md                 # 프로젝트 문서
└── CLAUDE.md                 # 프로젝트 명세
```

## 기술 스택

### 백엔드
#### 프로그래밍 언어
- **Python 3.12** - 메인 개발 언어

#### 웹 프레임워크
- **FastAPI** - 고성능 비동기 웹 프레임워크
- **Uvicorn** - ASGI 서버

#### PDF 처리
- **pypdfium2** - PDF 파싱 및 이미지 추출
- **pdfplumber** - PDF 텍스트 추출
- **reportlab** - PDF 생성

#### 이미지 처리
- **OpenCV** - 이미지 처리 및 분석 (OCR 컨테이너만)
- **Pillow** - 이미지 조작 및 저장
- **NumPy** - 배열 연산 (OCR 컨테이너만)

#### OCR (광학 문자 인식)
- **EasyOCR** - 다국어 OCR (한국어/영어 지원)
- **PyTorch** - EasyOCR 백엔드 (CPU 버전)

### 프론트엔드
#### 프레임워크
- **Vue.js 3** - 반응형 UI 프레임워크
- **Vite** - 빌드 도구 및 개발 서버
- **Vue Router** - SPA 라우팅
- **Axios** - HTTP 클라이언트

#### 스타일링
- **CSS3** - 커스텀 스타일링
- **Flexbox/Grid** - 레이아웃

### AWS 인프라
- **Lambda** - 서버리스 함수 (API 엔드포인트)
- **ECS Fargate** - 컨테이너 실행 (무거운 처리)
- **S3** - 파일 저장소
- **DynamoDB** - NoSQL 데이터베이스
- **CloudFront** - CDN
- **API Gateway** - REST API
- **ECR** - 컨테이너 레지스트리
- **CloudWatch** - 로깅 및 모니터링

### CI/CD
- **GitHub Actions** - 자동 배포
- **SAM (Serverless Application Model)** - 인프라 배포
- **Docker** - 컨테이너화

## 컨테이너 최적화 상세

### Extractor 컨테이너 (경량)
**용도**: PDF 분석 및 매핑 추출
**리소스**: CPU 1024, Memory 2048MB
**의존성** (4개만):
- pypdfium2 (PDF 처리)
- pdfplumber (텍스트 추출)
- Pillow (이미지 처리)
- boto3 (AWS 연동)

### OCR 컨테이너 (무거움)
**용도**: OCR 처리 및 PDF 생성
**리소스**: CPU 4096, Memory 8192MB
**의존성** (6개):
- easyocr (OCR 엔진)
- opencv-python (이미지 전처리)
- Pillow (이미지 처리)
- numpy (배열 연산)
- boto3 (AWS 연동)
- reportlab (PDF 생성)

## API 엔드포인트

### AWS Lambda 엔드포인트
- `POST /extract-mappings` - 매핑 추출 시작
- `POST /process-with-mappings` - OCR 처리 시작
- `GET /status/{jobId}` - 작업 상태 확인
- `GET /result/{jobId}` - 작업 결과 조회
- `GET /history` - 작업 이력 조회
- `GET /images/{key}` - S3 이미지 프록시

### 로컬 개발 엔드포인트
- `POST /api/v1/extract-mappings` - 매핑 추출
- `POST /api/v1/process-with-mappings` - OCR 처리
- `GET /api/v1/status` - 서비스 상태
- `GET /api/v1/images/{filename}` - 이미지 조회

## 실행 방법

### 로컬 개발 환경

#### 1. 백엔드 실행
```bash
# 프로젝트 루트에서
pip install -r requirements.txt
python main.py
# http://localhost:8000에서 실행
```

#### 2. 프론트엔드 실행
```bash
cd front
npm install
npm run dev
# http://localhost:3000에서 실행
```

### AWS 배포

#### Lambda 함수 배포
```bash
cd deploy_aws/infrastructure
sam build
sam deploy --stack-name patent-helper-prod \
  --s3-bucket patent-helper-sam-deploy-857201044807 \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-2
```

#### 프론트엔드 배포
```bash
cd deploy_aws
./update-frontend.sh
```

#### ECS 컨테이너 배포
GitHub에 푸시하면 GitHub Actions가 자동으로 배포

## 사용 방법

### 1단계: 매핑 추출
1. PDF 파일 업로드
2. 자동으로 번호-명칭 매핑 추출
3. 매핑 정보 편집 가능
   - 체크박스로 선택/해제
   - 명칭 수정
   - 새 매핑 추가
   - 불필요한 매핑 삭제

### 2단계: OCR 처리
1. 편집된 매핑으로 OCR 시작
2. 선택된 번호만 어노테이션
3. 어노테이션된 이미지 생성
4. 모든 이미지를 하나의 PDF로 생성

### 결과 확인
- 원본 도면 탭: 추출된 원본 이미지
- 어노테이션 탭: 명칭이 추가된 이미지
- PDF 다운로드: 어노테이션된 전체 PDF

## 현재 상태 및 주요 기능

### ✅ 완료된 기능
- **2단계 처리 프로세스**: 매핑 추출 → OCR 처리
- **컨테이너 분리**: 경량 Extractor + 무거운 OCR
- **매핑 편집 UI**: 체크박스, 수정, 추가, 삭제
- **PDF 생성**: 어노테이션된 모든 이미지를 하나의 PDF로
- **실시간 모니터링**: 진행 상황 실시간 업데이트
- **자동 배포**: GitHub Actions로 컨테이너 자동 빌드/배포
- **한국어 완벽 지원**: 폰트 및 인코딩 문제 해결

### 🚀 최신 개선사항
1. **컨테이너 최적화**: 
   - Extractor: 4개 라이브러리만 사용 (빠른 시작)
   - OCR: 6개 라이브러리 (필수 기능만)
2. **PDF 생성 기능**: OCR 처리 후 자동으로 PDF 생성
3. **GitHub Actions 분리**: 각 컨테이너 독립 배포
4. **메타데이터 관리**: DynamoDB로 단계 간 데이터 전달

### 📊 성능 지표
- **Extractor 시작 시간**: ~10초
- **OCR 처리 시간**: 이미지당 ~5-10초
- **PDF 생성**: ~5초
- **전체 처리 시간**: 30-60초 (PDF 크기에 따라)

### 🔧 배포 환경
- **AWS 프로덕션**: https://d38f9rplbkj0f2.cloudfront.net
- **API Gateway**: https://ginihhv5d6.execute-api.ap-northeast-2.amazonaws.com/prod
- **로컬 개발**: http://localhost:3000 (프론트) + http://localhost:8000 (백엔드)

## 문제 해결

### 일반적인 문제
1. **ECS 태스크 실행 권한 오류**: Lambda IAM 역할에 ECS RunTask 권한 추가
2. **모듈 없음 오류**: requirements.txt 확인 및 컨테이너 재빌드
3. **PDF 생성 실패**: reportlab 설치 확인

### 디버깅
- CloudWatch Logs에서 ECS 컨테이너 로그 확인
- Lambda 함수 로그 확인
- DynamoDB에서 작업 상태 확인

## 향후 계획
- [ ] 배치 처리 기능
- [ ] 사용자 인증 추가
- [ ] 처리 결과 이메일 알림
- [ ] 다국어 OCR 지원 확대