# PatentHelper 🔬

**특허 문서 PDF에서 도면을 추출하고 각 부품 번호에 한국어 명칭을 자동으로 추가하는 AI 기반 시스템**

[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-orange.svg)](https://aws.amazon.com/serverless/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)](https://vuejs.org/)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org/)
[![EasyOCR](https://img.shields.io/badge/EasyOCR-Korean-green.svg)](https://github.com/JaidedAI/EasyOCR)

## ✨ 주요 기능

### 🤖 AI 기반 처리
- **도면 자동 추출**: "도면[숫자]" 패턴이 있는 페이지만 정확히 추출
- **향상된 OCR**: 적응형 스케일링으로 인식률 개선 (2025.01.14 업데이트)
- **텍스트 분석**: 영어-한글 혼합 용어 및 하이픈 번호 지원 (111a-1, CFD시뮬레이션 등)
- **스마트 어노테이션**: 다중 도면 영역 감지, 도면별 중심점 기반 라벨 배치

### 🎨 고급 사용자 인터페이스
- **실시간 진행 모니터링**: 2초 간격 상태 업데이트
- **통합 이미지 뷰어**: 확대, 다운로드, 형식 변환 지원
- **반응형 디자인**: 모바일/태블릿 최적화
- **작업 이력 관리**: 로컬 + 클라우드 백업

### ☁️ 클라우드 서버리스 아키텍처
- **즉시 처리**: Lambda + ECS Fargate로 대기 시간 최소화
- **자동 확장**: AWS 관리형 서비스로 트래픽 자동 처리
- **안정적 저장**: S3 + DynamoDB 기반 데이터 보관

## 🚀 빠른 시작

### 프로덕션 사용 (권장)
**AWS 서버리스 버전**: https://patent.sncbears.cloud

1. 웹사이트 접속
2. PDF 파일 업로드 (드래그&드롭 또는 파일 선택)
3. "도면 추출 시작" 버튼 클릭
4. 실시간 진행 상황 모니터링
5. 추출된 도면 및 어노테이션 결과 확인

### 로컬 개발 환경

#### 백엔드 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 설정
cp .env.example .env

# 서버 시작
python main.py
# → http://localhost:8000
```

#### 프론트엔드 설정
```bash
# 프론트엔드 디렉토리 이동
cd front

# 의존성 설치
npm install

# 개발 서버 시작
npm run dev
# → http://localhost:3000
```

## 📡 API 엔드포인트

### AWS 프로덕션 API
```bash
# 파일 업로드 및 처리 시작
POST https://api-url/upload

# 작업 상태 확인 (실시간)
GET https://api-url/status/{jobId}

# 작업 결과 조회
GET https://api-url/result/{jobId}

# 작업 이력 조회
GET https://api-url/history?limit=50

# 이미지 프록시 (S3 presigned URL)
GET https://api-url/images/{key}
```

### 로컬 개발 API
```bash
# 매핑 추출 (1단계)
POST http://localhost:8000/api/v1/extract-mappings

# OCR 처리 (2단계)
POST http://localhost:8000/api/v1/process-with-mappings

# PDF 생성
POST http://localhost:8000/api/v1/generate-pdf

# PDF 다운로드
GET http://localhost:8000/api/v1/download-pdf/{filename}

# 이미지 조회
GET http://localhost:8000/api/v1/images/{filename}

# 서비스 상태 확인
GET http://localhost:8000/api/v1/status

# API 문서
GET http://localhost:8000/docs (Swagger UI)
GET http://localhost:8000/redoc (ReDoc)
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

## 최근 업데이트 (2025-08-24)

### 도면 어노테이션 최적화
- **왼쪽 라벨 영역 최적화**: 영역 10% 축소, 화살표 길이 15px로 단축
- **오른쪽 라벨 영역 확장**: 원본 이미지 너비의 10% 추가 확장으로 라벨 잘림 방지
- **상단 텍스트 자동 제거**: 라벨링 후 상단 텍스트 영역 자동 크롭 처리
- **좌우 비대칭 확장**: 라벨 위치에 따른 최적화된 공간 활용

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

## 🚀 배포 및 인프라

### 프로덕션 환경 (AWS)
- **프론트엔드**: CloudFront + S3 정적 호스팅
- **백엔드**: API Gateway + Lambda Functions
- **처리엔진**: ECS Fargate (on-demand)
- **저장소**: S3 (파일) + DynamoDB (메타데이터)
- **모니터링**: CloudWatch Logs

#### AWS 배포 명령어
```bash
# 전체 인프라 배포
cd deploy_aws
./deploy.sh

# 프론트엔드만 업데이트
./update-frontend.sh

# Lambda 함수만 업데이트
./update-lambda.sh
```


### 📊 성능 및 비용 최적화
- **Cold Start**: ~5-10초 (vs 이전 90-120초)
- **Auto Scaling**: 트래픽에 따른 자동 확장/축소
- **비용 효율성**: 사용량 기반 과금 (무료 티어 활용)
- **고가용성**: Multi-AZ 배포로 99.9% 가용성

### 🔧 개발자 도구
```bash
# 로컬 테스트
npm run dev          # 프론트엔드 개발 서버
python main.py       # 백엔드 개발 서버

# AWS 리소스 검증
cd deploy_aws
./validate.sh        # CloudFormation 템플릿 검증

# 로그 확인
aws logs tail /aws/lambda/patent-helper-upload --follow
```

### 🌐 서비스 URL
- **프로덕션**: https://d1k8m3z5xkr8hb.cloudfront.net
- **로컬**: http://localhost:3000

## 🎯 최근 주요 개선사항

### 🔍 도면 인식 로직 개선 (2025.01.13)
- **명확한 도면 인식**: "도면[숫자]" 패턴이 있는 페이지만 도면으로 처리
- **코드 간소화**: 복잡한 판단 로직을 단순화하여 성능 향상
- **전체 페이지 활용**: 여백 계산 없이 전체 페이지를 도면 영역으로 사용

### 🎯 매핑 추출 로직 강화 (2025.01.13)
- **인라인 패턴 지원**: "명칭(숫자)" 형태 매핑 추출 (예: "제어부(100)")
- **한국어 조사 처리**: 자동 조사 제거로 깨끗한 명칭 추출
- **추출 정확도 향상**: 82.4% 정확도 달성
- **우선순위 시스템**: 부호설명 > 인라인 > 전체텍스트 순

### ✨ UI/UX 향상 (2025.01)
- **통합 이미지 뷰어**: 메인/결과 페이지 모두 동일한 ImageModal 적용
- **일관된 디자인**: 이미지 배열, 매핑 정보 표시 방식 통일
- **다운로드 기능**: JPG, PNG, SVG, PDF 형식 선택 가능
- **반응형 최적화**: 모바일 환경에서 향상된 사용성

### 🔧 기술적 개선
- **한국어 텍스트 렌더링**: PIL 'latin-1' 인코딩 오류 완전 해결
- **FontManager 시스템**: 유니코드 폰트 자동 선택 및 캐시 관리
- **에러 핸들링**: 상세한 단계별 진행 상황 및 오류 메시지
- **성능 최적화**: ECS 직접 호출로 90-120초 → 즉시 시작

### 🎨 도면 처리 최적화 (2025.01)
- **스마트 어노테이션 개선**:
  - 도면 확장 영역을 라벨 크기에 맞춰 자동 조정
  - 화살표 길이 최적화 (30px)로 깔끔한 연결선
  - 상하 여백 130px 추가로 라벨 짤림 완전 방지
  - 오른쪽 라벨 위치 자동 계산으로 캔버스 내 완전 표시
- **정밀한 도면 영역 추출**:
  - 실제 그래픽 요소 분석으로 도면 영역만 크롭
  - 상하 여백 80px로 대폭 증가하여 잘림 완전 방지
  - 좌표 키 처리 개선 (top/bottom, y0/y1 호환)
  - 라벨링 후 재크롭으로 최적 크기 자동 조정
- **텍스트/도면 구분 강화**:
  - 첫 페이지 상단 텍스트 블록 자동 감지 및 제외
  - 숫자 및 짧은 라벨 비율 분석
  - 평균 단어 길이로 도면 라벨 판별
  - 중요 사각형 개수로 도면 판단 (50px 이상)
- **스마트 후처리**:
  - 라벨링 완료 후 실제 콘텐츠 영역만 재크롭
  - 모든 라벨이 포함되도록 자동 경계 계산
  - 불필요한 여백 제거로 깔끔한 결과물

### 📈 성능 지표
- **처리 시간**: 평균 30-60초 (이전 2-3분)
- **사용자 경험**: 실시간 진행률 표시
- **안정성**: 한국어 텍스트 100% 호환
- **확장성**: AWS 서버리스로 무제한 동시 처리

## 🛠 기술 스택 상세

### Frontend
- **Vue.js 3**: Composition API + `<script setup>`
- **Vue Router**: SPA 라우팅
- **Axios**: HTTP 클라이언트
- **Vite**: 빠른 개발 빌드 도구

### Backend
- **AWS Lambda**: 서버리스 API (Node.js 18.x)
- **ECS Fargate**: 컨테이너 기반 처리 (Python 3.12)
- **S3**: 파일 저장소 + presigned URL
- **DynamoDB**: NoSQL 메타데이터 저장

### AI/ML Processing
- **EasyOCR**: 한국어/영어 OCR 인식
- **OpenCV**: 이미지 처리 및 분석
- **Pillow + FontManager**: 한국어 텍스트 렌더링
- **pypdfium2**: PDF 파싱 및 이미지 추출

### DevOps
- **GitHub Actions**: CI/CD 자동화
- **CloudFormation**: 인프라스트럭처 as Code
- **Docker**: 컨테이너 환경 통일
- **CloudWatch**: 로깅 및 모니터링

## 📞 지원 및 문의

- **이슈 리포팅**: GitHub Issues
- **기술 문의**: [이메일 주소 또는 연락처]

---

**PatentHelper**는 특허 문서 처리의 효율성을 혁신적으로 개선하는 AI 기반 솔루션입니다. 🚀