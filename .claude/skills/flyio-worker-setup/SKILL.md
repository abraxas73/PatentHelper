---
name: flyio-worker-setup
description: ECS Extractor/OCR 컨테이너를 Fly.io Machines 상주 워커로 전환하는 표준 패턴. pgmq 폴링 루프, fly.toml(autostart/autostop), Dockerfile 최적화, 모델 캐시, 볼륨, 헬스체크, 배포 명령을 담는다.
---

# Fly.io Worker Setup

`flyio-worker-engineer` 전용. Extractor + OCR 두 워커의 표준 구축.

## 앱 구성
- `patent-extractor` — 경량 (shared-cpu-2x, 2GB)
- `patent-ocr` — 무거움 (performance-4x, 8GB) — GPU 옵션 가능

## 디렉토리 구조
```
fly/
├── extractor/
│   ├── Dockerfile
│   ├── fly.toml
│   ├── worker.py         # pgmq 폴링 + 처리
│   └── requirements.txt
└── ocr/
    ├── Dockerfile
    ├── fly.toml
    ├── worker.py
    └── requirements.txt
```

## 공통 worker.py 템플릿
```python
import os, time, json, logging
from supabase import create_client

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
QUEUE = os.environ['QUEUE_NAME']        # extract_jobs or ocr_jobs
VT = int(os.environ.get('VT_SECONDS', '600'))

def read_one():
    res = sb.rpc('pgmq_read', {'queue_name': QUEUE, 'vt': VT, 'qty': 1}).execute()
    msgs = res.data or []
    return msgs[0] if msgs else None

def delete(msg_id):
    sb.rpc('pgmq_delete', {'queue_name': QUEUE, 'msg_id': msg_id}).execute()

def archive(msg_id):
    sb.rpc('pgmq_archive', {'queue_name': QUEUE, 'msg_id': msg_id}).execute()

def handle(payload):
    raise NotImplementedError  # 각 워커에서 오버라이드

def main():
    idle = 0
    while True:
        msg = read_one()
        if not msg:
            idle += 1
            time.sleep(min(30, 2 ** idle))  # exponential up to 30s
            continue
        idle = 0
        try:
            handle(msg['message'])
            delete(msg['msg_id'])
        except Exception:
            log.exception('job failed')
            if msg.get('read_ct', 0) >= 3:
                archive(msg['msg_id'])
            # else: vt 만료 시 재시도

if __name__ == '__main__':
    main()
```

**RPC 래퍼** (supabase-data-engineer가 생성):
```sql
create or replace function pgmq_read(queue_name text, vt int, qty int)
returns setof pgmq.message_record language sql as $$
  select * from pgmq.read(queue_name, vt, qty);
$$;
create or replace function pgmq_delete(queue_name text, msg_id bigint)
returns boolean language sql as $$ select pgmq.delete(queue_name, msg_id); $$;
create or replace function pgmq_archive(queue_name text, msg_id bigint)
returns boolean language sql as $$ select pgmq.archive(queue_name, msg_id); $$;
```

## Extractor worker.py
```python
# ... 공통 템플릿 import
from app.services.image_extractor import extract_drawings_and_mappings

def handle(payload):
    job_id = payload['job_id']
    pdf_path = payload['pdf_path']

    # 1) Storage에서 PDF 다운로드
    data = sb.storage.from_('uploads').download(pdf_path.replace('uploads/', ''))
    local_pdf = f'/tmp/{job_id}.pdf'
    open(local_pdf, 'wb').write(data)

    # 2) /app 핵심 로직 사용
    result = extract_drawings_and_mappings(local_pdf)
    # result = {'images': [...], 'mappings': [...], 'metadata': [...]}

    # 3) 이미지 Storage 업로드
    for i, img_path in enumerate(result['images']):
        sb.storage.from_('results').upload(
            f'{job_id}/drawings/drawing_{i+1:03d}.png',
            open(img_path, 'rb').read()
        )

    # 4) jobs 업데이트
    sb.table('jobs').update({
        'status': 'awaiting_mapping',
        'extracted_images': [...],
        'mappings': result['mappings'],
        'extracted_images_metadata': result['metadata'],
    }).eq('id', job_id).execute()
```

## OCR worker.py
OCR 컨테이너는 `batch_annotate` 사용, 결과 PDF까지 생성 후 `results/{job_id}/completed.pdf` 업로드, jobs.status=completed.

## Dockerfile (Extractor)
```Dockerfile
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PLATFORM=fly

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# /app 핵심 로직 복사
COPY app /srv/app
COPY fly/extractor/worker.py /srv/worker.py

CMD ["python", "worker.py"]
```

## Dockerfile (OCR)
```Dockerfile
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PLATFORM=fly

# 시스템 라이브러리 (OpenCV 런타임)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# EasyOCR 모델 사전 다운로드 (콜드스타트 절감)
RUN python -c "import easyocr; easyocr.Reader(['ko','en'], gpu=False)"

COPY app /srv/app
COPY fly/ocr/worker.py /srv/worker.py

CMD ["python", "worker.py"]
```

## fly.toml (Extractor)
```toml
app = "patent-extractor"
primary_region = "nrt"

[build]
  dockerfile = "Dockerfile"

[env]
  QUEUE_NAME = "extract_jobs"
  VT_SECONDS = "600"

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 2048

# 큐 기반이므로 HTTP 서비스 없이 워커만 실행
[processes]
  worker = "python worker.py"

# 휴면/자동기동 (비용 절감 핵심)
[[mounts]]  # 모델/캐시 영속 저장 (OCR 측에서 필요)
# 필요 시 volume 추가
```

## fly.toml (OCR)
```toml
app = "patent-ocr"
primary_region = "nrt"

[build]
  dockerfile = "Dockerfile"

[env]
  QUEUE_NAME = "ocr_jobs"
  VT_SECONDS = "900"

[[vm]]
  cpu_kind = "performance"
  cpus = 4
  memory_mb = 8192

[processes]
  worker = "python worker.py"
```

## 휴면/자동기동 전략
- Fly Machines는 HTTP 서비스가 없는 워커 모드에서는 자동 정지가 어려움
- **패턴 A (권장)**: 워커가 idle 임계 시간(예: 5분) 동안 메시지 없으면 스스로 종료(`sys.exit(0)`). Fly가 재시작 정책(`restart = "never"`)일 경우, Vercel Functions가 작업 발행 시 `fly machine start`를 REST API로 호출
- **패턴 B**: 간단히 min_machines=0으로 두고, Vercel 함수가 `fly machine start` 호출하는 스크립트 공통화

Vercel에서 Fly 머신 기동 (선택):
```python
# api/extract-mappings.py 안에서
import requests
requests.post(
  f"https://api.machines.dev/v1/apps/patent-extractor/machines/{MACHINE_ID}/start",
  headers={"Authorization": f"Bearer {os.environ['FLY_API_TOKEN']}"}
)
```

## 배포 명령
```bash
# 초기
flyctl launch --no-deploy  # 앱/토큰 생성
flyctl secrets set SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
flyctl deploy

# 재배포
flyctl deploy -c fly/extractor/fly.toml
flyctl deploy -c fly/ocr/fly.toml
```

## 헬스/관찰
- `flyctl logs -a patent-extractor` 로 실시간 로그
- `job_events` 테이블에 시작/종료 기록 이중화

## 검증 체크리스트
- [ ] 로컬에서 `PLATFORM=fly python worker.py` 로 실행 가능 (로컬 Postgres or 원격 Supabase)
- [ ] 큐 메시지 1개 왕복 성공
- [ ] 처리 실패 시 3회 재시도 후 archive로 이동
- [ ] OCR 모델 사전 다운로드로 첫 실행 시간 < 30초
- [ ] Storage 업로드가 한글 경로 없이도 정상 (경로는 영문/숫자로 구성)

## 출력
- `_workspace/fly/extractor/{Dockerfile, fly.toml, worker.py, requirements.txt}`
- `_workspace/fly/ocr/{Dockerfile, fly.toml, worker.py, requirements.txt}`
- `_workspace/fly/README.md`
