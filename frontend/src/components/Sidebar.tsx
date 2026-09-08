import { useEffect, useMemo, useRef, useState } from 'react'
import type { 대화, 사업행 } from '../api'
import Icon from './Icon'

type Props = {
  conversations: 대화[]
  currentId: number | null
  businesses: 사업행[]
  onSelect: (id: number) => void
  onNew: () => void
  onNewWithProject: (사업_id: number) => void
  onDelete: (id: number) => void
}

// 백엔드가 주는 생성일시는 타임존 없는 naive ISO 문자열(예: "2026-09-08T05:14:00")이라
// new Date()가 로컬 타임존으로 그대로 해석한다 — 서버/브라우저 모두 KST 기준이라 문제없다.
// 그대로 노출하면 "2026-09-08T05:14"처럼 원시 포맷이 보이므로 사람이 읽기 좋게 바꾼다.
function 생성일시_표시(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })
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
  const [강조_인덱스, set강조_인덱스] = useState(0)
  const [삭제확인_id, set삭제확인_id] = useState<number | null>(null)

  const 프로젝트_입력ref = useRef<HTMLInputElement>(null)
  const 프로젝트팝오버_ref = useRef<HTMLDivElement>(null)
  const 프로젝트버튼_ref = useRef<HTMLButtonElement>(null)

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

  // 검색어가 바뀌어 후보 목록이 달라지면 키보드 강조 위치를 맨 위로 되돌린다.
  useEffect(() => {
    set강조_인덱스(0)
  }, [프로젝트_후보])

  // 팝오버가 열리면 검색창에 바로 포커스하고(커맨드 팔레트 관례), 바깥을 클릭하면 닫는다.
  useEffect(() => {
    if (!프로젝트패널_열림) return
    프로젝트_입력ref.current?.focus()
    function 바깥클릭_처리(e: MouseEvent) {
      if (프로젝트팝오버_ref.current && !프로젝트팝오버_ref.current.contains(e.target as Node)) {
        set프로젝트패널_열림(false)
      }
    }
    document.addEventListener('mousedown', 바깥클릭_처리)
    return () => document.removeEventListener('mousedown', 바깥클릭_처리)
  }, [프로젝트패널_열림])

  function 프로젝트_선택(id: number) {
    onNewWithProject(id)
    set프로젝트패널_열림(false)
    set프로젝트_검색어('')
    프로젝트버튼_ref.current?.focus()
  }

  function 프로젝트_검색_키다운(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      set강조_인덱스((i) => Math.min(i + 1, 프로젝트_후보.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      set강조_인덱스((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const 대상 = 프로젝트_후보[강조_인덱스]
      if (대상) 프로젝트_선택(대상.id)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      set프로젝트패널_열림(false)
      프로젝트버튼_ref.current?.focus()
    }
  }

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
          {d.제목 || `새 대화 (${생성일시_표시(d.생성일시)})`}
        </button>
        <button
          className="conv-row-delete"
          title="이 대화 삭제"
          aria-label={`'${d.제목 || '제목 없음'}' 대화 삭제`}
          onClick={() => set삭제확인_id(d.id)}
        >
          <Icon name="trash" size={14} />
        </button>
      </div>
    )
  }

  return (
    <div className="sidebar">
      <button className="btn btn-primary btn-block sidebar-action-btn" onClick={onNew}>
        <Icon name="plus" size={15} />
        새 대화
      </button>

      <div className="project-popover-wrap" ref={프로젝트팝오버_ref}>
        <button
          ref={프로젝트버튼_ref}
          className="btn btn-secondary btn-block sidebar-action-btn"
          onClick={() => set프로젝트패널_열림((v) => !v)}
          aria-expanded={프로젝트패널_열림}
          aria-haspopup="listbox"
        >
          <Icon name="folder" size={15} />
          프로젝트로 새 대화
        </button>
        {프로젝트패널_열림 && (
          <div className="project-popover">
            <p className="sidebar-caption">사업현황의 특정 사업에 연결된 대화를 시작합니다.</p>
            <input
              ref={프로젝트_입력ref}
              className="text-input"
              placeholder="업체명·용역명 검색"
              value={프로젝트_검색어}
              onChange={(e) => set프로젝트_검색어(e.target.value)}
              onKeyDown={프로젝트_검색_키다운}
              role="combobox"
              aria-expanded
              aria-controls="project-candidate-listbox"
              aria-activedescendant={
                프로젝트_후보[강조_인덱스] ? `project-candidate-${프로젝트_후보[강조_인덱스].id}` : undefined
              }
            />
            <div className="project-candidate-list" role="listbox" id="project-candidate-listbox">
              {프로젝트_후보.length === 0 && <p className="sidebar-caption">일치하는 사업이 없습니다.</p>}
              {프로젝트_후보.map((b, i) => (
                <button
                  key={b.id}
                  id={`project-candidate-${b.id}`}
                  role="option"
                  aria-selected={i === 강조_인덱스}
                  className={`conv-row-title project-candidate-row ${
                    i === 강조_인덱스 ? 'project-candidate-row-active' : ''
                  }`}
                  onMouseEnter={() => set강조_인덱스(i)}
                  onClick={() => 프로젝트_선택(b.id)}
                >
                  {b.라벨 || `사업 #${b.id}`}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="search-input-wrap">
        <Icon name="search" size={14} />
        <input
          className="text-input search-input"
          placeholder="대화 검색"
          value={검색어}
          onChange={(e) => set검색어(e.target.value)}
        />
      </div>

      <div className="conv-list">
        {필터된_목록.length === 0 && <p className="sidebar-caption">검색 결과가 없습니다.</p>}
        {[...프로젝트별.entries()].map(([사업_id, 목록]) => {
          const 라벨 = businesses.find((b) => b.id === 사업_id)
          const 표시라벨 = 라벨 ? `${라벨.업체명} · ${라벨.용역명}` : `사업 #${사업_id}`
          return (
            <div key={사업_id} className="conv-group">
              <p className="conv-group-label">
                <Icon name="folder" size={12} />
                {표시라벨}
              </p>
              {목록.map(대화_행)}
            </div>
          )
        })}
        {일반.length > 0 && (
          <div className="conv-group">
            {프로젝트별.size > 0 && <p className="conv-group-label">일반 대화</p>}
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
