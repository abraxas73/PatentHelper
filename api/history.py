"""GET /api/history?userId=&limit=50&days=30

응답: {count, history: [{jobId, status, filename, createdAt, completedAt, progress, regeneratedCount}]}
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
from datetime import datetime, timedelta, timezone

from _lib.supabase_client import sb


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            user_id = (qs.get('userId') or [None])[0]
            limit = int((qs.get('limit') or ['50'])[0])
            days = int((qs.get('days') or ['365'])[0])
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            q = sb().table('jobs').select(
                'id, status, filename, created_at, completed_at, progress, regenerated_pdfs'
            ).gte('created_at', since).order('created_at', desc=True).limit(limit)
            if user_id:
                q = q.eq('user_id', user_id)

            data = q.execute().data or []
            history = [
                {
                    'jobId': r['id'],
                    'status': r['status'],
                    'filename': r.get('filename'),
                    'createdAt': r.get('created_at'),
                    'completedAt': r.get('completed_at'),
                    'progress': r.get('progress', 0),
                    'regeneratedCount': len(r.get('regenerated_pdfs') or []),
                }
                for r in data
            ]
            self._json(200, {'count': len(history), 'history': history})
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
