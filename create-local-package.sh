#!/bin/bash

# 스크립트 실행 위치 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_NAME="PatentHelper"
OUTPUT_FILE="PatentHelper-local.zip"
TEMP_DIR="temp_package"

# 색상 출력을 위한 변수
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== PatentHelper 로컬 실행용 패키지 생성 ===${NC}"
echo ""

# 기존 임시 디렉토리 삭제
if [ -d "$TEMP_DIR" ]; then
    echo -e "${YELLOW}기존 임시 디렉토리 삭제 중...${NC}"
    rm -rf "$TEMP_DIR"
fi

# 기존 zip 파일 삭제
if [ -f "$OUTPUT_FILE" ]; then
    echo -e "${YELLOW}기존 압축 파일 삭제 중...${NC}"
    rm -f "$OUTPUT_FILE"
fi

# 임시 디렉토리 생성
echo -e "${GREEN}임시 디렉토리 생성 중...${NC}"
mkdir -p "$TEMP_DIR/$PROJECT_NAME"

# 필요한 파일과 디렉토리 복사
echo -e "${GREEN}필요한 파일들을 복사 중...${NC}"

# app 디렉토리 (핵심 백엔드 로직)
if [ -d "app" ]; then
    echo "  - app/ (백엔드 핵심 로직)"
    cp -r app "$TEMP_DIR/$PROJECT_NAME/"
fi

# local 디렉토리의 필요한 파일들만
if [ -d "local" ]; then
    echo "  - local/ (프론트엔드 소스)"
    mkdir -p "$TEMP_DIR/$PROJECT_NAME/local"
    
    # src 디렉토리
    if [ -d "local/src" ]; then
        cp -r local/src "$TEMP_DIR/$PROJECT_NAME/local/"
    fi
    
    # 설정 파일들
    for file in package.json package-lock.json vite.config.js index.html .gitignore; do
        if [ -f "local/$file" ]; then
            cp "local/$file" "$TEMP_DIR/$PROJECT_NAME/local/"
        fi
    done
    
    # public 디렉토리가 있으면 복사
    if [ -d "local/public" ]; then
        cp -r local/public "$TEMP_DIR/$PROJECT_NAME/local/"
    fi
fi

# 테스트 디렉토리
if [ -d "tests" ]; then
    echo "  - tests/ (테스트 코드)"
    cp -r tests "$TEMP_DIR/$PROJECT_NAME/"
fi

# 루트 레벨 파일들
echo "  - 루트 설정 파일들"
for file in main.py requirements.txt LOCAL.md README.md CLAUDE.md .gitignore; do
    if [ -f "$file" ]; then
        echo "    • $file"
        cp "$file" "$TEMP_DIR/$PROJECT_NAME/"
    fi
done

# data와 logs 디렉토리는 빈 디렉토리로 생성
echo "  - 빈 디렉토리 생성"
mkdir -p "$TEMP_DIR/$PROJECT_NAME/data"
mkdir -p "$TEMP_DIR/$PROJECT_NAME/logs"
echo "*" > "$TEMP_DIR/$PROJECT_NAME/data/.gitignore"
echo "!.gitignore" >> "$TEMP_DIR/$PROJECT_NAME/data/.gitignore"
echo "*" > "$TEMP_DIR/$PROJECT_NAME/logs/.gitignore"
echo "!.gitignore" >> "$TEMP_DIR/$PROJECT_NAME/logs/.gitignore"

# 압축 파일 생성
echo ""
echo -e "${BLUE}압축 파일 생성 중...${NC}"
cd "$TEMP_DIR"
zip -r "../$OUTPUT_FILE" "$PROJECT_NAME" -q

# 임시 디렉토리 삭제
cd ..
echo -e "${GREEN}임시 디렉토리 정리 중...${NC}"
rm -rf "$TEMP_DIR"

# 결과 확인
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo -e "${GREEN}✅ 패키지 생성 완료!${NC}"
    echo -e "   파일명: ${YELLOW}$OUTPUT_FILE${NC}"
    echo -e "   크기: ${YELLOW}$FILE_SIZE${NC}"
    echo ""
    echo -e "${BLUE}포함된 내용:${NC}"
    echo "  • app/          - 백엔드 핵심 로직"
    echo "  • local/src/    - 프론트엔드 소스 코드"
    echo "  • local/        - package.json 등 설정 파일"
    echo "  • tests/        - 테스트 코드"
    echo "  • main.py       - 로컬 개발 서버"
    echo "  • requirements.txt - Python 의존성"
    echo "  • LOCAL.md      - 로컬 실행 가이드"
    echo "  • README.md     - 프로젝트 문서"
    echo "  • CLAUDE.md     - 프로젝트 명세"
    echo "  • data/         - 데이터 디렉토리 (빈 폴더)"
    echo "  • logs/         - 로그 디렉토리 (빈 폴더)"
    echo ""
    echo -e "${RED}제외된 내용:${NC}"
    echo "  ✗ deploy_aws/   - AWS 배포 관련 파일"
    echo "  ✗ .github/      - GitHub Actions"
    echo "  ✗ front/        - 프로덕션 프론트엔드"
    echo "  ✗ local/dist/   - 빌드된 파일"
    echo "  ✗ local/node_modules/ - npm 패키지"
    echo "  ✗ __pycache__/  - Python 캐시"
    echo "  ✗ .git/         - Git 저장소"
    echo ""
    echo -e "${GREEN}사용 방법:${NC}"
    echo "  1. unzip $OUTPUT_FILE"
    echo "  2. cd $PROJECT_NAME"
    echo "  3. pip install -r requirements.txt"
    echo "  4. cd local && npm install && cd .."
    echo "  5. python main.py (백엔드 실행)"
    echo "  6. cd local && npm run dev (프론트엔드 실행)"
else
    echo -e "${RED}❌ 패키지 생성 실패!${NC}"
    exit 1
fi