import { useMemo, useState } from 'react'
import type { 대화, 사업행 } from '../api'

type Props = {
  conversations: 대화[]
  currentId: number | null
  businesses: 사업행[]
  onSelect: (id: number) => void
  onNew: () => void
  onNewWithProject: (사업_id: number) => void
  onDelete: (id: number) => void
}

export default function Sidebar({
  conversations,
  currentId,
  businesses,
  onSelect,
  onNew,
  onNewWithProject,
  onDelete,
}: Props) {
  const [검색어, set검색어] = useState('')
  const [프로젝트패널_열림, set프로젝트패널_열림] = useState(false)
  const [프로젝트_검색어, set프로젝트_검색어] = useState('')
  const [삭제확인_id, set삭제확인_id] = useState<number | null>(null)

  const 사업_라벨_목록 = useMemo(
    () =>
      businesses
        .map((b) => ({ id: b.id, 라벨: `${b.업체명 ?? ''} · ${b.용역명 ?? ''}`.replace(/^ · /, '') }))
        .sort((a, b) => a.라벨.localeCompare(b.라벨)),
    [businesses],
  )

  const 프로젝트_후보 = useMemo(() => {
    const q = 프로젝트_검색어.trim().toLowerCase()
    const list = q ? 사업_라벨_목록.filter((b) => b.라벨.toLowerCase().includes(q)) : 사업_라벨_목록
    return list.slice(0, 30)
  }, [사업_라벨_목록, 프로젝트_검색어])

  const 필터된_목록 = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    if (!q) return conversations
    return conversations.filter((c) => (c.제목 ?? '').toLowerCase().includes(q))
  }, [conversations, 검색어])

  const { 프로젝트별, 일반 } = useMemo(() => {
    const 프로젝트별 = new Map<number, 대화[]>()
    const 일반: 대화[] = []
    for (const c of 필터된_목록) {
      if (c.사업_id) {
        if (!프로젝트별.has(c.사업_id)) 프로젝트별.set(c.사업_id, [])
        프로젝트별.get(c.사업_id)!.push(c)
      } else {
        일반.push(c)
      }
    }
    return { 프로젝트별, 일반 }
  }, [필터된_목록])

  function 대화_행(d: 대화) {
    const 선택됨 = d.id === currentId
    return (
      <div key={d.id} className={`conv-row ${선택됨 ? 'conv-row-active' : ''}`}>
        <button className="conv-row-title" onClick={() => onSelect(d.id)}>
          {d.제목 || `새 대화 (${d.생성일시.slice(0, 16)})`}
        </button>
        <button className="conv-row-delete" title="이 대화 삭제" onClick={() => set삭제확인_id(d.id)}>
          🗑
        </button>
      </div>
    )
  }

  return (
    <div className="sidebar">
      <button className="btn btn-primary btn-block" onClick={onNew}>
        ＋ 새 대화
      </button>

      <div className="project-popover-wrap">
        <button
          className="btn btn-secondary btn-block"
          onClick={() => set프로젝트패널_열림((v) => !v)}
        >
          📁 프로젝트로 새 대화
        </button>
        {프로젝트패널_열림 && (
          <div className="project-popover">
            <p className="sidebar-caption">사업현황의 특정 사업에 연결된 대화를 시작합니다.</p>
            <input
              className="text-input"
              placeholder="업체명·용역명 검색"
              value={프로젝트_검색어}
              onChange={(e) => set프로젝트_검색어(e.target.value)}
            />
            <div className="project-candidate-list">
              {프로젝트_후보.length === 0 && <p className="sidebar-caption">일치하는 사업이 없습니다.</p>}
              {프로젝트_후보.map((b) => (
                <button
                  key={b.id}
                  className="conv-row-title project-candidate-row"
                  onClick={() => {
                    onNewWithProject(b.id)
                    set프로젝트패널_열림(false)
                    set프로젝트_검색어('')
                  }}
                >
                  {b.라벨 || `사업 #${b.id}`}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <input
        className="text-input search-input"
        placeholder="🔍 대화 검색"
        value={검색어}
        onChange={(e) => set검색어(e.target.value)}
      />

      <div className="conv-list">
        {필터된_목록.length === 0 && <p className="sidebar-caption">검색 결과가 없습니다.</p>}
        {[...프로젝트별.entries()].map(([사업_id, 목록]) => {
          const 라벨 = businesses.find((b) => b.id === 사업_id)
          const 표시라벨 = 라벨 ? `${라벨.업체명} · ${라벨.용역명}` : `사업 #${사업_id}`
          return (
            <div key={사업_id} className="conv-group">
              <p className="conv-group-label">📁 {표시라벨}</p>
              {목록.map(대화_행)}
            </div>
          )
        })}
        {일반.length > 0 && (
          <div className="conv-group">
            {프로젝트별.size > 0 && <p className="conv-group-label">💬 일반 대화</p>}
            {일반.map(대화_행)}
          </div>
        )}
      </div>

      {삭제확인_id !== null && (
        <div className="delete-confirm">
          <p className="proposal-warning">
            '{conversations.find((c) => c.id === 삭제확인_id)?.제목 || ''}' 대화를 삭제할까요? 되돌릴 수
            없습니다.
          </p>
          <div className="proposal-actions">
            <button
              className="btn btn-primary"
              onClick={() => {
                onDelete(삭제확인_id)
                set삭제확인_id(null)
              }}
            >
              삭제
            </button>
            <button className="btn btn-secondary" onClick={() => set삭제확인_id(null)}>
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
