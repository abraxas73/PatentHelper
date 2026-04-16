---
name: frontend-vercel-deploy
description: Vue.js 프론트엔드를 Vercel에 배포한다. config.js 엔드포인트 전환, VITE_ 환경변수 설계, vercel.json, 업로드/다운로드 경로(signed URL) 변경, 한글 파일명/회전 이슈 퇴행 방지 체크리스트.
---

# Frontend Vercel Deploy

`frontend-migration-engineer` 전용. 기존 Vue 앱을 최소 변경으로 Vercel에 올린다.

## 변경 범위
- 프론트 UI/UX는 **절대 건드리지 않는다**. 기능 이관이 목적
- `front/src/config.js` (API/Storage 베이스 URL)
- `front/` 루트에 `vercel.json` 추가
- `.env.example` 업데이트

## vercel.json
```json
{
  "buildCommand": "npm --prefix front run build",
  "outputDirectory": "front/dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/:path*" }
  ]
}
```
**Monorepo 구성**: 레포 루트에 Vercel 프로젝트를 바인딩하고 `Root Directory = ./`로 두되 build는 `front/`에서 실행. `api/`는 레포 루트에 둔다 (vercel-api-engineer 산출물과 일치).

또는 Vercel 대시보드 설정으로 Root Directory = `front/`, `api/` 만 레포 루트 유지 — architect와 합의.

## config.js 패턴
```js
// front/src/config.js
const API_BASE = import.meta.env.VITE_API_BASE || '/api';
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const config = {
  apiBase: API_BASE,
  supabaseUrl: SUPABASE_URL,
  supabaseAnonKey: SUPABASE_ANON_KEY,
};
```
**주의**: `SUPABASE_SERVICE_ROLE_KEY` 절대 노출 금지. anon key만.

## 업로드 플로우 변경
**기존**: API Gateway 바디 업로드 or S3 presigned URL
**신규**: Vercel Function이 `signed_upload_url` 발급 → 프론트가 PUT으로 Storage에 직접

```js
// 1. 업로드 URL 발급
const { uploadUrl, jobId, uploadPath } = await axios.post('/api/extract-mappings', { fileName, size });

// 2. Storage로 직접 업로드
await axios.put(uploadUrl, fileBlob, { headers: { 'Content-Type': 'application/pdf' } });

// 3. 서버에 "업로드 완료" 통지 or 상태 폴링 시작
pollStatus(jobId);
```

## 다운로드 플로우 변경
**기존**: CloudFront URL 직접 링크
**신규**: `/api/result/{jobId}` → signed URL 받아 blob 변환 후 다운로드 (한글 파일명 퇴행 방지)

```js
async function download(jobId, kind = 'completed') {
  const { data } = await axios.get(`/api/result/${jobId}`);
  const url = data.signedUrls[kind];
  const blob = (await axios.get(url, { responseType: 'blob' })).data;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${data.originalName}_완성.pdf`;  // 한글 파일명 유지
  a.click();
}
```

## 이미지 src 변경
기존 CloudFront URL → signed URL. signed URL은 1시간 만료이므로 상태 조회 시점에 새로 발급받은 URL만 사용. 캐싱 주의.

## 환경변수 (.env.example)
```
# 공개 가능 (프론트 번들에 포함됨)
VITE_API_BASE=/api
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOi...

# 서버 전용 (Vercel Functions 환경변수로 설정, 프론트에 노출되지 않음)
# SUPABASE_SERVICE_ROLE_KEY=... (대시보드에서 설정, .env.example에는 제외)
```

## Vercel 프로젝트 설정 (대시보드)
- Framework Preset: Vite
- Build Command: `npm --prefix front run build` 또는 `cd front && npm run build`
- Output Directory: `front/dist`
- Install Command: `npm --prefix front install`
- Environment Variables: 위의 `VITE_*` + 서버용 Supabase 서비스 롤

## 도메인 연결
- Preview: Vercel 기본 (예: `patent-helper-{username}.vercel.app`)
- Production: `patent.sncbears.cloud` 추가 → DNS 전환 시 활성화

## 퇴행 방지 체크리스트 (CLAUDE.md 기록된 과거 이슈)
- [ ] **한글 파일명 다운로드**: blob 변환 + `download` 속성으로 유지, 서버는 `Content-Disposition`에 RFC 5987 인코딩 사용 시 주의
- [ ] **이미지 회전 라벨링 좌표**: 프론트에서 좌표 변환 코드 있으면 유지
- [ ] **이미지 모달 NaN 표시**: width/height 기본값 가드 유지
- [ ] **크로스 오리진 이미지 다운로드**: 같은 도메인(Vercel 뒤)이므로 CORS 자동 해결, 그러나 blob 다운로드 패턴은 유지

## 출력
- `_workspace/frontend/config.js.diff`
- `_workspace/frontend/vercel.json`
- `_workspace/frontend/.env.example`
- `_workspace/frontend/README.md` — 로컬(Vite + 프리뷰 API) 연결 방법

## 검증 체크리스트
- [ ] `npm run build` 성공
- [ ] Vercel 프리뷰 배포에서 전체 플로우 동작
- [ ] 한글 파일명 업로드/다운로드 정상
- [ ] 환경변수 노출 검사 (`VITE_*` 외에 서버 키가 번들에 포함되지 않았는지 grep)
- [ ] 기존 기능 퇴행 없음 (이미지 모달, 매핑 편집, 재생성 PDF, 작업 이력 등)
