# 🚀 PatentHelper 로컬 실행 가이드 (초보자용)

이 가이드는 프로그래밍 경험이 없는 분들도 쉽게 따라할 수 있도록 작성되었습니다.
모든 단계를 차근차근 따라하시면 로컬 컴퓨터에서 PatentHelper를 실행할 수 있습니다.

## 📋 목차
1. [필수 프로그램 설치](#1-필수-프로그램-설치)
2. [프로젝트 다운로드](#2-프로젝트-다운로드)
3. [백엔드 서버 실행](#3-백엔드-서버-실행)
4. [프론트엔드 실행](#4-프론트엔드-실행)
5. [브라우저에서 접속](#5-브라우저에서-접속)
6. [문제 해결](#6-문제-해결)

---

## 1. 필수 프로그램 설치

### 1.1 Python 설치 (백엔드용)

#### Windows 사용자
1. [Python 공식 사이트](https://www.python.org/downloads/) 접속
2. "Download Python 3.12.x" 버튼 클릭 (최신 3.12 버전)
3. 다운로드된 설치 파일 실행
4. ⚠️ **중요**: "Add Python to PATH" 체크박스 반드시 체크
5. "Install Now" 클릭하여 설치

#### Mac 사용자
1. 터미널 열기 (Spotlight 검색에서 "터미널" 입력)
2. Homebrew가 없다면 먼저 설치:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. Python 설치:
   ```bash
   brew install python@3.12
   ```

#### 설치 확인
터미널(Windows는 명령 프롬프트)에서 다음 명령어 입력:
```bash
python --version
```
또는
```bash
python3 --version
```
"Python 3.12.x"가 표시되면 성공!

### 1.2 Node.js 설치 (프론트엔드용)

#### Windows/Mac 공통
1. [Node.js 공식 사이트](https://nodejs.org/) 접속
2. "LTS" 버전 다운로드 (안정적인 버전)
3. 다운로드된 설치 파일 실행
4. 모든 기본 설정 그대로 "Next" 클릭하여 설치

#### 설치 확인
터미널/명령 프롬프트에서:
```bash
node --version
npm --version
```
버전 번호가 표시되면 성공!

---

## 2. 프로젝트 다운로드

- 제공된 PatentHelper-local.zip 파일의 압축을 풀어주세요. 

---

## 3. 백엔드 서버 실행

### 3.1 터미널/명령 프롬프트 열기
- **Windows**: Win+R → "cmd" 입력 → Enter
- **Mac**: Spotlight(Cmd+Space) → "터미널" 입력 → Enter

### 3.2 프로젝트 폴더로 이동
```bash
# 예시: 바탕화면에 있는 경우
cd Desktop/PatentHelper
```

### 3.3 Python 가상환경 생성 및 활성화

#### Windows
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate
```

#### Mac/Linux
```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate
```

✅ **성공 표시**: 터미널에 `(venv)`가 표시되면 활성화 성공!

### 3.4 필요한 패키지 설치
```bash
# pip 업그레이드 (선택사항)
pip install --upgrade pip

# 필요한 패키지 모두 설치 (시간이 좀 걸립니다)
pip install -r requirements.txt
```

⏱️ **예상 시간**: 5-10분 (인터넷 속도에 따라 다름)

### 3.5 백엔드 서버 실행

⚠️ **중요**: 가상환경이 활성화되어 있는지 확인하세요!
- 터미널에 `(venv)`가 표시되어야 합니다
- 표시되지 않는다면 3.3 단계의 가상환경 활성화 명령을 다시 실행하세요

```bash
python main.py
```

✅ **성공 메시지**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

⚠️ **중요**: 이 터미널 창을 닫지 마세요! 서버가 계속 실행 중이어야 합니다.

---

## 4. 프론트엔드 실행

### 4.1 새 터미널/명령 프롬프트 열기
백엔드 서버는 계속 실행 중이어야 하므로 **새로운** 터미널 창을 엽니다.

### 4.2 프론트엔드 폴더로 이동
```bash
# 프로젝트 폴더로 이동
cd Desktop/PatentHelper

# local 폴더로 이동
cd local
```

### 4.3 필요한 패키지 설치
```bash
# 처음 실행할 때만 필요 (시간이 좀 걸립니다)
npm install
```

⏱️ **예상 시간**: 3-5분

### 4.4 프론트엔드 개발 서버 실행
```bash
npm run dev
```

✅ **성공 메시지**:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://xxx.xxx.xxx.xxx:3000/
  ➜  press h + enter to show help
```

---

## 5. 브라우저에서 접속

### 5.1 웹 브라우저 열기
Chrome, Firefox, Safari, Edge 등 아무 브라우저나 사용 가능

### 5.2 주소 입력
주소창에 다음 중 하나 입력:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

### 5.3 PatentHelper 사용 시작!
🎉 축하합니다! 이제 로컬에서 PatentHelper를 사용할 수 있습니다.

#### 사용 방법:
1. "PDF 파일 선택" 버튼 클릭
2. 특허 문서 PDF 파일 선택
3. "1단계: 매핑 추출" 버튼 클릭
4. 추출된 번호-명칭 매핑 확인 및 편집
5. "2단계: OCR 처리 시작" 버튼 클릭
6. 처리 완료 후 결과 확인 및 다운로드

---

## 6. 문제 해결

### 자주 발생하는 문제와 해결 방법

#### 문제 1: "python이 내부 또는 외부 명령... 인식되지 않습니다"
**해결책**:
- Python 재설치 시 "Add Python to PATH" 체크 확인
- 또는 `python3` 명령어 사용해보기

#### 문제 2: "pip가 인식되지 않습니다"
**해결책**:
```bash
python -m pip install -r requirements.txt
```

#### 문제 3: "포트 8000이 이미 사용 중입니다"
**해결책**:
- 기존 실행 중인 서버 종료 (Ctrl+C)
- 또는 main.py 파일에서 포트 변경:
  ```python
  uvicorn.run(app, host="0.0.0.0", port=8001)  # 8000 → 8001
  ```

#### 문제 4: "포트 3000이 이미 사용 중입니다"
**해결책**:
- local/vite.config.js 파일에서 포트 변경:
  ```javascript
  server: {
    port: 3001  // 3000 → 3001
  }
  ```

#### 문제 5: npm install 실행 시 오류
**해결책**:
```bash
# 캐시 정리
npm cache clean --force

# 다시 설치
npm install
```

#### 문제 6: "ModuleNotFoundError: No module named 'xxx'"
**해결책**:
```bash
# 가상환경 활성화 확인 (venv)가 표시되는지
# 특정 모듈만 설치
pip install [모듈명]
```

#### 문제 7: 백엔드와 프론트엔드 연결 안 됨
**해결책**:
1. 백엔드 서버가 실행 중인지 확인 (http://localhost:8000)
2. local/src/config.js 파일에서 API_URL 확인:
   ```javascript
   export const API_URL = 'http://localhost:8000'
   ```

---

## 🔄 서버 종료 및 재시작

### 서버 종료
각 터미널에서 `Ctrl+C` (Mac은 `Cmd+C`)

### 다음에 다시 실행할 때

#### 백엔드:
```bash
cd PatentHelper
source venv/bin/activate  # Mac/Linux
# 또는
venv\Scripts\activate  # Windows
python main.py
```

#### 프론트엔드:
```bash
cd PatentHelper/local
npm run dev
```

---

## 💡 추가 팁

### 개발자 도구 활용
브라우저에서 F12 키를 눌러 개발자 도구를 열면:
- Console: 에러 메시지 확인
- Network: API 요청 상태 확인

### 로그 확인
- 백엔드 로그: main.py를 실행한 터미널
- 프론트엔드 로그: npm run dev를 실행한 터미널
- 브라우저 콘솔: F12 → Console 탭

### 파일 변경 시
- 백엔드: 자동으로 재시작됨
- 프론트엔드: 자동으로 새로고침됨

---

## 📞 도움이 필요하신가요?

이 가이드를 따라해도 문제가 해결되지 않는다면:
1. 에러 메시지를 정확히 복사해두세요
2. 어느 단계에서 문제가 발생했는지 기록해두세요
3. GitHub Issues에 문제를 올려주세요

---

**작성일**: 2025-08-25
**버전**: 1.0.0