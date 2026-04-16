---
name: vercel-api-port
description: AWS Lambda 6개를 Vercel Functions(Python)로 포팅하는 표준 패턴. /app 핵심 로직 재사용, Supabase 클라이언트 초기화, pgmq 메시지 발행, signed URL 발급 패턴을 담는다. 환경 분기(local/vercel/fly)와 vercel.json 설정 포함.
---

# Vercel API Port

`vercel-api-engineer` 전용. Lambda → Vercel Functions 포팅 표준.

## 디렉토리 구조
```
api/
├── extract-mappings.py
├── process-with-mappings.py
├── status/[jobId].py
├── result/[jobId].py
├── history.py
└── _lib/
    ├── supabase_client.py
    └── queue.py
vercel.json
requirements.txt
```

## vercel.json (샘플)
```json
{
  "functions": {
    "api/**/*.py": {
      "runtime": "python3.12",
      "memory": 1024,
      "maxDuration": 60
    }
  },
  "env": {
    "PLATFORM": "vercel"
  }
}
```

## requirements.txt (Vercel Functions용)
```
supabase==2.*
pypdfium2==4.25.0
pdfplumber
Pillow
```
**주의**: OCR/PyTorch는 절대 포함하지 않는다 (Fly 워커 전용).

## _lib/supabase_client.py
```python
import os
from supabase import create_client, Client

_client: Client | None = None

def sb() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ['SUPABASE_URL'],
            os.environ['SUPABASE_SERVICE_ROLE_KEY'],
        )
    return _client
```

## _lib/queue.py
```python
from .supabase_client import sb

def enqueue(queue: str, payload: dict) -> int:
    res = sb().rpc('pgmq_send', {'queue_name': queue, 'msg': payload}).execute()
    return res.data  # msg_id
```
**주의**: Supabase Python SDK가 pgmq 네이티브 호출을 지원하지 않는 경우 SQL RPC 함수로 래핑.

```sql
-- 미리 만들어두는 RPC (supabase-data-engineer가 생성)
create or replace function pgmq_send(queue_name text, msg jsonb)
returns bigint language sql as $$
  select pgmq.send(queue_name, msg);
$$;
```

## 엔드포인트 포팅 패턴

### api/extract-mappings.py
```python
from http.server import BaseHTTPRequestHandler
import json, uuid, os
from _lib.supabase_client import sb
from _lib.queue import enqueue

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        job_id = str(uuid.uuid4())
        pdf_path = f"{job_id}/original.pdf"

        # 1) 업로드용 signed URL 발급
        upload = sb().storage.from_('uploads').create_signed_upload_url(pdf_path)

        # 2) jobs row 생성
        sb().table('jobs').insert({
            'id': job_id,
            'status': 'pending',
            'original_pdf_path': f'uploads/{pdf_path}',
        }).execute()

        # 3) 큐 발행
        enqueue('extract_jobs', {'job_id': job_id, 'pdf_path': f'uploads/{pdf_path}'})

        self._respond(200, {
            'jobId': job_id,
            'uploadUrl': upload['signed_url'],
            'uploadPath': pdf_path,
        })

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
```
**핵심**: 큐에 발행만 하고 즉시 반환. 실제 처리는 Fly 워커. Vercel Functions는 절대 PDF 파싱 하지 않는다.

### api/status/[jobId].py
```python
from http.server import BaseHTTPRequestHandler
import json
from _lib.supabase_client import sb

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        job_id = self.path.rstrip('/').split('/')[-1]
        res = sb().table('jobs').select('*').eq('id', job_id).single().execute()
        self.send_response(200 if res.data else 404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(res.data or {}).encode())
```

### api/result/[jobId].py (signed URL 포함)
```python
# 모든 결과 파일 signed URL 1시간 발급
paths = job['result_paths']  # {'completed': '...', 'annotated': [...]}
signed = {
  'completed': sb().storage.from_('results').create_signed_url(paths['completed'], 3600)['signedURL'],
  ...
}
```

## /app 재사용 전략
```
repo/
├── app/services/...     # 유지, 수정 금지
├── api/...              # Vercel Functions (얇은 래퍼)
└── fly/worker/...       # Fly 워커 (/app import)
```

Vercel은 `api/` 함수가 `/app` 상대 import 가능하도록 `vercel.json`에 `includeFiles` 지정:
```json
{
  "functions": {
    "api/**/*.py": {
      "includeFiles": "app/**"
    }
  }
}
```

## 환경 분기 (/app/config/settings.py 확장)
```python
import os
PLATFORM = os.environ.get('PLATFORM', 'local')  # local|vercel|fly

if PLATFORM == 'local':
    # 기존 로컬 설정
elif PLATFORM in ('vercel', 'fly'):
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
```

## 엔드포인트 매핑 표

| 기존 Lambda | 새 경로 | 변경 요점 |
|------------|---------|----------|
| extract-mappings | `api/extract-mappings.py` | S3 upload → Storage signed URL, pgmq 발행 |
| process-with-mappings | `api/process-with-mappings.py` | pgmq `ocr_jobs` 발행 |
| status | `api/status/[jobId].py` | DynamoDB get → Postgres select |
| result | `api/result/[jobId].py` | signed URL 1시간 발급 후 반환 |
| history | `api/history.py` | jobs 최신 N건 |
| image-proxy | 제거 | 프론트가 signed URL로 직접 |

## 제약/주의
- Vercel 무료/Pro 함수 실행시간: 10s/60s. 이 안에 모든 핸들러가 끝나야 한다. 초과 시 로직을 워커로 위임
- 페이로드 한계: 4.5MB 기본. 대용량 PDF는 **signed URL로 직접 Storage 업로드**
- 콜드스타트: Python Functions 초기화 1~2초. supabase client는 모듈 레벨 lazy 캐시

## 출력
- `_workspace/vercel/api/*.py`
- `_workspace/vercel/_lib/*.py`
- `_workspace/vercel/vercel.json`
- `_workspace/vercel/requirements.txt`
- `_workspace/vercel/README.md`

## 검증 체크리스트
- [ ] 모든 핸들러가 60초 안에 반환 (무거운 처리는 워커 위임)
- [ ] 한글 파일명 응답 인코딩 OK
- [ ] CORS: 같은 도메인이므로 헤더 불필요, 다른 도메인(프리뷰)에서 테스트 시만 `Access-Control-Allow-Origin` 추가
- [ ] vercel CLI로 `vercel dev` 로컬 실행 가능
