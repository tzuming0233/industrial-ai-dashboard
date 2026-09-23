import { useEffect, useMemo, useRef, useState } from 'react'
import { searchConversations, type 대화, type 대화_검색_결과, type 프로젝트 } from '../api'
import Icon from './Icon'

type Props = {
  conversations: 대화[]
  currentId: number | null
  projects: 프로젝트[]
  // 프로젝트 페이지를 보는 중이면 그 프로젝트를 사이드바에서 강조한다.
  현재_프로젝트_id: number | null
  onSelect: (id: number) => void
  onNew: () => void
  onOpenProject: (id: number) => void
  onNewProject: () => void
  onDelete: (id: number) => void
  onRename: (id: number, 제목: string) => Promise<void>
}

// 백엔드가 주는 생성일시는 타임존 없는 naive ISO 문자열(예: "2026-09-08T05:14:00")이라
// new Date()가 로컬 타임존으로 그대로 해석한다 — 서버/브라우저 모두 KST 기준이라 문제없다.
// 그대로 노출하면 "2026-09-08T05:14"처럼 원시 포맷이 보이므로 사람이 읽기 좋게 바꾼다.
function 생성일시_표시(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

// 클로드 앱 사이드바처럼 "오늘/어제/지난 7일/이전"으로 나눈다.
const _날짜_버킷_순서 = ['오늘', '어제', '지난 7일', '이전'] as const
type 날짜버킷 = (typeof _날짜_버킷_순서)[number]

function 날짜_버킷(iso: string): 날짜버킷 {
  const d = new Date(iso)
  d.setHours(0, 0, 0, 0)
  const 오늘 = new Date()
  오늘.setHours(0, 0, 0, 0)
  const 일차 = Math.round((오늘.getTime() - d.getTime()) / 86400000)
  if (일차 <= 0) return '오늘'
  if (일차 === 1) return '어제'
  if (일차 <= 7) return '지난 7일'
  return '이전'
}

export default function Sidebar({
  conversations,
  currentId,
  projects,
  현재_프로젝트_id,
  onSelect,
  onNew,
  onOpenProject,
  onNewProject,
  onDelete,
  onRename,
}: Props) {
  const [검색어, set검색어] = useState('')
  const [삭제확인_id, set삭제확인_id] = useState<number | null>(null)
  // 클로드 앱처럼 제목을 그 자리에서 바로 고친다(Enter/포커스 이탈=저장, Escape=취소).
  const [편집중_id, set편집중_id] = useState<number | null>(null)
  const [편집_값, set편집_값] = useState('')

  const [프로젝트_모두_보기, set프로젝트_모두_보기] = useState(false)

  // 클로드 앱의 대화 검색 — 제목뿐 아니라 대화 내용 전체를 서버에서 훑는다. 디바운스
  // 대기 중에는(또는 서버 결과가 아직 없으면) 아래 필터된_목록/필터된_프로젝트로
  // 즉석 클라이언트 필터링을 먼저 보여주고, 결과가 오면 그걸로 바꿔 보여준다.
  const [검색_결과, set검색_결과] = useState<대화_검색_결과[] | null>(null)
  const [검색_로딩, set검색_로딩] = useState(false)
  const 검색_토큰_ref = useRef(0)

  useEffect(() => {
    const q = 검색어.trim()
    if (!q) {
      set검색_결과(null)
      set검색_로딩(false)
      return
    }
    const 토큰 = ++검색_토큰_ref.current
    set검색_로딩(true)
    const 타이머 = window.setTimeout(() => {
      searchConversations(q)
        .then((결과) => {
          if (검색_토큰_ref.current === 토큰) {
            set검색_결과(결과)
            set검색_로딩(false)
          }
        })
        .catch(() => {
          if (검색_토큰_ref.current === 토큰) set검색_로딩(false)
        })
    }, 300)
    return () => window.clearTimeout(타이머)
  }, [검색어])

  function 검색결과_선택(대화_id: number) {
    onSelect(대화_id)
    set검색어('')
  }

  const 필터된_목록 = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    if (!q) return conversations
    return conversations.filter((c) => (c.제목 ?? '').toLowerCase().includes(q))
  }, [conversations, 검색어])

  const 프로젝트_이름_맵 = useMemo(() => new Map(projects.map((p) => [p.id, p.이름])), [projects])

  const 필터된_프로젝트 = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    return q ? projects.filter((p) => p.이름.toLowerCase().includes(q)) : projects
  }, [projects, 검색어])

  // 클로드 앱처럼 최근 대화는 프로젝트 소속 여부와 상관없이 한 목록에 날짜별로 모으고,
  // 프로젝트 대화에는 소속 프로젝트 이름을 작은 태그로 붙인다.
  const 일반 = 필터된_목록

  const 일반_날짜별 = useMemo(() => {
    const 맵 = new Map<날짜버킷, 대화[]>()
    for (const c of 일반) {
      const 버킷 = 날짜_버킷(c.마지막_활동일시)
      if (!맵.has(버킷)) 맵.set(버킷, [])
      맵.get(버킷)!.push(c)
    }
    return 맵
  }, [일반])

  function 편집_시작(d: 대화) {
    set편집_값(d.제목 || '')
    set편집중_id(d.id)
  }

  async function 편집_확정(d: 대화) {
    if (편집중_id !== d.id) return
    const 새제목 = 편집_값.trim()
    set편집중_id(null)
    if (!새제목 || 새제목 === (d.제목 ?? '')) return
    try {
      await onRename(d.id, 새제목)
    } catch {
      // 저장 실패 시 목록이 원래 제목 그대로 남으니 별도 처리 없이 조용히 넘어간다.
    }
  }

  function 대화_행(d: 대화) {
    const 선택됨 = d.id === currentId
    return (
      <div key={d.id} className={`conv-row ${선택됨 ? 'conv-row-active' : ''}`}>
        {편집중_id === d.id ? (
          <input
            className="conv-row-edit-input"
            value={편집_값}
            maxLength={60}
            autoFocus
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) => set편집_값(e.target.value)}
            onBlur={() => 편집_확정(d)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                편집_확정(d)
              } else if (e.key === 'Escape') {
                e.preventDefault()
                set편집중_id(null)
              }
            }}
            aria-label="대화 제목 편집"
          />
        ) : (
          <button
            className="conv-row-title"
            onClick={() => onSelect(d.id)}
            onDoubleClick={() => 편집_시작(d)}
            title="더블클릭하여 이름 바꾸기"
          >
            {d.제목 || `새 대화 (${생성일시_표시(d.생성일시)})`}
            {d.프로젝트_id && 프로젝트_이름_맵.get(d.프로젝트_id) && (
              <span className="conv-row-project-tag">{프로젝트_이름_맵.get(d.프로젝트_id)}</span>
            )}
          </button>
        )}
        <button
          className="conv-row-delete"
          title="이름 바꾸기"
          aria-label={`'${d.제목 || '제목 없음'}' 대화 이름 바꾸기`}
          onClick={() => 편집_시작(d)}
        >
          <Icon name="edit" size={14} />
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
        {검색_결과 !== null ? (
          <div className="conv-group">
            <p className="conv-group-label">검색 결과{!검색_로딩 && ` (${검색_결과.length})`}</p>
            {검색_로딩 && <p className="sidebar-caption">검색하는 중...</p>}
            {!검색_로딩 && 검색_결과.length === 0 && (
              <p className="sidebar-caption">일치하는 대화가 없습니다.</p>
            )}
            {검색_결과.map((r) => (
              <button
                key={r.대화_id}
                type="button"
                className="search-result-row"
                onClick={() => 검색결과_선택(r.대화_id)}
              >
                <span className="search-result-title-row">
                  <span className="search-result-title">{r.제목 || '새 대화'}</span>
                  {r.프로젝트_이름 && <span className="conv-row-project-tag">{r.프로젝트_이름}</span>}
                </span>
                {r.미리보기 && <span className="search-result-snippet">{r.미리보기}</span>}
              </button>
            ))}
          </div>
        ) : (
          <>
            <div className="conv-group">
              <div className="conv-group-head">
                <p className="conv-group-label">
                  <Icon name="folder" size={12} />
                  프로젝트
                </p>
                <button
                  type="button"
                  className="conv-group-add"
                  onClick={onNewProject}
                  title="새 프로젝트"
                  aria-label="새 프로젝트 만들기"
                >
                  <Icon name="plus" size={13} />
                </button>
              </div>
              {projects.length === 0 && (
                <button type="button" className="project-empty-cta" onClick={onNewProject}>
                  프로젝트를 만들어 지침과 자료를 모아보세요
                </button>
              )}
              {(프로젝트_모두_보기 ? 필터된_프로젝트 : 필터된_프로젝트.slice(0, 6)).map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`project-row ${p.id === 현재_프로젝트_id ? 'project-row-active' : ''}`}
                  onClick={() => onOpenProject(p.id)}
                  title={p.설명 || p.이름}
                >
                  <span className="project-row-name">{p.이름}</span>
                  {p.지식수 > 0 && <Icon name="file" size={12} />}
                  <span className="project-row-count">{p.대화수}</span>
                </button>
              ))}
              {필터된_프로젝트.length > 6 && (
                <button type="button" className="project-more-btn" onClick={() => set프로젝트_모두_보기((v) => !v)}>
                  {프로젝트_모두_보기 ? '접기' : `모두 보기 (${필터된_프로젝트.length})`}
                </button>
              )}
            </div>

            {필터된_목록.length === 0 && <p className="sidebar-caption">검색 결과가 없습니다.</p>}
            {_날짜_버킷_순서.map((버킷) => {
              const 목록 = 일반_날짜별.get(버킷)
              if (!목록 || 목록.length === 0) return null
              return (
                <div key={버킷} className="conv-group">
                  <p className="conv-group-label">{버킷}</p>
                  {목록.map(대화_행)}
                </div>
              )
            })}
          </>
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
