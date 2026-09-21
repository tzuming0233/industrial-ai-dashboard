import { useEffect, useMemo, useRef, useState } from 'react'
import type { 사업행 } from '../api'

export type 프로젝트_폼_값 = { 이름: string; 설명: string; 사업_id: number | null }

type Props = {
  제목: string
  확인_라벨: string
  초기값: 프로젝트_폼_값
  businesses: 사업행[]
  onSubmit: (값: 프로젝트_폼_값) => Promise<void>
  onClose: () => void
}

// 새 프로젝트 만들기 / 프로젝트 정보 편집에 함께 쓰는 모달 — 클로드 앱처럼 이름·설명만
// 먼저 받고, 지침과 지식 파일은 만든 뒤 프로젝트 페이지에서 채운다.
export default function ProjectForm({ 제목, 확인_라벨, 초기값, businesses, onSubmit, onClose }: Props) {
  const [이름, set이름] = useState(초기값.이름)
  const [설명, set설명] = useState(초기값.설명)
  const [사업_id, set사업_id] = useState<number | null>(초기값.사업_id)
  const [처리중, set처리중] = useState(false)
  const [오류, set오류] = useState<string | null>(null)
  const 이름_ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    이름_ref.current?.focus()
    function 키다운(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', 키다운)
    return () => document.removeEventListener('keydown', 키다운)
  }, [onClose])

  const 사업_옵션 = useMemo(
    () =>
      businesses
        .map((b) => ({ id: b.id, 라벨: `${b.업체명 ?? ''} · ${b.용역명 ?? ''}`.replace(/^ · /, '') }))
        .sort((a, b) => a.라벨.localeCompare(b.라벨)),
    [businesses],
  )

  async function 제출(e: React.FormEvent) {
    e.preventDefault()
    if (!이름.trim() || 처리중) return
    set처리중(true)
    set오류(null)
    try {
      await onSubmit({ 이름: 이름.trim(), 설명: 설명.trim(), 사업_id })
    } catch (err) {
      set오류(err instanceof Error ? err.message : String(err))
      set처리중(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal-card" onSubmit={제출} role="dialog" aria-modal="true" aria-label={제목}>
        <h3 className="modal-title">{제목}</h3>

        <label className="modal-field">
          <span>프로젝트 이름</span>
          <input
            ref={이름_ref}
            className="text-input"
            value={이름}
            maxLength={60}
            placeholder="예: 2026 AI 바우처 사업"
            onChange={(e) => set이름(e.target.value)}
          />
        </label>

        <label className="modal-field">
          <span>설명 (선택)</span>
          <textarea
            className="text-input"
            rows={3}
            value={설명}
            maxLength={300}
            placeholder="이 프로젝트에서 무엇을 다루나요?"
            onChange={(e) => set설명(e.target.value)}
          />
        </label>

        <label className="modal-field">
          <span>연결할 사업 (선택)</span>
          <select
            className="text-input"
            value={사업_id ?? ''}
            onChange={(e) => set사업_id(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">연결 안 함</option>
            {사업_옵션.map((b) => (
              <option key={b.id} value={b.id}>
                {b.라벨 || `사업 #${b.id}`}
              </option>
            ))}
          </select>
          <small>연결하면 이 프로젝트의 모든 대화에 그 사업의 현황(금액·기간·진행률 등)이 자동으로 참고돼요.</small>
        </label>

        {오류 && <p className="proposal-error">{오류}</p>}

        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            취소
          </button>
          <button type="submit" className="btn btn-primary" disabled={!이름.trim() || 처리중}>
            {처리중 ? '처리 중...' : 확인_라벨}
          </button>
        </div>
      </form>
    </div>
  )
}
