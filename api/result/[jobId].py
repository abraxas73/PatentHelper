"""GET /api/result/[jobId]

응답: {
  jobId, status, filename, originalPdfUrl,
  extractedImages: [{page, url}], annotatedImages: [{page, url}],
  editedImages: {index: url}, completedPdfUrl, regeneratedPdfs: [{url, createdAt}],
  numberMappings, processingTime
}

signed URL은 매 호출마다 새로 발급 (만료 3600s).
"""
from http.server import BaseHTTPRequestHandler
import json

from _lib.supabase_client import sb


def sign(bucket: str, path: str, ttl: int = 3600) -> str | None:
    if not path:
        return None
    try:
        path = path.split(f'{bucket}/', 1)[-1] if path.startswith(f'{bucket}/') else path
        res = sb().storage.from_(bucket).create_signed_url(path, ttl)
        return res.get('signedURL') or res.get('signed_url')
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            job_id = self.path.rstrip('/').split('/')[-1].split('?')[0]
            res = sb().table('jobs').select('*').eq('id', job_id).single().execute()
            job = res.data
            if not job:
                return self._json(404, {'error': 'job not found'})

            def sign_img_list(items):
                out = []
                for item in (items or []):
                    if isinstance(item, dict) and item.get('path'):
                        out.append({'page': item.get('page'), 'url': sign('results', item['path'])})
                return out

            result = {
                'jobId': job['id'],
                'status': job['status'],
                'filename': job.get('filename'),
                'originalPdfUrl': sign('uploads', job.get('original_pdf_path', '')),
                'extractedImages': sign_img_list(job.get('extracted_images')),
                'annotatedImages': sign_img_list(job.get('annotated_images')),
                'editedImages': {
                    str(k): sign('results', v) for k, v in (job.get('edited_images') or {}).items()
                },
                'completedPdfUrl': sign('results', (job.get('result_paths') or {}).get('completed_pdf', '')),
                'regeneratedPdfs': [
                    {'url': sign('results', item.get('path', '')), 'createdAt': item.get('created_at')}
                    for item in (job.get('regenerated_pdfs') or [])
                ],
                'numberMappings': job.get('mappings', []),
                'processingTime': job.get('processing_time'),
            }

            status_code = 200 if job['status'] in ('completed',) else 202
            self._json(status_code, result)
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
