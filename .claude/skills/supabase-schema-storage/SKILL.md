---
name: supabase-schema-storage
description: Supabase Postgres 스키마 설계, Storage 버킷/경로 컨벤션, RLS 정책, pgmq 큐 설정을 표준 템플릿에 따라 생성한다. DynamoDB 이력 이전 스크립트와 signed URL 발급 패턴도 포함한다. MCP 우선, 미연결 시 SQL 파일로 폴백.
---

# Supabase Schema & Storage

`supabase-data-engineer` 전용 스킬. Supabase 3요소(Postgres + Storage + pgmq)를 통일된 패턴으로 구축한다.

## 기본 원칙
- **MCP 우선**: `mcp__plugin_supabase_supabase__apply_migration`, `execute_sql`, `list_tables` 등 사용
- **SQL 파일 폴백**: MCP 미연결이면 `_workspace/supabase/migrations/{timestamp}_{name}.sql`로 생성
- **서버 롤 분리**: 프론트는 anon, 서버(Vercel Functions + Fly 워커)는 service_role
- **버킷 비공개**: 퍼블릭 버킷 금지. 항상 signed URL

## 1. jobs 테이블 (DynamoDB 대체)
```sql
create extension if not exists pgcrypto;
create extension if not exists pgmq;

create type job_status as enum (
  'pending',
  'extracting',
  'awaiting_mapping',
  'ocr_processing',
  'completed',
  'failed'
);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  status job_status not null default 'pending',
  original_pdf_path text,
  extracted_images jsonb not null default '[]'::jsonb,
  extracted_images_metadata jsonb not null default '[]'::jsonb,
  mappings jsonb not null default '[]'::jsonb,
  result_paths jsonb not null default '{}'::jsonb,
  regenerated_pdf_path text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_jobs_status_created on jobs (status, created_at desc);
create index idx_jobs_created on jobs (created_at desc);

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

create trigger trg_jobs_updated
before update on jobs
for each row execute function set_updated_at();
```

## 2. job_events 테이블 (감사/디버깅용 선택)
```sql
create table job_events (
  id bigserial primary key,
  job_id uuid not null references jobs(id) on delete cascade,
  event_type text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);
create index idx_job_events_job on job_events(job_id, created_at);
```

## 3. pgmq 큐
```sql
select pgmq.create('extract_jobs');
select pgmq.create('ocr_jobs');
-- DLQ 스타일 이동은 pgmq.archive 사용
```

**메시지 포맷 (03_data_contracts.md와 동기화)**
```json
// extract_jobs
{"job_id": "uuid", "pdf_path": "uploads/{job_id}/original.pdf"}

// ocr_jobs
{"job_id": "uuid", "mappings": [{"number": "111", "label": "예시"}]}
```

## 4. Storage 버킷
```sql
-- SQL로 생성 가능하지만, 실제로는 Supabase Dashboard 또는 MCP 관리 편의성 고려
insert into storage.buckets (id, name, public) values
  ('uploads', 'uploads', false),
  ('results', 'results', false)
on conflict (id) do nothing;
```

**경로 컨벤션**
```
uploads/{job_id}/original.pdf
results/{job_id}/drawings/drawing_{page:03d}.png
results/{job_id}/annotated/annotated_{page:03d}.png
results/{job_id}/completed.pdf
results/{job_id}/regenerated.pdf
```

## 5. RLS 정책
```sql
alter table jobs enable row level security;
alter table job_events enable row level security;

-- service_role은 bypass(기본). anon은 접근 금지
-- 필요 시 프론트에서 최근 N개 이력 조회하려면 view + policy 추가
```

## 6. Storage 접근 패턴
### 업로드 signed URL (서버에서 발급)
```python
# supabase-py 예시
res = supabase.storage.from_('uploads').create_signed_upload_url(
    path=f'{job_id}/original.pdf'
)
# res['signed_url'] 프론트로 전달, 프론트가 PUT
```

### 다운로드 signed URL
```python
res = supabase.storage.from_('results').create_signed_url(
    path=f'{job_id}/completed.pdf',
    expires_in=3600  # 1시간
)
```

## 7. DynamoDB 이력 이전 (선택)
가능 여부 판단:
- `deploy_aws` 내 DynamoDB 테이블명과 키 스키마 확인
- boto3로 scan → 변환 → Supabase insert
- 실패하면 clean으로 포기

```python
# _workspace/supabase/dynamodb_import.py (스켈레톤)
import boto3
from supabase import create_client

dynamo = boto3.resource('dynamodb', region_name='ap-northeast-2')
table = dynamo.Table('patent-helper-jobs')

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def convert(item):
    # DynamoDB 타입(L/M/S/N) → Python primitive 변환
    # Decimal → float
    return {
        'id': item['jobId'],
        'status': map_status(item.get('status', 'UNKNOWN')),
        'original_pdf_path': item.get('originalPdfS3Key'),
        'mappings': item.get('mappings', []),
        # ...
        'created_at': item.get('createdAt'),
    }

resp = table.scan()
for it in resp['Items']:
    try:
        sb.table('jobs').upsert(convert(it)).execute()
    except Exception as e:
        print(f'skip {it.get("jobId")}: {e}')
```

## 8. MCP 사용 패턴
```
1. mcp__plugin_supabase_supabase__list_projects → 타겟 프로젝트 확인
2. mcp__plugin_supabase_supabase__apply_migration (name, query) → 스키마 적용
3. mcp__plugin_supabase_supabase__execute_sql (query) → 검증 SELECT
4. mcp__plugin_supabase_supabase__list_tables → 결과 확인
5. mcp__plugin_supabase_supabase__get_advisors (type='security') → RLS 누락 체크
```

## 9. 검증 체크리스트
- [ ] `jobs` 테이블 CRUD 가능
- [ ] pgmq.send / read / delete 왕복 성공
- [ ] signed upload URL로 업로드 성공
- [ ] signed download URL로 다운로드 성공 (한글 파일명 포함)
- [ ] `get_advisors` 보안 경고 없음
- [ ] RLS 활성화 확인

## 출력 산출물
- `_workspace/supabase/migrations/0001_init.sql`
- `_workspace/supabase/seed.sql`
- `_workspace/supabase/rls_policies.sql`
- `_workspace/supabase/dynamodb_import.py` (선택)
- `_workspace/supabase/README.md` — 사용 패턴 및 경로 컨벤션

## 재사용 참고
- SQL은 멱등(idempotent)하게 — `if not exists`, `on conflict`
- 메시지 포맷 변경은 반드시 architect 승인 + `03_data_contracts.md` 먼저 갱신
