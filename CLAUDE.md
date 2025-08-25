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
- 이미지 영역 테두리: 빨간색 → 진한 회색 (#333333)
- "Image Area" 텍스트: 빨간색 → 진한 회색 (#333333)
- 좌우 확장 경계선: 파란색 → 중간 회색 (#666666)
- 상하 확장 경계선: 초록색 → 어두운 회색 (#555555)

## 아키텍처

### 클라우드 서버리스 아키텍처 (AWS Serverless + ECS)
```
┌─────────────────────────────────────────┐
│         Frontend (Vue.js)                │
│  - PDF 업로드 인터페이스                │
│  - 이미지 갤러리 뷰 (탭/그리드 통합)    │
│  - 실시간 진행 상황 모니터링             │
│  - 통합 ImageModal (확대/다운로드)       │
│  - 반응형 UI 컴포넌트                   │
└─────────────────────────────────────────┘
                    ↓ HTTP/REST
┌─────────────────────────────────────────┐
│      AWS Lambda Functions               │
│  - Upload Handler (파일 업로드)          │
│  - Status Checker (작업 상태 확인)       │
│  - Result Fetcher (결과 조회)           │
│  - History Manager (작업 이력)          │
└─────────────────────────────────────────┘
                    ↓ 
┌─────────────────────────────────────────┐
│         AWS ECS Fargate                 │
│  - PDF Processor (PDF 파싱)             │
│  - Image Extractor (도면 추출 + OCR)    │
│  - Text Analyzer (텍스트 분석)          │
│  - Image Annotator (한국어 어노테이션)   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       AWS Cloud Storage                 │
│  - S3 (파일 저장소)                    │
│  - DynamoDB (작업 상태/이력)            │
│  - CloudWatch (로깅/모니터링)           │
└─────────────────────────────────────────┘
```

### 데이터 플로우 (서버리스)
1. **PDF 업로드** → Lambda Upload Handler → S3 저장
2. **작업 시작** → ECS Task 실행 (Fargate)
3. **도면 추출** → PDF에서 이미지 추출 
4. **OCR 처리** → EasyOCR로 도면 번호 및 부품 번호 인식 (한국어 지원)
5. **텍스트 분석** → PDF 텍스트에서 번호-명칭 매핑 추출
6. **이미지 어노테이션** → 유니코드 폰트로 한국어 명칭 추가
7. **결과 저장** → S3 presigned URL로 이미지 저장
8. **상태 업데이트** → DynamoDB에 진행 상황 및 결과 저장
9. **결과 조회** → Lambda Result Fetcher → 프론트엔드 표시

## 폴더 구조

```
PatentHelper/
├── app/                      # 백엔드 애플리케이션 코드 (로컬 개발용)
│   ├── services/             # 서비스 레이어
│   │   ├── image_extractor.py    # 이미지 추출 및 OCR
│   │   ├── text_analyzer.py      # 텍스트 분석
│   │   └── image_annotator.py    # 한국어 어노테이션 (FontManager)
│   └── core/                 # 핵심 비즈니스 로직
│       └── pdf_processor.py  # PDF 처리 모듈
├── front/                    # 프론트엔드 (Vue.js)
│   ├── src/
│   │   ├── views/
│   │   │   ├── MainView.vue        # 메인 페이지 (업로드/결과)
│   │   │   └── JobResultView.vue   # 작업 결과 상세 페이지
│   │   ├── ImageModal.vue          # 통합 이미지 모달 (확대/다운로드)
│   │   ├── App.vue                 # 메인 Vue 컴포넌트
│   │   ├── router.js               # Vue Router 설정
│   │   └── config.js               # API 엔드포인트 설정
│   └── dist/                       # 빌드된 정적 파일
├── deploy_aws/               # AWS 서버리스 배포
│   ├── infrastructure/       # CloudFormation 템플릿
│   │   └── template.yaml     # AWS 인프라 정의
│   ├── lambda/               # Lambda Functions
│   │   ├── upload/           # 파일 업로드 핸들러
│   │   ├── status/           # 작업 상태 확인
│   │   ├── result/           # 결과 조회
│   │   ├── history/          # 작업 이력 관리
│   │   └── image-proxy/      # 이미지 프록시
│   ├── ecs/                  # ECS Fargate 처리 컨테이너
│   │   ├── Dockerfile        # 유니코드 폰트 + Python 환경
│   │   ├── app/              # 처리 로직 (app/ 복사본)
│   │   ├── processor/        # ECS 메인 처리기
│   │   └── requirements.txt  # Python 의존성
│   ├── frontend/             # 프론트엔드 빌드 설정
│   └── scripts/              # 배포 스크립트
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
- **Python 3.10+** - 메인 개발 언어

#### 웹 프레임워크
- **FastAPI** - 고성능 비동기 웹 프레임워크
- **Uvicorn** - ASGI 서버
- **Pydantic** - 데이터 검증 및 설정 관리

#### PDF 처리
- **pypdfium2** - PDF 파싱 및 이미지 추출
- **pdfplumber** - PDF 텍스트 추출
- **PyPDF2** - PDF 메타데이터 처리

#### 이미지 처리
- **OpenCV** - 이미지 처리 및 분석
- **Pillow** - 이미지 조작 및 저장
- **NumPy** - 배열 연산

#### OCR (광학 문자 인식)
- **EasyOCR** - 다국어 OCR (한국어/영어 지원) ✅ 설치 완료
- **PyTorch** - EasyOCR 백엔드
- **TorchVision** - 이미지 처리 모델

### 프론트엔드
#### 프레임워크
- **Vue.js 3** - 반응형 UI 프레임워크
- **Vite** - 빌드 도구 및 개발 서버
- **Axios** - HTTP 클라이언트

#### 스타일링
- **CSS3** - 커스텀 스타일링
- **Flexbox/Grid** - 레이아웃

### 개발 도구
- **pytest** - 테스트 프레임워크
- **black** - 코드 포매터
- **python-dotenv** - 환경변수 관리
- **aiofiles** - 비동기 파일 처리

### 선택 이유

1. **Python**: PDF/이미지 처리에 강력한 라이브러리 생태계
2. **FastAPI**: 자동 API 문서화, 타입 안정성, 고성능
3. **pypdfium2**: 크로스 플랫폼 지원, 안정적인 PDF 렌더링
4. **EasyOCR**: 한국어 지원, GPU 가속 옵션, 높은 정확도
5. **Vue.js**: 간단한 학습 곡선, 반응형 UI, 컴포넌트 기반
6. **레이어드 아키텍처**: 관심사 분리, 유지보수 용이, 테스트 가능

## API 엔드포인트 (AWS Lambda)

### 업로드 및 처리
- `POST /upload` - PDF 업로드 및 ECS 작업 시작
- `GET /status/{jobId}` - 작업 상태 실시간 확인
- `GET /result/{jobId}` - 작업 결과 조회 (presigned URLs)
- `GET /history?limit=50` - 작업 이력 조회

### 이미지 서비스
- `GET /images/{key}` - S3 이미지 프록시 (presigned URL 생성)

### 로컬 개발용 (FastAPI)
- `POST /api/v1/process` - PDF 업로드 및 처리
- `GET /api/v1/status` - 서비스 상태 확인
- `GET /api/v1/images/{filename}` - 이미지 조회
- `GET /api/v1/list-images` - 이미지 목록 조회

## 실행 방법

### 백엔드 실행

#### 1. 패키지 설치
```bash
pip install -r requirements.txt
pip install easyocr  # OCR 기능 (필수, PyTorch 포함)
```

#### 2. 환경 설정
```bash
cp .env.example .env
# 필요시 .env 파일 수정
```

#### 3. 서버 실행
```bash
python main.py
# 서버가 http://localhost:8000 에서 실행됨
```

### 프론트엔드 실행

#### 1. 패키지 설치
```bash
cd front
npm install
```

#### 2. 개발 서버 실행
```bash
npm run dev
# 프론트엔드가 http://localhost:3000 에서 실행됨
```

#### 3. 프로덕션 빌드
```bash
npm run build
npm run preview
```

## 사용 방법

1. 브라우저에서 http://localhost:3000 접속
2. PDF 파일 업로드 (드래그&드롭 또는 파일 선택)
3. "도면 추출 시작" 버튼 클릭
4. 추출된 도면 확인
   - 원본 도면 탭: 추출된 원본 이미지
   - 어노테이션 탭: 명칭이 추가된 이미지
5. 이미지 클릭하여 확대 보기

## API 문서
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- API 상태: http://localhost:8000/api/v1/status

## 현재 상태 및 주요 기능

### ✅ 완료된 기능
- **AWS 서버리스 아키텍처**: Lambda + ECS Fargate 기반 클라우드 배포
- **실시간 작업 모니터링**: 진행 상황 실시간 업데이트 (2초 간격 폴링)
- **한국어 텍스트 지원**: 유니코드 폰트 (Noto Sans CJK, DejaVu) + FontManager
- **고급 이미지 뷰어**: ImageModal 컴포넌트 (확대, 다운로드, 형식 변환)
- **통합 UI 경험**: 메인 페이지와 결과 페이지 일관된 디자인
- **작업 이력 관리**: localStorage + DynamoDB 백업
- **반응형 디자인**: 모바일/태블릿 최적화

### 🚀 핵심 개선사항
1. **처리 속도**: 기존 90-120초 → 즉시 시작 (ECS 직접 호출)
2. **한국어 렌더링**: PIL 'latin-1' 오류 완전 해결
3. **UI 일관성**: 이미지 배열/매핑 정보 표시 통일
4. **다운로드 기능**: S3 presigned URL 지원, 다중 형식 변환
5. **에러 핸들링**: 상세한 진행 단계별 오류 처리
6. **도면 어노테이션 최적화**: 
   - 도면 확장 크기를 라벨 너비에 맞춰 최적화
   - 화살표 길이 단축 (30px)으로 깔끔한 표시
   - 상하 여백 추가로 라벨 짤림 방지
   - 오른쪽 라벨 위치 자동 조정으로 완전 표시
7. **정밀한 도면 영역 추출**:
   - 실제 도면 영역만 자동 감지 및 크롭
   - 상하 여백 80px로 대폭 증가하여 잘림 완전 방지
   - 첫 페이지 상단 텍스트 헤더 자동 제외 (텍스트 블록 분석)
   - 텍스트/도면 구분 로직 강화 (숫자, 짧은 라벨 분석)
   - 라벨링 후 재크롭 후처리로 최적 크기 조정

### 📊 기술 스택
- **Frontend**: Vue.js 3 + Vite + Vue Router
- **Backend**: AWS Lambda (Node.js) + ECS Fargate (Python)
- **Processing**: EasyOCR + OpenCV + Pillow + pypdfium2
- **Storage**: AWS S3 + DynamoDB
- **Deployment**: GitHub Actions + CloudFormation

### 🔧 배포 환경
- **AWS 프로덕션**: https://d1k8m3z5xkr8hb.cloudfront.net (서버리스)
- **로컬 개발**: http://localhost:3000 (프론트엔드) + http://localhost:8000 (백엔드)