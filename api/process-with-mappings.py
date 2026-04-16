"""POST /api/process-with-mappings

요청: {"jobId": "uuid", "mappings": [{"number":"111","label":"예시","selected":true}]}
응답: {"jobId": uuid, "status": "ocr_processing"}

동작:
  1. jobs row 확인, status가 awaiting_mapping 이어야 이상적 (검증은 유연하게)
  2. jobs.mappings 업데이트 + status → ocr_processing
  3. pgmq ocr_jobs 큐에 {job_id, mappings} 발행
"""
from http.server import BaseHTTPRequestHandler
import json

import os
from supabase import create_client

_sb_cache = None
def sb():
    global _sb_cache
    if _sb_cache is None:
        _sb_cache = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    return _sb_cache

def enqueue(queue, payload):
    return sb().rpc('pgmq_send', {'queue_name': queue, 'msg': payload}).execute().data


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
            job_id = body.get('jobId')
            mappings = body.get('mappings')
            if not job_id or mappings is None:
                return self._json(400, {'error': 'jobId and mappings required'})
            if not isinstance(mappings, list):
                return self._json(400, {'error': 'mappings must be array'})

            job = sb().table('jobs').select('id, status').eq('id', job_id).single().execute().data
            if not job:
                return self._json(404, {'error': 'job not found'})

            sb().table('jobs').update({
                'mappings': mappings,
                'status': 'ocr_processing',
                'progress': 50,
            }).eq('id', job_id).execute()

            enqueue('ocr_jobs', {'job_id': job_id, 'mappings': mappings})
            sb().table('job_events').insert({
                'job_id': job_id, 'event_type': 'enqueued', 'source': 'vercel',
                'payload': {'queue': 'ocr_jobs', 'mapping_count': len(mappings)}
            }).execute()

            self._json(200, {'jobId': job_id, 'status': 'ocr_processing'})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
