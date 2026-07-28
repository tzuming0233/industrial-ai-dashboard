import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL as string

type 사업행 = {
  id: number
  업체명: string
  용역명: string
  사업구분: string
  사업단계: string
  진행률: number
}

type 대시보드요약 = {
  전체_건수: number
  사업구분_수: number
  구분_수: number
  평균_진행률: number
  사업구분별_건수: { 사업구분: string; 건수: number }[]
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function App() {
  const [인증됨, set인증됨] = useState<boolean | null>(null)
  const [비밀번호, set비밀번호] = useState('')
  const [로그인에러, set로그인에러] = useState('')
  const [사업목록, set사업목록] = useState<사업행[] | null>(null)
  const [요약, set요약] = useState<대시보드요약 | null>(null)

  useEffect(() => {
    api<{ 인증됨: boolean }>('/api/me')
      .then((r) => set인증됨(r.인증됨))
      .catch(() => set인증됨(false))
  }, [])

  useEffect(() => {
    if (!인증됨) return
    api<사업행[]>('/api/business').then(set사업목록).catch(console.error)
    api<대시보드요약>('/api/dashboard-summary').then(set요약).catch(console.error)
  }, [인증됨])

  const 로그인 = async (e: React.FormEvent) => {
    e.preventDefault()
    set로그인에러('')
    try {
      await api('/api/login', { method: 'POST', body: JSON.stringify({ password: 비밀번호 }) })
      set인증됨(true)
    } catch {
      set로그인에러('비밀번호가 올바르지 않습니다.')
    }
  }

  if (인증됨 === null) return <p style={{ padding: 24 }}>확인 중...</p>

  if (!인증됨) {
    return (
      <div style={{ maxWidth: 320, margin: '80px auto', fontFamily: 'sans-serif' }}>
        <h2>산업AI팀 사업 통합관리</h2>
        <form onSubmit={로그인}>
          <input
            type="password"
            value={비밀번호}
            onChange={(e) => set비밀번호(e.target.value)}
            placeholder="비밀번호"
            style={{ width: '100%', padding: 8, marginBottom: 8 }}
          />
          <button type="submit" style={{ width: '100%', padding: 8 }}>
            로그인
          </button>
        </form>
        {로그인에러 && <p style={{ color: 'crimson' }}>{로그인에러}</p>}
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 720, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h2>산업AI팀 사업 통합관리 (Phase 0 — React/FastAPI 툴체인 검증)</h2>
      {요약 && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
          <div>전체 건수: <b>{요약.전체_건수}</b></div>
          <div>사업구분 수: <b>{요약.사업구분_수}</b></div>
          <div>구분 수: <b>{요약.구분_수}</b></div>
          <div>평균 진행률: <b>{요약.평균_진행률}%</b></div>
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>업체명</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>용역명</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>사업단계</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>진행률</th>
          </tr>
        </thead>
        <tbody>
          {사업목록?.map((row) => (
            <tr key={row.id}>
              <td>{row.업체명}</td>
              <td>{row.용역명}</td>
              <td>{row.사업단계}</td>
              <td>{row.진행률}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default App
