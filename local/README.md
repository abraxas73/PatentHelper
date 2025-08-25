# Patent Helper - Local Web Application

로컬 Python 서버와 통신하는 웹 애플리케이션입니다.

## 특징

- 로컬 Python FastAPI 서버 (http://localhost:8000) 와 통신
- AWS 없이 로컬에서 PDF 처리
- 처리 결과를 localStorage에 저장
- 포트 3001에서 실행 (기존 front는 3000 사용)

## 설치 및 실행

### 1. 백엔드 서버 실행 (필수)

먼저 Python 백엔드 서버가 실행되어야 합니다:

```bash
# 프로젝트 루트에서
pip install -r requirements.txt
python main.py
# 서버가 http://localhost:8000 에서 실행됨
```

### 2. 프론트엔드 설치

```bash
cd local
npm install
```

### 3. 개발 서버 실행

```bash
npm run dev
# 웹앱이 http://localhost:3001 에서 실행됨
```

### 4. 프로덕션 빌드

```bash
npm run build
npm run preview
```

## API 엔드포인트

로컬 서버는 다음 엔드포인트를 사용합니다:

- `POST /api/v1/process` - PDF 업로드 및 처리
- `GET /api/v1/images/{filename}` - 이미지 조회
- `GET /api/v1/list-images` - 이미지 목록
- `GET /api/v1/status` - 서버 상태 확인

## 주요 차이점

### AWS 버전 (front)
- Lambda Functions를 통한 비동기 처리
- S3, DynamoDB 사용
- 작업 ID 기반 폴링
- Presigned URL 사용

### 로컬 버전 (local)
- FastAPI 동기 처리
- 로컬 파일 시스템 사용
- 즉시 결과 반환
- 직접 이미지 URL 사용

## 파일 구조

```
local/
├── src/
│   ├── views/
│   │   ├── MainView.vue      # 메인 업로드/결과 페이지
│   │   └── JobResultView.vue  # 작업 결과 상세 페이지
│   ├── components/
│   │   └── ImageModal.vue    # 이미지 확대/다운로드 모달
│   ├── config.js              # 로컬 서버 설정
│   ├── router.js              # 라우터 설정
│   └── App.vue               # 메인 컴포넌트
├── package.json              # 포트 3001 설정
├── vite.config.js            # Vite 프록시 설정
└── README.md                 # 이 파일
```

## 문제 해결

### CORS 오류
Vite 프록시를 통해 처리되므로 CORS 문제가 발생하지 않아야 합니다.
문제가 있다면 백엔드 서버의 CORS 설정을 확인하세요.

### 포트 충돌
- 백엔드: 8000 포트 사용
- 로컬 프론트: 3001 포트 사용
- AWS 프론트: 3000 포트 사용

### 이미지가 보이지 않는 경우
1. 백엔드 서버가 실행 중인지 확인
2. `data/extracted_images/` 폴더에 이미지가 있는지 확인
3. 브라우저 개발자 도구에서 네트워크 오류 확인