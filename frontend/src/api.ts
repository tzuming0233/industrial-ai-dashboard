import { fetchEventSource } from '@microsoft/fetch-event-source'

export const API_BASE = import.meta.env.VITE_API_BASE_URL as string

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// 회원가입/로그인은 실패 사유(이름 중복 409, 비밀번호 불일치 401 등)를 화면에
// 그대로 보여줘야 해서, 공용 api()가 버리는 응답 본문의 detail을 직접 읽는다.
async function _인증_요청(path: string, 이름: string, 비밀번호: string): Promise<{ ok: boolean; 이름: string }> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 이름, 비밀번호 }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const signup = (이름: string, 비밀번호: string) => _인증_요청('/api/signup', 이름, 비밀번호)

export const login = (이름: string, 비밀번호: string) => _인증_요청('/api/login', 이름, 비밀번호)

export const logout = () => api<{ ok: boolean }>('/api/logout', { method: 'POST' })

export const getMe = () => api<{ 인증됨: boolean; 이름: string | null }>('/api/me')

export type 대화 = {
  id: number
  제목: string | null
  생성일시: string
  마지막_활동일시: string
  사업_id: number | null
  사업_라벨: string | null
}

export type 메시지 = { role: 'user' | 'assistant'; content: string }

export type 제안요약 = {
  유형: string
  경고?: string[]
  행?: Record<string, unknown>[]
  변경?: { 필드: string; 이전값: unknown; 새값: unknown }[]
  관계?: { 노드1: string; 노드2: string; 관계유형: string; 설명: string }[]
  대상id?: number
  제목?: string
  오류?: string
}

export type 대기중_제안 = { 요약: 제안요약; action_token: string }

export type 사업행 = {
  id: number
  구분: string
  업체명: string
  용역명: string
  사업구분: string
  담당자?: string
  주관참여구분?: string
  사업단계: string
  진행률: number
  시작일?: string | null
  종료일?: string | null
  계약금액: number
  기수입금액: number
  당해년도수입금액: number
}

// '데이터 관리' 탭의 편집 테이블용 — 저장 전 새 행은 id가 아직 없다.
export type 편집_사업행 = Omit<사업행, 'id'> & { id: number | null }

export type 연간목표행 = { id: number; 연도: number; 목표매출: number; 목표손익: number }

export type 투입인력행 = { id: number; 사업_id: number; 이름: string; 역할: string | null }

export type 건수행 = { 건수: number; [key: string]: unknown }

export type 마감임박행 = {
  업체명: string
  용역명: string
  종료일: string
  'D-day': number
  사업단계: string
}

export type 대시보드요약 = {
  전체_건수: number
  사업구분_수: number
  구분_수: number
  평균_진행률: number
  올해_목표: {
    연도: number
    목표매출: number | null
    실적_매출: number
    매출_달성률: number | null
  }
  사업구분별_건수: 건수행[]
  구분별_건수: 건수행[]
  사업단계별_건수: 건수행[]
  담당자별_건수: 건수행[]
  마감임박: 마감임박행[]
}

export type 이력행 = { 사업_id: number; 유형: string; 내용: string; 작성일시: string }

export type 온톨로지_노드 = {
  id: number
  유형: string
  이름: string
  사업_id: number | null
  노트_id: number | null
  생성일시: string
}

export type 온톨로지_관계 = {
  id: number
  출발_노드_id: number
  도착_노드_id: number
  관계유형: string
  설명: string | null
  작성자: string | null
  생성일시: string
}

export type 노트_요약 = {
  id: number
  제목: string
  태그: string | null
  생성일시: string
  수정일시: string
}

export type 노트 = 노트_요약 & {
  내용: string | null
  위키_내용: string | null
  고정컨텍스트?: number | boolean
  최근수정자?: string | null
}

export type 노트_버전행 = {
  id: number
  제목: string
  저장일시: string
  작성자: string
}

export const getNotes = () => api<노트_요약[]>('/api/notes')

export const getNote = (id: number) => api<노트>(`/api/notes/${id}`)

export const createNote = (제목: string, 내용 = '', 태그 = '') =>
  api<{ id: number }>('/api/notes', {
    method: 'POST',
    body: JSON.stringify({ 제목, 내용, 태그 }),
  })

export const updateNote = (
  id: number,
   변경: Partial<{
    제목: string
    내용: string
    위키_내용: string | null
    태그: string
    고정컨텍스트: boolean
  }>,
) =>
  api<{ ok: boolean }>(`/api/notes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(변경),
  })

export const deleteNote = (id: number) => api<{ ok: boolean }>(`/api/notes/${id}`, { method: 'DELETE' })

export const organizeNote = (id: number) =>
  api<{ 위키_내용: string }>(`/api/notes/${id}/organize`, { method: 'POST' })

export const getNoteVersions = (id: number) => api<노트_버전행[]>(`/api/notes/${id}/versions`)

export const restoreNoteVersion = (noteId: number, versionId: number) =>
  api<{ ok: boolean }>(`/api/notes/${noteId}/versions/${versionId}/restore`, { method: 'POST' })

export const listConversations = () => api<대화[]>('/api/conversations')

export const createConversation = (사업_id: number | null = null) =>
  api<{ id: number }>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ 사업_id }),
  })

export const deleteConversation = (id: number) =>
  api<{ ok: boolean }>(`/api/conversations/${id}`, { method: 'DELETE' })

export const getMessages = (id: number) =>
  api<{
    메시지: 메시지[]
    연결된_사업_id: number | null
    사업_라벨: string | null
    제안: 대기중_제안 | null
  }>(`/api/conversations/${id}/messages`)

export const applyProposal = (id: number, action_token: string) =>
  api<{ 적용됨: boolean; 메시지?: string }>(`/api/conversations/${id}/proposal/apply`, {
    method: 'POST',
    body: JSON.stringify({ action_token }),
  })

export const cancelProposal = (id: number, action_token: string) =>
  api<{ 취소됨: boolean }>(`/api/conversations/${id}/proposal/cancel`, {
    method: 'POST',
    body: JSON.stringify({ action_token }),
  })

export const getBusiness = () => api<사업행[]>('/api/business')

export const getDashboardSummary = () => api<대시보드요약>('/api/dashboard-summary')

export const getHistory = () => api<이력행[]>('/api/history')

export const getOntologyNodes = () => api<온톨로지_노드[]>('/api/ontology/nodes')

export const getOntologyRelations = () => api<온톨로지_관계[]>('/api/ontology/relations')

export const addOntologyRelationDirect = (node1_id: number, node2_id: number, relation_type: string) =>
  api<{ ok: boolean }>('/api/ontology/relations/direct', {
    method: 'POST',
    body: JSON.stringify({ node1_id, node2_id, relation_type }),
  })

export const deleteOntologyRelation = (id: number) =>
  api<{ ok: boolean }>(`/api/ontology/relations/${id}`, { method: 'DELETE' })

export const resetOntology = () => api<{ ok: boolean }>('/api/ontology/reset', { method: 'POST' })

export const saveBusinessRows = (행: 편집_사업행[], 작성자: string) =>
  api<{ ok: boolean }>('/api/business/save', {
    method: 'POST',
    body: JSON.stringify({ 행, 작성자 }),
  })

export const getAnnualTargets = () => api<연간목표행[]>('/api/targets')

export const saveAnnualTarget = (연도: number, 목표매출: number, 목표손익: number) =>
  api<{ ok: boolean }>('/api/targets', {
    method: 'POST',
    body: JSON.stringify({ 연도, 목표매출, 목표손익 }),
  })

export const getStaffing = (사업_id: number) => api<투입인력행[]>(`/api/staffing/${사업_id}`)

export const addStaffing = (사업_id: number, 이름: string, 역할: string) =>
  api<{ ok: boolean }>('/api/staffing', {
    method: 'POST',
    body: JSON.stringify({ 사업_id, 이름, 역할 }),
  })

export const deleteStaffing = (id: number) => api<{ ok: boolean }>(`/api/staffing/${id}`, { method: 'DELETE' })

export async function exportXlsx(행: Record<string, unknown>[], 파일명: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/export/xlsx`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 행 }),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 파일명
  a.click()
  URL.revokeObjectURL(url)
}

export function exportCsv(행: Record<string, unknown>[], 파일명: string): void {
  if (행.length === 0) return
  const 컬럼 = Object.keys(행[0])
  const 줄들 = [
    컬럼.join(','),
    ...행.map((row) =>
      컬럼.map((c) => `"${String(row[c] ?? '').replace(/"/g, '""')}"`).join(','),
    ),
  ]
  const csv = '﻿' + 줄들.join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 파일명
  a.click()
  URL.revokeObjectURL(url)
}

export type 생성_파일 = { id: number; 파일명: string; mime타입: string }

export const fileDownloadUrl = (id: number) => `${API_BASE}/api/files/${id}`

// html/svg/이미지는 백엔드가 미리보기용으로 항상 Content-Disposition: inline을
// 내려서, 그냥 <a href download>로는(특히 프론트/백엔드가 다른 서브도메인이라
// 크로스 오리진이라) 새 탭 열람으로만 동작하고 다운로드가 안 될 수 있다 —
// exportXlsx/exportCsv와 같은 방식으로 fetch해 blob으로 직접 저장한다.
export async function downloadGeneratedFile(id: number, 파일명: string): Promise<void> {
  const res = await fetch(fileDownloadUrl(id), { credentials: 'include' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 파일명
  a.click()
  URL.revokeObjectURL(url)
}

export async function uploadNoteAttachment(file: File): Promise<생성_파일> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/notes/attachments`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export type 명확화_선택지 = { label: string; description?: string }
export type 명확화_질문 = { 질문: string; 선택지: 명확화_선택지[] }

type 스트림_done = {
  text: string
  제안: 제안요약 | null
  action_token: string | null
  생성_파일: 생성_파일 | null
  질문_대기: 명확화_질문 | null
}

export function streamMessage(
  대화_id: number,
  message: string,
  file: File | null,
  handlers: {
    onToken: (text: string) => void
    onStatus?: (message: string) => void
    onDone: (data: 스트림_done) => void
    onError: (message: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  const form = new FormData()
  form.append('message', message)
  if (file) form.append('file', file)

  return fetchEventSource(`${API_BASE}/api/conversations/${대화_id}/messages/stream`, {
    method: 'POST',
    body: form,
    credentials: 'include',
    openWhenHidden: true,
    signal,
    async onopen(res) {
      if (!res.ok) throw new Error(`서버 응답 오류: ${res.status}`)
    },
    onmessage(ev) {
      if (ev.event === 'token') handlers.onToken((JSON.parse(ev.data) as { text: string }).text)
      else if (ev.event === 'status') handlers.onStatus?.((JSON.parse(ev.data) as { message: string }).message)
      else if (ev.event === 'done') handlers.onDone(JSON.parse(ev.data) as 스트림_done)
      else if (ev.event === 'error') handlers.onError((JSON.parse(ev.data) as { message: string }).message)
    },
    onerror(err) {
      handlers.onError(err instanceof Error ? err.message : String(err))
      throw err // fetch-event-source의 무한 재시도를 막는다 — 채팅 요청은 1회성이라 재시도 불필요.
    },
  })
}
