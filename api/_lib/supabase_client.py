"""Vercel Functions와 Fly 워커가 공통으로 쓰는 Supabase 클라이언트 팩토리.

환경변수:
    SUPABASE_URL                서비스 URL
    SUPABASE_SERVICE_ROLE_KEY   서버 전용. 절대 프론트 노출 금지.

사용:
    from _lib.supabase_client import sb
    sb().table('jobs').select('*').eq('id', job_id).single().execute()
"""
import os
from supabase import create_client, Client

_client: Client | None = None


def sb() -> Client:
    global _client
    if _client is None:
        url = os.environ['SUPABASE_URL']
        key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
        _client = create_client(url, key)
    return _client


def json_response(status: int, body: dict) -> tuple[int, str, dict]:
    """Vercel Python Functions 응답 헬퍼."""
    import json
    return status, json.dumps(body, ensure_ascii=False), {'Content-Type': 'application/json; charset=utf-8'}
