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
  업체명: string
  용역명: string
  사업구분: string
  사업단계: string
  진행률: number
  담당자?: string
  시작일?: string
  종료일?: string
  계약금액?: number
}

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

type 스트림_done = { text: string; 제안: 제안요약 | null; action_token: string | null }

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
