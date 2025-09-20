## 기본 규칙
- 실행 결과는 모두 한글로 알려줘. 
- 중간 진행 사항도 모두 한글로 알려줘.
- Git Push하기 전에 CLAUDE.md,  README.md , tasks 파일 업데이트하고 push해줘
- 

## 핵심 기능
- 특허문서 관련 PDF파일을 입력 받아서, 내용 중에 도면을 추출해 제공합니다.
- 추출된 도면에는 도면 번호가 포함되어 있습니다 ("도 1", "도 2" 형식 포함).
- 추출된 도면은 별도의 이미지 파일로 저장됩니다.
- 추출된 도면에는 각 부위별로 넘버링이되어 있는데, 이 넘버링은 PDF 파일에 설명이 되어 있음.
- 추출된 도면에 넘버링 부분에 "명칭"을 추가하여, 새로운 이미지로 저장합니다.
- **어노테이션된 모든 도면을 하나의 PDF로 생성합니다** ✨ NEW
- 이미지 영역 테두리: 빨간색 → 진한 회색 (#333333)
- "Image Area" 텍스트: 빨간색 → 진한 회색 (#333333)
- 좌우 확장 경계선: 파란색 → 중간 회색 (#666666)
- 상하 확장 경계선: 초록색 → 어두운 회색 (#555555)

## 핵심 원칙
- **/app 폴더 아래의 서버 핵심 로직을 관리**하며, 로컬 실행 시와 AWS 등의 환경에서도 핵심 로직은 이 폴더에서 관리
- ECS 컨테이너는 /app 폴더의 서비스를 그대로 사용하고, AWS 연동 코드만 추가
- 코드 중복 최소화 및 일관성 유지
- 모든 작업은 로컬 환경과 AWS 환경을 고려하여, 양쪽 환경에서 동일하게 동작할 수 있도록 분기 처리에 유의


## 핵심 배포 원칙
### AWS
- **Lambda 업데이트**: `update-lambda.sh` 스크립트를 사용하여 개별적으로 진행 (권장)
- **CloudFront**: 커스텀 도메인 patent.sncbears.cloud 사용 중 (ACM 인증서 포함)

### ⚠️ CloudFront 배포 주의사항 (매우 중요!)
- **절대 SAM deploy를 사용하지 마세요!** CloudFront 설정이 덮어써집니다.
- **문제점**:
  - CloudFormation/SAM은 선언적 방식으로 작동하여 template.yaml에 없는 설정은 삭제됨
  - AWS Console에서 수동 추가한 behavior들이 사라짐
  - CloudFront는 부분 업데이트가 불가능하여 전체 설정이 교체됨
- **현재 필수 CloudFront Behaviors**:
  - `results/*` → DocumentsOrigin
  - `edited/*` → DocumentsOrigin
  - `uploads/*` → DocumentsOrigin
- **해결 방법**:
  - Lambda 함수만 업데이트: `./update-lambda.sh` 사용 (안전)
  - CloudFront 수정 필요 시: AWS Console에서 직접 수정
  - 절대 `sam deploy` 실행 금지
   
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
│   ├── ecs-extractor/        # 매핑 추출 컨테이너 (래퍼)
│   │   ├── Dockerfile        # 경량 이미지
│   │   ├── processor/        
│   │   │   └── extractor.py  # /app/services 사용 + S3 연동
│   │   └── requirements.txt  # 최소 의존성 (4개)
│   ├── ecs-ocr/              # OCR 처리 컨테이너 (래퍼)
│   │   ├── Dockerfile        # PyTorch + EasyOCR
│   │   ├── processor/        
│   │   │   └── ocr_processor.py  # /app/services 사용 + S3 연동
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
- 가상환경 실행 꼭 확인할 것.
- > api.log로 남길것 
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
- **향상된 매핑 추출**: 복수 매핑, 관형어구/부사구 제거, 인라인 패턴 지원
- **어노테이션 위치 최적화**: 원본 이미지 기준 좌/우 배치
- **크로스 브라우저 다운로드**: CORS 문제 해결, blob 변환 방식 적용

### 🚀 최신 개선사항 (2025.01.20)
1. **재생성 PDF 다운로드 권한 문제 해결**:
   - 한글 파일명을 포함한 PDF 다운로드 시 403 에러 수정
   - S3 presigned URL 생성 방식 도입 (1시간 유효)
   - CloudFront URL 대신 직접 S3 액세스로 권한 문제 해결
   - Lambda 함수에서 presigned URL 자동 생성

2. **UI 구성 개선**:
   - 재생성된 PDF 섹션을 어노테이션 도면 상단으로 이동
   - 추출된 원본 도면을 페이지 최하단으로 재배치
   - 사용자 워크플로우에 맞춰 중요도순 재정렬

### 🚀 이전 개선사항 (2025.09.19)
1. **양방향 회전 감지 기능 추가**:
   - +90도(시계방향)와 -90도(반시계방향) 양방향 회전 시도
   - 각 방향에서 OCR 수행 후 가장 많은 번호를 감지한 방향 선택
   - 회전 상태별 독립적 OCR 처리로 인식률 극대화
   - cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE 사용

2. **개선된 도면 페이지 감지**:
   - 독립 라인 패턴 매칭 방식 도입 (_is_drawing_page 메서드 재작성)
   - 도면 번호가 단독 라인에 있는 경우만 도면으로 인식
   - 텍스트 페이지에서 도면 참조만 있는 경우 정확히 제외
   - "도면의 설명" 등 텍스트만 있는 페이지 필터링

3. **회전 복원 문제 해결**:
   - PIL.Image.rotate() 방향 이해 오류 수정
   - PIL은 양수가 반시계방향임을 정확히 반영
   - +90° 회전 시 PIL에서 90도로 복원
   - -90° 회전 시 PIL에서 -90도로 복원
   - 180도 뒤집힘 문제 완전 해결

4. **기술적 개선**:
   - scipy 의존성 제거 (numpy만으로 엔트로피 계산)
   - batch_annotate 메서드 시그니처 수정 (rotation_status_by_image 파라미터 추가)
   - PDF 병합 실패 시 상세한 에러 로깅 추가 (traceback 포함)
   - UI 텍스트 "어노테이션 PDF" → "완성 PDF 다운로드"로 개선

5. **이전 문제 해결**:
   - DynamoDB 타입 어노테이션 문제 해결 (L/M/S/N 타입 래퍼 처리)
   - pypdfium2 버전 통일 (4.25.0)으로 환경 간 일관성 확보
   - Dockerfile CMD 구문 오류 수정
   - pypdfium2 matrix/scale API 호환성 처리

### 🚀 이전 개선사항 (2025.01.16)
1. **PDF 재생성 페이지 매핑 버그 수정**:
   - 도면이 원본 PDF의 정확한 위치에 치환되도록 수정
   - 파일명에서 페이지 번호 추출 로직 개선 (drawing_020 → 페이지 20)
   - 어노테이션 PDF 생성과 동일한 로직 적용
   - extractedImages 데이터에서 페이지 정보 올바르게 파싱
2. **CloudFront 배포 문제 해결**:
   - SAM deploy 사용 금지 문서화 (DO_NOT_USE_SAM_DEPLOY.md)
   - CloudFront behaviors 수동 관리 필요성 명시
   - uploads/*, edited/* 경로 설정 추가
3. **원본 PDF 다운로드 기능 추가**:
   - 업로드 시 원본 PDF를 S3에 저장
   - DynamoDB에 originalPdfS3Key 필드 추가
   - 작업 이력 상세에서 원본 PDF 다운로드 버튼 제공
   - 원본 PDF가 있는 경우에만 버튼 표시

2. **PDF 재생성 로직 개선**:
   - 원본 PDF 페이지 구조 유지하며 도면만 치환
   - `create_annotated_pdf` 메서드 사용하여 텍스트 페이지 보존
   - bbox 정보를 활용한 정확한 도면 위치 배치
   - extractedImagesMetadata에서 bbox 정보 올바르게 처리

3. **재생성 PDF 상태 표시 개선**:
   - "재생성중" / "재생성완료" 태그 분리
   - 애니메이션 효과로 진행 상태 시각화
   - 재생성 완료 시 자동 상태 업데이트

### 🚀 이전 개선사항 (2025.01.15)
1. **이미지 편집 기능 개선**:
   - 편집된 이미지 인덱스 문제 해결 (문자열 키 일관성)
   - 여러 이미지 편집 시 각각 고유하게 저장
   - 새로고침 후에도 편집 내용 유지
   - Fabric.js 텍스트 편집 모드 버그 수정
2. **CORS 및 API 안정성**:
   - save-edited-image Lambda CORS 설정 추가
   - regenerate-pdf Lambda CORS 설정 추가
   - ECS 컨테이너 이름 불일치 문제 해결
3. **UI/UX 개선**:
   - 이미지 에디터 핸들 클릭 영역 개선
   - 텍스트 편집 시 백스페이스 동작 수정
   - 버튼 레이블 "취소" → "닫기" 변경

### 🚀 이전 개선사항 (2025.01.14 밤)
1. **PDF 병합 문제 완전 해결**:
   - bbox 정보를 DynamoDB에 저장 (Decimal 타입 변환)
   - 페이지 인덱싱 오류 수정 (0-indexed vs 1-indexed)
   - 도면 크기 자동 조정 (원본 영역 내 최적화)
   - 모든 페이지 유지 (마지막 페이지 누락 해결)
2. **환경 분리 최적화**:
   - 로컬: /app/config/settings.py로 설정 관리
   - AWS: 환경 변수로 설정 관리
   - 핵심 로직은 /app 폴더에서 공유
3. **안정성 개선**:
   - float-Decimal 타입 자동 변환
   - 페이지 번호 매핑 정확도 향상
   - 에러 메시지 명확화

### 🚀 이전 개선사항 (2025.01.14 오전)
1. **텍스트 추출 개선**:
   - 영어-한글 혼합 용어 지원 (예: CFD시뮬레이션)
   - 하이픈 번호 패턴 지원 (111a-1, 111a-2 등)
   - 지시형용사구 자동 제거 ("이와 같은", "동일한" 등)
   - 긴 레이블 우선 선택으로 정확도 향상
2. **OCR 인식률 개선**:
   - 적응형 스케일링 도입 (이미지 크기별 최적 배율)
   - 작은 이미지(<1000px): 2.5배
   - 중간 이미지(1000-2000px): 2.0-2.2배
   - 큰 이미지(≥2000px): 1.5배
3. **도면 영역 감지**:
   - 다중 도면 영역 자동 감지 (Y좌표 클러스터링)
   - 도면별 중심점 계산으로 라벨 위치 정확도 향상
4. **매핑 추출 정확도 향상**:
   - 한 줄에 여러 매핑 동시 추출 (non-greedy 패턴)
   - 관형어구/부사구 자동 제거
   - 공백 2개 초과 시 제외 처리

### 🚀 이전 개선사항 (2025.01.13)
1. **컨테이너 최적화**:
   - Extractor: 4개 라이브러리만 사용 (빠른 시작)
   - OCR: 6개 라이브러리 (필수 기능만)
2. **PDF 생성 기능**: OCR 처리 후 자동으로 PDF 생성
3. **GitHub Actions 분리**: 각 컨테이너 독립 배포
4. **메타데이터 관리**: DynamoDB로 단계 간 데이터 전달
5. **Lambda 함수 성능 개선**:
   - ExtractMappings: 메모리 3GB, 타임아웃 5분
   - ProcessMappings: 메모리 10GB (최대), 타임아웃 15분 (최대)
6. **CloudFront 커스텀 도메인**: patent.sncbears.cloud
7. **대용량 파일 업로드 지원**: S3 사전 서명 URL 방식으로 API Gateway 제한 우회
8. **작업 이력 기능 개선**:
   - 로컬 환경에서 localStorage 활용
   - 일관된 jobId 관리로 PDF URL 추적 개선
   - 작업 이력에서 완료된 작업 상세보기 시 결과 즉시 표시
9. **UI/UX 개선**:
   - 이미지 모달 NaN 표시 문제 해결
   - 크로스 오리진 이미지 다운로드 지원

### 📊 성능 지표
- **Extractor 시작 시간**: ~10초
- **OCR 처리 시간**: 이미지당 ~5-10초
- **PDF 생성**: ~5초
- **전체 처리 시간**: 30-60초 (PDF 크기에 따라)

### 🔧 배포 환경
- **AWS 프로덕션**: https://patent.sncbears.cloud
- **CloudFront 도메인**: d38f9rplbkj0f2.cloudfront.net
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
- /app 폴더 아래의 서버 핵심 로직을 관리하며, 로컬 실행 시와 AWS 등의 환경에서도 핵심 로직은 이 폴더에서 관리해야 함.
- python은 가상환경에서 실행되어야 함.
- 앞으로 오늘을 계산할 때는 시스템의 날짜를 기준으로 할 것