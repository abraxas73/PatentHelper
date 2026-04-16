// API endpoint configuration (Vercel/Fly/Supabase 이관)
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

// 베이스 URL 우선순위:
//   1) VITE_API_BASE (명시 지정)
//   2) 로컬이면 기존 FastAPI, 그 외(Vercel)는 same-origin /api
const ENV_API_BASE = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL
const LOCAL_API_URL = 'http://localhost:8000/api/v1'
const VERCEL_API_URL = '/api'

const API_URL = ENV_API_BASE || (isLocal ? LOCAL_API_URL : VERCEL_API_URL)

// Supabase (선택 사용 — 프론트에서 직접 Storage 등 접근 시)
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export default {
  API_URL,
  SUPABASE_URL,
  SUPABASE_ANON_KEY,
  isProduction,
  isLocal,
}
