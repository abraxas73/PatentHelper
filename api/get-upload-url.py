"""POST /api/get-upload-url

요청: {"filename": "특허도면.pdf", "content_type": "application/pdf"}
응답: {"jobId": uuid, "uploadUrl": str, "uploadPath": str}

동작:
  1. jobs row 생성 (status='pending', filename 저장)
  2. uploads/{jobId}/original.pdf 로 signed upload URL 발급
  3. 프론트가 반환된 uploadUrl 로 PUT 직접 업로드

References:
  - 03_data_contracts.md D.1
"""
from http.server import BaseHTTPRequestHandler
import json
import uuid

from _lib.supabase_client import sb


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = json.loads(self.rfile.read(length) or b'{}')
            filename = body.get('filename')
            if not filename:
                return self._json(400, {'error': 'filename required'})

            job_id = str(uuid.uuid4())
            upload_path = f'{job_id}/original.pdf'

            sb().table('jobs').insert({
                'id': job_id,
                'status': 'pending',
                'filename': filename,
                'original_pdf_path': f'uploads/{upload_path}',
            }).execute()

            signed = sb().storage.from_('uploads').create_signed_upload_url(upload_path)

            self._json(200, {
                'jobId': job_id,
                'uploadUrl': signed['signed_url'],
                'uploadPath': upload_path,
            })
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status: int, body: dict):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
