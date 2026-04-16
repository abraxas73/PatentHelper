"""GET /api/status/[jobId]

응답: {jobId, status, progress, message, filename, totalPages}
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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            job_id = self.path.rstrip('/').split('/')[-1].split('?')[0]
            res = sb().table('jobs').select(
                'id, status, progress, message, filename, total_pages, error'
            ).eq('id', job_id).single().execute()
            data = res.data
            if not data:
                return self._json(404, {'error': 'job not found'})
            self._json(200, {
                'jobId': data['id'],
                'status': data['status'],
                'progress': data.get('progress', 0),
                'message': data.get('message'),
                'filename': data.get('filename'),
                'totalPages': data.get('total_pages'),
                'error': data.get('error'),
            })
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
