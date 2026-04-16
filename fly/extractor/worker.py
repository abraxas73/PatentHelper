"""Fly.io Extractor 워커.

pgmq `extract_jobs` 큐를 폴링해 PDF에서 도면 이미지와 번호-명칭 매핑을 추출한다.
  - /app/core/pdf_processor.py (PDFProcessor) — cloud-agnostic 핵심 로직
  - /app/services/text_analyzer.py (TextAnalyzer) — 매핑 추출
  - Storage 입출력은 supabase-py, 상태는 Postgres jobs 테이블

메시지 포맷:
  {"job_id": "uuid", "pdf_path": "uploads/{job_id}/original.pdf"}
"""
import os
import sys
import time
import json
import logging
import tempfile
import traceback
from pathlib import Path

from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('extractor')

# /app 핵심 로직 (Docker COPY 로 /srv/app 에 위치)
sys.path.insert(0, '/srv')
from app.core.pdf_processor import PDFProcessor  # noqa: E402
from app.services.text_analyzer import TextAnalyzer  # noqa: E402

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
QUEUE = os.environ.get('QUEUE_NAME', 'extract_jobs')
VT = int(os.environ.get('VT_SECONDS', '600'))
IDLE_EXIT_AFTER = int(os.environ.get('IDLE_EXIT_AFTER', '300'))

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def rpc_read():
    res = sb.rpc('pgmq_read', {'queue_name': QUEUE, 'vt': VT, 'qty': 1}).execute()
    msgs = res.data or []
    return msgs[0] if msgs else None


def rpc_delete(msg_id):
    sb.rpc('pgmq_delete', {'queue_name': QUEUE, 'msg_id': msg_id}).execute()


def rpc_archive(msg_id):
    sb.rpc('pgmq_archive', {'queue_name': QUEUE, 'msg_id': msg_id}).execute()


def update_job(job_id, **fields):
    sb.table('jobs').update(fields).eq('id', job_id).execute()


def emit_event(job_id, event_type, payload=None):
    sb.table('job_events').insert({
        'job_id': job_id, 'event_type': event_type,
        'source': 'fly-extractor', 'payload': payload,
    }).execute()


import httpx

_AUTH_HEADERS = {'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY}


def storage_download(storage_path: str, dest: Path):
    """storage_path = 'uploads/{job_id}/original.pdf' → bucket 'uploads'.
    supabase-py .storage.download 가 storage3 내부에서 empty-body HTTP error 시 JSONDecodeError 를
    던지는 버그가 있어 httpx 로 직접 호출한다."""
    bucket, _, object_path = storage_path.partition('/')
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}"
    with httpx.Client(timeout=120) as cli:
        r = cli.get(url, headers=_AUTH_HEADERS)
        r.raise_for_status()
        dest.write_bytes(r.content)


def storage_upload(bucket: str, object_path: str, src_bytes: bytes, mime='image/png'):
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}"
    headers = {**_AUTH_HEADERS, 'Content-Type': mime, 'x-upsert': 'true'}
    with httpx.Client(timeout=180) as cli:
        r = cli.post(url, content=src_bytes, headers=headers)
        if r.status_code == 409 and 'already exists' in r.text.lower():
            # upsert 실패 시 PUT 로 덮어쓰기
            r = cli.put(url, content=src_bytes, headers=headers)
        r.raise_for_status()


def process(msg: dict):
    job_id = msg['job_id']
    storage_path = msg['pdf_path']

    log.info('extract start job=%s path=%s', job_id, storage_path)
    emit_event(job_id, 'started')
    update_job(job_id, status='extracting', progress=20, message='PDF 분석 중')

    with tempfile.TemporaryDirectory(prefix=f'extract_{job_id}_') as tmp:
        tmp = Path(tmp)
        local_pdf = tmp / 'input.pdf'
        storage_download(storage_path, local_pdf)

        pdf = PDFProcessor(local_pdf)
        try:
            text = pdf.extract_text()
            images = pdf.extract_all_images()   # List[Dict{page,index,width,height,bbox,pil_image,...}]
            total_pages = len(pdf.pdfium_doc)
        finally:
            pdf.close()

        # 이미지 Storage 업로드
        extracted = []
        metadata = []
        for img_data in images:
            page = int(img_data['page'])
            idx = int(img_data.get('index', 0))
            pil = img_data['pil_image']

            local_png = tmp / f'drawing_{page:03d}.png'
            pil.save(local_png, format='PNG')

            object_path = f'{job_id}/extracted/drawing_{page:03d}.png'
            storage_upload('results', object_path, local_png.read_bytes())

            extracted.append({'page': page, 'path': object_path})
            metadata.append({
                'page': page,
                'index': idx,
                'width': int(img_data.get('width', 0)),
                'height': int(img_data.get('height', 0)),
                'bbox': list(img_data.get('bbox')) if img_data.get('bbox') else None,
                'content_ratio': float(img_data.get('content_ratio', 0)),
                'entropy': float(img_data.get('entropy', 0)),
            })

        # 매핑 추출 (Dict[str,str] → list of objects for DB contract)
        mappings_dict = TextAnalyzer().extract_number_mappings(text) if text else {}
        mappings = [
            {'number': n, 'label': l, 'selected': True}
            for n, l in sorted(mappings_dict.items())
        ]

        update_job(
            job_id,
            status='awaiting_mapping',
            progress=50,
            extracted_images=extracted,
            extracted_images_metadata=metadata,
            mappings=mappings,
            total_pages=total_pages,
            message=f'추출 완료: 도면 {len(extracted)}개, 매핑 {len(mappings)}개',
        )

    emit_event(job_id, 'completed', {'images': len(extracted), 'mappings': len(mappings)})
    log.info('extract done job=%s images=%d mappings=%d', job_id, len(extracted), len(mappings))


def main():
    idle_since = None
    while True:
        msg = rpc_read()
        if msg is None:
            if idle_since is None:
                idle_since = time.time()
            elif IDLE_EXIT_AFTER and (time.time() - idle_since) > IDLE_EXIT_AFTER:
                log.info('idle exit after %ds', IDLE_EXIT_AFTER)
                return
            time.sleep(5)
            continue

        idle_since = None
        job_id = None
        try:
            body = msg['message']
            job_id = body.get('job_id')
            process(body)
            rpc_delete(msg['msg_id'])
        except Exception as e:
            log.error('job failed: %s', traceback.format_exc())
            if job_id:
                try:
                    update_job(job_id, status='failed', error=str(e))
                    emit_event(job_id, 'failed', {'error': str(e)})
                except Exception:
                    pass
            if (msg.get('read_ct') or 0) >= 3:
                rpc_archive(msg['msg_id'])


if __name__ == '__main__':
    main()
