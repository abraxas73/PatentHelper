"""POST /api/extract-mappings

요청: {"jobId": "uuid"}
응답: {"jobId": uuid, "status": "extracting"}

동작:
  1. jobs row가 존재하는지 확인 (get-upload-url 호출 이후여야 함)
  2. 원본 PDF가 실제로 Storage에 업로드되었는지 head 체크(optional)
  3. jobs.status → 'extracting' 업데이트
  4. pgmq extract_jobs 큐에 {job_id, pdf_path} 발행
"""
from http.server import BaseHTTPRequestHandler
import json

from _lib.supabase_client import sb
from _lib.queue import enqueue


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
            job_id = body.get('jobId')
            if not job_id:
                return self._json(400, {'error': 'jobId required'})

            job = sb().table('jobs').select('id, original_pdf_path, status').eq('id', job_id).single().execute().data
            if not job:
                return self._json(404, {'error': 'job not found'})
            if not job.get('original_pdf_path'):
                return self._json(400, {'error': 'original_pdf_path missing'})

            sb().table('jobs').update({'status': 'extracting', 'progress': 10}).eq('id', job_id).execute()

            enqueue('extract_jobs', {'job_id': job_id, 'pdf_path': job['original_pdf_path']})
            sb().table('job_events').insert({
                'job_id': job_id, 'event_type': 'enqueued', 'source': 'vercel',
                'payload': {'queue': 'extract_jobs'}
            }).execute()

            self._json(200, {'jobId': job_id, 'status': 'extracting'})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
