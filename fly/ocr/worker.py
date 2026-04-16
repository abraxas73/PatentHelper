"""Fly.io OCR 워커.

두 큐를 폴링:
  - ocr_jobs        : 번호 감지 + 어노테이션 + 완성 PDF 생성
  - regenerate_jobs : 사용자 편집(edited_images) 반영한 PDF 재생성

/app/services 의 ImageExtractor, ImageAnnotator, PDFGenerator 를 재사용한다.
각 서비스는 output_dir 을 필수로 받으므로 tempdir 을 전달한다.

메시지 포맷:
  ocr_jobs        {"job_id": "uuid", "mappings": [{"number","label","selected"}]}
  regenerate_jobs {"job_id","parent_job_id","edited_images":{idx:path},"session_id","force_regenerate"}
"""
import os
import sys
import time
import json
import logging
import tempfile
import traceback
import datetime as dt
from pathlib import Path

from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('ocr')

sys.path.insert(0, '/srv')
from app.services.image_extractor import ImageExtractor  # noqa: E402
from app.services.image_annotator import ImageAnnotator  # noqa: E402
from app.services.pdf_generator import PDFGenerator  # noqa: E402

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
QUEUES = [q.strip() for q in os.environ.get('QUEUES', 'ocr_jobs,regenerate_jobs').split(',') if q.strip()]
VT = int(os.environ.get('VT_SECONDS', '900'))
IDLE_EXIT_AFTER = int(os.environ.get('IDLE_EXIT_AFTER', '300'))

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def rpc_read(queue):
    res = sb.rpc('pgmq_read', {'queue_name': queue, 'vt': VT, 'qty': 1}).execute()
    msgs = res.data or []
    return msgs[0] if msgs else None


def rpc_delete(queue, msg_id):
    sb.rpc('pgmq_delete', {'queue_name': queue, 'msg_id': msg_id}).execute()


def rpc_archive(queue, msg_id):
    sb.rpc('pgmq_archive', {'queue_name': queue, 'msg_id': msg_id}).execute()


def update_job(job_id, **fields):
    sb.table('jobs').update(fields).eq('id', job_id).execute()


def emit_event(job_id, event_type, payload=None):
    sb.table('job_events').insert({
        'job_id': job_id, 'event_type': event_type,
        'source': 'fly-ocr', 'payload': payload,
    }).execute()


import httpx

_AUTH_HEADERS = {'Authorization': f'Bearer {SUPABASE_KEY}', 'apikey': SUPABASE_KEY}


def storage_download(bucket: str, object_path: str, dest: Path):
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}"
    with httpx.Client(timeout=120) as cli:
        r = cli.get(url, headers=_AUTH_HEADERS)
        r.raise_for_status()
        dest.write_bytes(r.content)


def storage_upload(bucket: str, object_path: str, src_bytes: bytes, mime='application/octet-stream'):
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}"
    headers = {**_AUTH_HEADERS, 'Content-Type': mime, 'x-upsert': 'true'}
    with httpx.Client(timeout=300) as cli:
        r = cli.post(url, content=src_bytes, headers=headers)
        if r.status_code == 409 and 'already exists' in r.text.lower():
            r = cli.put(url, content=src_bytes, headers=headers)
        r.raise_for_status()


def _split_bucket(path: str):
    """'results/foo/bar' → ('results', 'foo/bar')"""
    bucket, _, rest = path.partition('/')
    return bucket, rest


def handle_ocr(msg: dict):
    job_id = msg['job_id']
    mappings_list = msg.get('mappings') or []
    selected_map = {m['number']: m['label'] for m in mappings_list if m.get('selected')}

    log.info('ocr start job=%s mappings_selected=%d', job_id, len(selected_map))
    emit_event(job_id, 'started')
    update_job(job_id, status='ocr_processing', progress=60, message='OCR 진행 중')

    job = sb.table('jobs').select('*').eq('id', job_id).single().execute().data
    extracted_records = job.get('extracted_images') or []        # [{page, path}]
    metadata = job.get('extracted_images_metadata') or []         # [{page, width, height, bbox, ...}]
    original_pdf_path = job.get('original_pdf_path') or ''        # 'uploads/{id}/original.pdf'

    with tempfile.TemporaryDirectory(prefix=f'ocr_{job_id}_') as tmp:
        tmp = Path(tmp)
        src_dir = tmp / 'src'; src_dir.mkdir()
        ann_dir = tmp / 'annotated'; ann_dir.mkdir()

        # 원본 PDF 다운로드
        local_pdf = tmp / 'input.pdf'
        if original_pdf_path:
            up_bucket, up_obj = _split_bucket(original_pdf_path)
            storage_download(up_bucket or 'uploads', up_obj, local_pdf)

        # 각 도면에 대해 OCR + 어노테이션
        extractor = ImageExtractor(output_dir=src_dir, ocr_languages=['ko', 'en'], use_gpu=False)
        annotator = ImageAnnotator(output_dir=ann_dir)

        annotated_records = []
        for rec in extracted_records:
            page = int(rec['page'])
            ex_path = rec['path']  # 'results/{id}/extracted/drawing_NNN.png' 또는 '{id}/extracted/...'
            ex_bucket, ex_obj = _split_bucket(ex_path) if '/' in ex_path else ('results', ex_path)
            if ex_bucket != 'results':
                # contracts: bucket prefix 없이 저장될 수도 있음
                ex_bucket, ex_obj = 'results', ex_path

            local_img = src_dir / f'drawing_{page:03d}.png'
            storage_download('results', ex_obj if ex_obj.startswith(f'{job_id}/') else ex_path, local_img)

            try:
                regions, _rotated = extractor.find_numbered_regions_with_rotation(str(local_img))
            except Exception as e:
                log.warning('ocr regions failed page=%d: %s', page, e)
                regions = []

            output_name = f'annotated_{page:03d}.png'
            try:
                annotator.annotate_image(
                    image_path=str(local_img),
                    numbered_regions=regions,
                    number_mappings=selected_map,
                    output_filename=output_name,
                )
            except Exception as e:
                log.warning('annotate failed page=%d: %s (원본 업로드로 폴백)', page, e)
                # 폴백: 원본을 annotated 디렉토리로 복사
                (ann_dir / output_name).write_bytes(local_img.read_bytes())

            ann_local = ann_dir / output_name
            ann_path = f'{job_id}/annotated/{output_name}'
            storage_upload('results', ann_path, ann_local.read_bytes(), mime='image/png')
            annotated_records.append({'page': page, 'path': ann_path})

        # 완성 PDF 생성
        completed_local = tmp / 'completed.pdf'
        try:
            PDFGenerator().create_annotated_pdf(
                original_pdf_path=local_pdf,
                extracted_images=metadata or extracted_records,
                annotated_images=[{'page': r['page'], 'path': str(ann_dir / f'annotated_{r["page"]:03d}.png')} for r in annotated_records],
                output_filename=completed_local,
            )
        except Exception as e:
            log.error('pdf generation failed: %s', traceback.format_exc())
            raise

        completed_path = f'{job_id}/completed.pdf'
        storage_upload('results', completed_path, completed_local.read_bytes(), mime='application/pdf')

    sb.table('jobs').update({
        'status': 'completed',
        'progress': 100,
        'annotated_images': annotated_records,
        'result_paths': {'completed_pdf': completed_path},
        'message': '완료',
        'completed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }).eq('id', job_id).execute()

    emit_event(job_id, 'completed', {'annotated': len(annotated_records), 'pdf': completed_path})
    log.info('ocr done job=%s annotated=%d', job_id, len(annotated_records))


def handle_regenerate(msg: dict):
    job_id = msg['job_id']
    parent_id = msg['parent_job_id']
    edited = msg.get('edited_images') or {}   # {index: 'results/{parent}/edited/N_sess.png' or similar}

    log.info('regenerate start job=%s parent=%s edits=%d', job_id, parent_id, len(edited))
    emit_event(job_id, 'started')
    update_job(job_id, status='regenerating', progress=30, message='PDF 재생성 중')

    parent = sb.table('jobs').select('*').eq('id', parent_id).single().execute().data
    annotated_base = parent.get('annotated_images') or []        # [{page, path}]
    metadata = parent.get('extracted_images_metadata') or []
    original_path = parent.get('original_pdf_path') or ''

    with tempfile.TemporaryDirectory(prefix=f'regen_{job_id}_') as tmp:
        tmp = Path(tmp)
        merged_dir = tmp / 'merged'; merged_dir.mkdir()

        local_pdf = tmp / 'input.pdf'
        if original_path:
            up_bucket, up_obj = _split_bucket(original_path)
            storage_download(up_bucket or 'uploads', up_obj, local_pdf)

        # 기본: 부모의 annotated 이미지 사용
        merged_records = []
        for rec in annotated_base:
            page = int(rec['page'])
            local = merged_dir / f'annotated_{page:03d}.png'
            storage_download('results', rec['path'], local)
            merged_records.append({'page': page, 'path': str(local)})

        # 편집본이 있으면 해당 인덱스/페이지 덮어쓰기
        # edited_images 의 key 가 imageIndex(str) 인지 page 인지는 프론트 계약에 따름.
        # save-edited-image 계약: imageIndex → 'results/{jobId}/edited/{idx}_{session}.png'
        # 편집 이미지가 어느 페이지에 해당하는지는 metadata 의 index → page 매핑으로 결정
        index_to_page = {int(m.get('index', i)): int(m.get('page', i)) for i, m in enumerate(metadata or [])}
        for idx_key, storage_path in edited.items():
            try:
                idx = int(idx_key)
            except (TypeError, ValueError):
                continue
            page = index_to_page.get(idx, idx)
            local = merged_dir / f'annotated_{page:03d}.png'
            storage_download('results', storage_path, local)

        # 재생성 PDF
        out_pdf = tmp / 'regenerated.pdf'
        PDFGenerator().create_annotated_pdf(
            original_pdf_path=local_pdf,
            extracted_images=metadata or annotated_base,
            annotated_images=merged_records,
            output_filename=out_pdf,
        )

        ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        regen_path = f'{parent_id}/regenerated_{ts}.pdf'
        storage_upload('results', regen_path, out_pdf.read_bytes(), mime='application/pdf')

    # 부모의 regenerated_pdfs 에 append
    parent_regens = parent.get('regenerated_pdfs') or []
    parent_regens.append({
        'path': regen_path,
        'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'regen_job_id': job_id,
    })
    sb.table('jobs').update({'regenerated_pdfs': parent_regens}).eq('id', parent_id).execute()

    sb.table('jobs').update({
        'status': 'completed',
        'progress': 100,
        'result_paths': {'regenerated_pdf': regen_path},
        'completed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }).eq('id', job_id).execute()

    emit_event(job_id, 'completed', {'regenerated': regen_path})
    log.info('regenerate done job=%s path=%s', job_id, regen_path)


def dispatch(queue: str, body: dict):
    if queue == 'ocr_jobs':
        handle_ocr(body)
    elif queue == 'regenerate_jobs':
        handle_regenerate(body)
    else:
        raise RuntimeError(f'unknown queue: {queue}')


def main():
    idle_since = None
    while True:
        got_one = False
        for queue in QUEUES:
            msg = rpc_read(queue)
            if msg is None:
                continue
            got_one = True
            idle_since = None
            body = msg.get('message') or {}
            job_id = body.get('job_id')
            try:
                dispatch(queue, body)
                rpc_delete(queue, msg['msg_id'])
            except Exception as e:
                log.error('%s failed: %s', queue, traceback.format_exc())
                if job_id:
                    try:
                        update_job(job_id, status='failed', error=str(e))
                        emit_event(job_id, 'failed', {'error': str(e), 'queue': queue})
                    except Exception:
                        pass
                if (msg.get('read_ct') or 0) >= 3:
                    rpc_archive(queue, msg['msg_id'])
            break

        if not got_one:
            if idle_since is None:
                idle_since = time.time()
            elif IDLE_EXIT_AFTER and (time.time() - idle_since) > IDLE_EXIT_AFTER:
                log.info('idle exit after %ds', IDLE_EXIT_AFTER)
                return
            time.sleep(5)


if __name__ == '__main__':
    main()
