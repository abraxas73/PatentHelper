# PatentHelper 🔬

**특허 문서 PDF에서 도면을 추출하고 각 부품 번호에 한국어 명칭을 자동으로 추가하는 AI 기반 시스템**

[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-orange.svg)](https://aws.amazon.com/serverless/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)](https://vuejs.org/)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org/)
[![EasyOCR](https://img.shields.io/badge/EasyOCR-Korean-green.svg)](https://github.com/JaidedAI/EasyOCR)

## ✨ 주요 기능

### 🤖 AI 기반 처리
- **도면 자동 추출**: 독립 라인 패턴 매칭으로 정확한 도면 페이지만 추출 (2025.09.19 개선)
- **이미지 콘텐츠 검증**: 엔트로피 계산으로 실제 도면 콘텐츠 확인
- **양방향 회전 감지**: +90°/-90° 양방향 회전 감지로 OCR 인식률 극대화 (2025.09.19 추가)
- **향상된 OCR**: 적응형 스케일링으로 인식률 개선 (2025.01.14 업데이트)
- **텍스트 분석**: 영어-한글 혼합 용어 및 하이픈 번호 지원 (111a-1, CFD시뮬레이션 등)
- **스마트 어노테이션**: 다중 도면 영역 감지, 도면별 중심점 기반 라벨 배치
- **완벽한 PDF 병합**: 원본 문서와 어노테이션된 도면을 정확한 위치에 병합
- **이미지 편집 기능**: Fabric.js 기반 실시간 이미지 편집 (2025.01.15 추가)
- **PDF 재생성**: 편집된 이미지로 원본 구조 유지하며 PDF 재생성 (2025.01.16 수정)

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
```

## 📂 프로젝트 구조

```
PatentHelper/
├── app/              # 핵심 비즈니스 로직
│   ├── services/     # 서비스 레이어
│   └── core/         # 코어 모듈
├── front/            # Vue.js 프론트엔드
│   ├── src/
│   └── dist/         # 빌드 결과물
├── deploy_aws/       # AWS 배포 파일
│   ├── infrastructure/  # SAM 템플릿
│   ├── lambda/          # Lambda 함수
│   ├── ecs-extractor/   # ECS 컨테이너
│   └── ecs-ocr/         # OCR 컨테이너
├── data/             # 로컬 데이터
│   ├── input/        # 업로드된 PDF
│   └── output/
│       ├── images/   # 추출된 도면
│       └── annotated/# 어노테이션된 도면
├── logs/             # 로그 파일
└── tests/            # 테스트
```

## 최근 업데이트 (2025-09-19)

### 도면 인식 개선
- **"도 N" 형식 지원**: "도 1", "도 2" 등 띄어쓰기가 있는 도면 번호 패턴 인식 추가
- **도면 추출 정확도 향상**: 다양한 특허 문서 형식에 대한 호환성 개선
- **텍스트 분석 강화**: 도면 설명 텍스트 패턴 매칭 알고리즘 개선

### 이미지 편집 기능 개선 (2025-01-15)
- **다중 이미지 편집 지원**: 각 도면별로 독립적인 편집 내용 저장
- **편집 내용 영구 저장**: S3에 저장되어 새로고침 후에도 유지
- **Fabric.js 통합**: 도형, 텍스트, 화살표 등 다양한 편집 도구 제공
- **텍스트 편집 버그 수정**: 백스페이스 키 동작 정상화

### CORS 및 API 안정성 개선 (2025-01-15)
- **Lambda 함수 CORS 설정**: save-edited-image, regenerate-pdf 엔드포인트
- **ECS 컨테이너 호환성**: 컨테이너 이름 불일치 문제 해결
- **CloudFront URL 처리**: 편집된 이미지 접근 경로 최적화

### 도면 어노테이션 최적화 (2025-08-24)
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
        "https://api-url/upload",
        files={"file": f}
    )
    job_id = response.json()["jobId"]

# 상태 확인
status = requests.get(f"https://api-url/status/{job_id}")
print(status.json())

# 결과 조회
if status.json()["status"] == "completed":
    results = requests.get(f"https://api-url/result/{job_id}")
    annotated_images = results.json()["annotatedImages"]
```

## 🔧 기술 스택
- **백엔드**: Python 3.12, FastAPI, EasyOCR
- **프론트엔드**: Vue.js 3, Vite, Axios
- **클라우드**: AWS Lambda, ECS Fargate, S3, DynamoDB, CloudFront
- **AI/ML**: PyTorch, OpenCV, PIL


### 📊 성능 및 비용 최적화
- **Cold Start**: ~5-10초 (vs 이전 90-120초)
- **Auto Scaling**: 트래픽에 따른 자동 확장/축소
- **비용 효율성**: 사용량 기반 과금 (무료 티어 활용)
- **고가용성**: Multi-AZ 배포로 99.9% 가용성

## 📝 최신 업데이트 (2025.01.19)

### 긴급 버그 수정
- 🐛 **DynamoDB 타입 어노테이션 처리**: boto3 resource/client API 불일치 문제 해결
- 🔧 **도면 추출 안정화**: pypdfium2 버전 통일 및 API 호환성 처리
- ✅ **프론트엔드 에러 수정**: `[object Object]` 표시 문제 해결

### 기술적 개선
- 📊 Lambda 함수에서 DynamoDB List(L)/Map(M) 타입 래퍼 처리
- 🔧 OCR 프로세서 extractedImages 파싱 로직 개선
- 🎨 ECS 컨테이너 Dockerfile CMD 구문 오류 수정

### 🔧 개발자 도구
```bash
# 로컬 테스트
npm run dev          # 프론트엔드 개발 서버
python main.py       # 백엔드 개발 서버

# AWS 리소스 검증
cd deploy_aws
./validate-cloudfront.sh  # CloudFront 설정 확인
./update-lambda.sh        # Lambda만 업데이트 (권장)
```

### 🌐 서비스 URL
- **프로덕션**: https://d1k8m3z5xkr8hb.cloudfront.net
- **로컬**: http://localhost:3000

## 🎯 최근 주요 개선사항

### 🔧 PDF 병합 및 안정성 개선 (2025.01.14 밤)
- **완벽한 PDF 병합**: 원본 문서와 어노테이션 도면을 정확한 위치에 병합
- **페이지 인덱싱 수정**: 0-indexed vs 1-indexed 문제 해결로 모든 페이지 유지
- **도면 크기 최적화**: bbox 영역 내 자동 크기 조정으로 잘림 방지
- **DynamoDB 호환성**: float-Decimal 타입 자동 변환

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
- **스트리밍 업로드**: S3 presigned URL로 대용량 파일 처리
- **메모리 최적화**: Lambda 메모리 10GB, 타임아웃 15분 설정
- **로깅 시스템**: CloudWatch 통합 상세 로깅

## 🤝 기여하기

1. Fork 프로젝트
2. Feature 브랜치 생성 (`git checkout -b feature/AmazingFeature`)
3. 변경사항 커밋 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 Push (`git push origin feature/AmazingFeature`)
5. Pull Request 생성

## 📄 라이선스

MIT 라이선스 - [LICENSE](LICENSE) 파일 참조

## 📧 문의

프로젝트 관련 문의사항은 이슈 트래커를 이용해 주세요.

---

**Made with ❤️ for Patent Engineers**