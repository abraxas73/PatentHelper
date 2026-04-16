"""POST /api/regenerate-pdf

요청: {"jobId": uuid (부모), "sessionId": str?, "editedImages": {idx: path}?, "forceRegenerate": bool?}
응답: {regenerationJobId, status: "regenerating"}

동작:
  1. 부모 jobs row 확인
  2. 새 jobs row 생성 (status='regenerating', parent_job_id=부모)
  3. pgmq regenerate_jobs 발행
"""
from http.server import BaseHTTPRequestHandler
import json
import uuid

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
            parent_job_id = body.get('jobId')
            session_id = body.get('sessionId')
            edited_images = body.get('editedImages') or {}
            force = bool(body.get('forceRegenerate'))
            if not parent_job_id:
                return self._json(400, {'error': 'jobId required'})

            parent = sb().table('jobs').select('id, filename, user_id').eq('id', parent_job_id).single().execute().data
            if not parent:
                return self._json(404, {'error': 'parent job not found'})

            regen_id = str(uuid.uuid4())
            sb().table('jobs').insert({
                'id': regen_id,
                'parent_job_id': parent_job_id,
                'user_id': parent.get('user_id'),
                'status': 'regenerating',
                'filename': parent.get('filename'),
                'progress': 10,
            }).execute()

            enqueue('regenerate_jobs', {
                'job_id': regen_id,
                'parent_job_id': parent_job_id,
                'edited_images': edited_images,
                'session_id': session_id,
                'force_regenerate': force,
            })
            sb().table('job_events').insert({
                'job_id': regen_id, 'event_type': 'enqueued', 'source': 'vercel',
                'payload': {'queue': 'regenerate_jobs', 'parent': parent_job_id}
            }).execute()

            self._json(200, {'regenerationJobId': regen_id, 'status': 'regenerating'})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
