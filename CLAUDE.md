## 기본 규칙
- 실행 결과는 모두 한글로 알려줘. 
- 중간 진행 사항도 모두 한글로 알려줘.

## 핵심 기능
- 특허문서 관련 PDF파일을 입력 받아서, 내용 중에 도면을 추출해 제공합니다.
- 추출된 도면에는 도면 번호가 포함되어 있습니다.
- 추출된 도면은 별도의 이미지 파일로 저장됩니다.
- 추출된 도면에는 각 부위별로 넘버링이되어 있는데, 이 넘버링은 PDF 파일에 설명이 되어 있음.
- 추출된 도면에 넘버링 부분에 "명칭"을 추가하여, 새로운 이미지로 저장합니다.

## 아키텍처

### 레이어드 아키텍처 (Layered Architecture)
```
┌─────────────────────────────────────────┐
│         Frontend (Vue.js)                │
│  - PDF 업로드 인터페이스                │
│  - 이미지 갤러리 뷰                     │
│  - 반응형 UI 컴포넌트                   │
└─────────────────────────────────────────┘
                    ↓ HTTP/REST
┌─────────────────────────────────────────┐
│      Backend API (FastAPI)              │
│  - REST endpoints                       │
│  - Request/Response handling            │
│  - File upload processing               │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       Business Logic Layer              │
│  - PDF Processor (PDF 파싱)             │
│  - Image Extractor (도면 추출)          │
│  - Text Analyzer (텍스트 분석)          │
│  - Image Annotator (어노테이션)         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│       Data Access Layer                 │
│  - File Storage (로컬 파일시스템)       │
│  - Configuration Management              │
└─────────────────────────────────────────┘
```

### 데이터 플로우
1. **PDF 업로드** → API 엔드포인트
2. **도면 추출** → PDF에서 이미지 추출
3. **OCR 처리** → 도면 번호 및 부품 번호 인식
4. **텍스트 분석** → PDF 텍스트에서 번호-명칭 매핑 추출
5. **이미지 어노테이션** → 번호 위치에 명칭 추가
6. **결과 저장** → 원본 및 어노테이션 이미지 저장

## 폴더 구조

```
PatentHelper/
├── app/                      # 백엔드 애플리케이션 코드
│   ├── __init__.py
│   ├── api/                  # API 레이어
│   │   ├── __init__.py
│   │   └── endpoints.py      # FastAPI 라우트 정의
│   ├── core/                 # 핵심 비즈니스 로직
│   │   ├── __init__.py
│   │   └── pdf_processor.py  # PDF 처리 모듈
│   ├── services/             # 서비스 레이어
│   │   ├── __init__.py
│   │   ├── image_extractor.py    # 이미지 추출 및 OCR
│   │   ├── text_analyzer.py      # 텍스트 분석
│   │   └── image_annotator.py    # 이미지 어노테이션
│   ├── models/               # 데이터 모델
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic 스키마
│   ├── config/               # 설정 관리
│   │   ├── __init__.py
│   │   └── settings.py       # 환경 설정
│   └── utils/                # 유틸리티
│       └── __init__.py
├── front/                    # 프론트엔드 (Vue.js)
│   ├── src/
│   │   ├── App.vue          # 메인 Vue 컴포넌트
│   │   ├── main.js          # 애플리케이션 진입점
│   │   └── style.css        # 글로벌 스타일
│   ├── index.html           # HTML 템플릿
│   ├── vite.config.js       # Vite 설정
│   ├── package.json         # Node.js 의존성
│   └── node_modules/        # NPM 패키지
├── data/                     # 데이터 저장소
│   ├── input/                # 업로드된 PDF 파일
│   └── output/
│       ├── images/           # 추출된 원본 도면
│       └── annotated/        # 어노테이션된 도면
├── logs/                     # 로그 파일
├── tests/                    # 테스트 코드
├── main.py                   # 백엔드 진입점
├── test_ocr.py              # OCR 테스트 스크립트
├── test_patent_diagram.png  # 테스트 이미지
├── requirements.txt          # Python 패키지 의존성
├── .env.example              # 환경변수 예시
├── .env                      # 환경 설정
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

## API 엔드포인트

- `POST /api/v1/process` - PDF 업로드 및 처리
- `GET /api/v1/status` - 서비스 상태 확인
- `GET /api/v1/images/{filename}` - 이미지 조회
- `GET /api/v1/list-images` - 이미지 목록 조회
- `DELETE /api/v1/cleanup` - 임시 파일 정리

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

## 현재 상태
- ✅ 백엔드 서버 정상 작동 중 (FastAPI)
- ✅ 프론트엔드 서버 정상 작동 중 (Vue.js)
- ✅ OCR 기능 활성화 (EasyOCR 설치 완료)
- ✅ 한국어/영어 텍스트 인식 지원
- ✅ PDF 업로드 및 도면 추출 기능
- ✅ 이미지 리스트 표시 및 어노테이션
- ✅ 반응형 UI 디자인