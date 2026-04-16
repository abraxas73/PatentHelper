"""POST /api/save-edited-image

요청: {"jobId": uuid, "imageIndex": int, "editedData": "data:image/png;base64,...", "sessionId": str?}
응답: {imageIndex, s3Key, url}

동작:
  1. data URL에서 base64 디코드
  2. Storage `results` 버킷에 edited/{jobId}/{index}_{session}.png 업로드
  3. jobs.edited_images[str(index)] = path 업데이트
  4. signed URL 반환 (1h)
"""
from http.server import BaseHTTPRequestHandler
import json
import base64
import uuid
import re

import os
from supabase import create_client

_sb_cache = None
def sb():
    global _sb_cache
    if _sb_cache is None:
        _sb_cache = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    return _sb_cache


DATA_URL_RE = re.compile(r'^data:image/\w+;base64,(.+)$')


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
            job_id = body.get('jobId')
            index = body.get('imageIndex')
            data_url = body.get('editedData')
            session = body.get('sessionId') or uuid.uuid4().hex[:8]
            if not (job_id and data_url is not None and index is not None):
                return self._json(400, {'error': 'jobId, imageIndex, editedData required'})

            m = DATA_URL_RE.match(data_url)
            if not m:
                return self._json(400, {'error': 'invalid data URL'})
            raw = base64.b64decode(m.group(1))

            path = f'{job_id}/edited/{int(index)}_{session}.png'
            sb().storage.from_('results').upload(
                path, raw,
                file_options={'content-type': 'image/png', 'upsert': 'true'},
            )

            job = sb().table('jobs').select('edited_images').eq('id', job_id).single().execute().data or {}
            edited = dict(job.get('edited_images') or {})
            edited[str(int(index))] = path
            sb().table('jobs').update({'edited_images': edited}).eq('id', job_id).execute()

            signed = sb().storage.from_('results').create_signed_url(path, 3600)
            url = signed.get('signedURL') or signed.get('signed_url')

            self._json(200, {'imageIndex': int(index), 's3Key': path, 'url': url})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
