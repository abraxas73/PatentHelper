# 변경 이력

## [2025.01.19] - DynamoDB 타입 처리 및 도면 추출 안정성 개선

### 🐛 버그 수정
- **DynamoDB 타입 어노테이션 문제 해결**
  - boto3 resource API와 client API 간 데이터 형식 불일치 문제 해결
  - Lambda 함수에서 DynamoDB List(L)/Map(M)/String(S)/Number(N) 타입 래퍼 처리 추가
  - OCR 프로세서에서 extractedImages 파싱 시 타입 어노테이션 처리
  - 프론트엔드 `[object Object]` 에러 해결

- **도면 추출 안정성 향상**
  - pypdfium2 버전 통일 (4.25.0)으로 로컬/AWS 환경 간 일관성 확보
  - Dockerfile CMD 구문 오류 수정 (주석이 같은 줄에 있던 문제)
  - pypdfium2 matrix/scale API 호환성 처리 (버전별 API 차이 대응)
  - PdfColorScheme path_stroke 파라미터 누락 수정

### 🔧 기술적 개선
- Result Lambda: extractedImages/annotatedImages 처리 시 L/M 타입 처리
- OCR Processor: DynamoDB Map 구조 파싱 로직 추가
- ECS 컨테이너 안정성 향상

## [2025.01.16] - PDF 재생성 및 원본 다운로드 기능

### ✨ 새로운 기능
- **원본 PDF 다운로드 기능 추가**
  - 업로드 시 원본 PDF를 S3에 저장
  - DynamoDB에 originalPdfS3Key 필드 추가
  - 작업 이력 상세에서 원본 PDF 다운로드 버튼 제공

- **PDF 재생성 로직 개선**
  - 원본 PDF 페이지 구조 유지하며 도면만 치환
  - bbox 정보를 활용한 정확한 도면 위치 배치
  - 재생성 상태 표시 개선 ("재생성중"/"재생성완료")

### 🐛 버그 수정
- PDF 재생성 페이지 매핑 버그 수정
- 파일명에서 페이지 번호 추출 로직 개선 (drawing_020 → 페이지 20)
- CloudFront behaviors 설정 문제 해결

## [2025.01.15] - 이미지 편집 기능 개선

### ✨ 기능 개선
- 편집된 이미지 인덱스 문제 해결 (문자열 키 일관성)
- 여러 이미지 편집 시 각각 고유하게 저장
- 새로고침 후에도 편집 내용 유지
- Fabric.js 텍스트 편집 모드 버그 수정

### 🔧 기술적 개선
- save-edited-image Lambda CORS 설정 추가
- regenerate-pdf Lambda CORS 설정 추가
- ECS 컨테이너 이름 불일치 문제 해결

## [2025.01.14] - PDF 병합 완전 수정

### 🐛 버그 수정
- bbox 정보 DynamoDB 저장 (Decimal 타입 변환)
- 페이지 인덱싱 오류 수정 (0-indexed vs 1-indexed)
- 도면 크기 자동 조정 (원본 영역 내 최적화)
- 모든 페이지 유지 (마지막 페이지 누락 해결)

### 🔧 기술적 개선
- 텍스트 추출 개선 (영어-한글 혼합, 하이픈 번호 지원)
- OCR 인식률 개선 (적응형 스케일링)
- 도면 영역 감지 (다중 도면 영역 자동 감지)
- 매핑 추출 정확도 향상 (non-greedy 패턴)

## [2025.01.13] - 컨테이너 최적화 및 PDF 생성

### ✨ 새로운 기능
- PDF 생성 기능: OCR 처리 후 자동으로 PDF 생성
- 작업 이력 기능 개선 (localStorage 활용)
- 대용량 파일 업로드 지원 (S3 presigned URL)

### 🔧 기술적 개선
- **컨테이너 최적화**:
  - Extractor: 4개 라이브러리만 사용 (빠른 시작)
  - OCR: 6개 라이브러리 (필수 기능만)
- GitHub Actions 분리: 각 컨테이너 독립 배포
- Lambda 함수 성능 개선 (메모리/타임아웃 최적화)

### 📊 성능 지표
- Extractor 시작 시간: ~10초
- OCR 처리 시간: 이미지당 ~5-10초
- PDF 생성: ~5초
- 전체 처리 시간: 30-60초 (PDF 크기에 따라)