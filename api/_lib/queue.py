"""pgmq RPC 래퍼. 발행/소비 공통.

03_data_contracts.md B항의 메시지 포맷을 준수해야 한다.
"""
from .supabase_client import sb


def enqueue(queue: str, payload: dict) -> int:
    """pgmq.send 래퍼. msg_id 반환."""
    res = sb().rpc('pgmq_send', {'queue_name': queue, 'msg': payload}).execute()
    return res.data


def read_one(queue: str, vt_seconds: int = 600):
    """메시지 1개 읽기. vt_seconds 동안 가시성 잠금. 없으면 None."""
    res = sb().rpc('pgmq_read', {'queue_name': queue, 'vt': vt_seconds, 'qty': 1}).execute()
    msgs = res.data or []
    return msgs[0] if msgs else None


def delete_msg(queue: str, msg_id: int) -> bool:
    res = sb().rpc('pgmq_delete', {'queue_name': queue, 'msg_id': msg_id}).execute()
    return bool(res.data)


def archive_msg(queue: str, msg_id: int) -> bool:
    res = sb().rpc('pgmq_archive', {'queue_name': queue, 'msg_id': msg_id}).execute()
    return bool(res.data)
