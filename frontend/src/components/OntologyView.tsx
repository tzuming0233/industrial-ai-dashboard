import { useEffect, useMemo, useRef, useState } from 'react'
import {
  addOntologyRelationDirect,
  deleteOntologyRelation,
  getBusiness,
  getOntologyNodes,
  getOntologyRelations,
  resetOntology,
  type 사업행,
  type 온톨로지_관계,
  type 온톨로지_노드,
} from '../api'
import OntologyGraph, { type 그래프_노드, type 그래프_엣지 } from './OntologyGraph'
import Icon from './Icon'
import { 고정_색상맵, 보조텍스트색 } from '../theme'

function 노드_표시라벨(이름: string, 유형: string, 최대길이 = 16): string {
  const 표시 = 유형 === '사업' && 이름.includes(' · ') ? 이름.split(' · ').slice(1).join(' · ') : 이름
  return 표시.length <= 최대길이 ? 표시 : 표시.slice(0, 최대길이) + '…'
}

type Props = {
  // 사이드 채팅에서 제안을 적용하는 등 DB가 바뀌었을 수 있을 때마다 값이 바뀌는 신호.
  // 이 화면을 보고 있는 동안 사이드 채팅으로 관계를 추가/삭제해도 다시 탭을 오가지
  // 않고 바로 반영되게 하기 위한 것 — 없으면 마운트 시 한 번만 불러온다.
  데이터_갱신_신호?: number
  // 그래프에서 노트에 연결된 노드를 클릭했을 때 "노트 열기"를 누르면 호출된다.
  onOpenNote?: (노트_id: number) => void
}

export default function OntologyView({ 데이터_갱신_신호, onOpenNote }: Props) {
  const [businesses, setBusinesses] = useState<사업행[]>([])
  const [nodes, setNodes] = useState<온톨로지_노드[]>([])
  const [relations, setRelations] = useState<온톨로지_관계[]>([])
  const [loading, setLoading] = useState(true)

  const [선택된_사업id, set선택된_사업id] = useState<number[]>([])
  const [필터_열림, set필터_열림] = useState(false)
  const [필터_검색어, set필터_검색어] = useState('')

  const [클릭된_엣지id, set클릭된_엣지id] = useState<number | null>(null)
  const [클릭된_노드id, set클릭된_노드id] = useState<number | null>(null)
  const [연결대상id, set연결대상id] = useState<number | null>(null)
  const [관계유형입력, set관계유형입력] = useState('')
  const [busy, setBusy] = useState(false)

  const [초기화_확인, set초기화_확인] = useState(false)

  async function 새로고침() {
    const [biz, n, r] = await Promise.all([getBusiness(), getOntologyNodes(), getOntologyRelations()])
    setBusinesses(biz)
    setNodes(n)
    setRelations(r)
  }

  useEffect(() => {
    새로고침().finally(() => setLoading(false))
  }, [])

  const 첫_렌더_완료 = useRef(false)
  useEffect(() => {
    if (!첫_렌더_완료.current) {
      첫_렌더_완료.current = true
      return
    }
    새로고침()
  }, [데이터_갱신_신호])

  const 사업_라벨_목록 = useMemo(
    () =>
      [...businesses]
        .map((b) => ({ id: b.id, 라벨: `${b.업체명} · ${b.용역명} (종료일 ${b.종료일 || '미정'})` }))
        .sort((a, b) => a.라벨.localeCompare(b.라벨)),
    [businesses],
  )

  const 필터_후보 = useMemo(() => {
    const q = 필터_검색어.trim().toLowerCase()
    return q ? 사업_라벨_목록.filter((b) => b.라벨.toLowerCase().includes(q)) : 사업_라벨_목록
  }, [사업_라벨_목록, 필터_검색어])

  const { 표시할_관계, 강조_노드id_집합 } = useMemo(() => {
    if (선택된_사업id.length === 0) return { 표시할_관계: relations, 강조_노드id_집합: new Set<number>() }
    const 강조 = new Set(nodes.filter((n) => n.사업_id && 선택된_사업id.includes(n.사업_id)).map((n) => n.id))
    const 관계 = 강조.size
      ? relations.filter((r) => 강조.has(r.출발_노드_id) || 강조.has(r.도착_노드_id))
      : []
    return { 표시할_관계: 관계, 강조_노드id_집합: 강조 }
  }, [nodes, relations, 선택된_사업id])

  const 표시할_노드 = useMemo(() => {
    const 연결된 = new Set([...표시할_관계.map((r) => r.출발_노드_id), ...표시할_관계.map((r) => r.도착_노드_id)])
    return nodes.filter((n) => 연결된.has(n.id))
  }, [nodes, 표시할_관계])

  const 유형_팔레트 = useMemo(() => 고정_색상맵([...new Set(nodes.map((n) => n.유형))]), [nodes])

  const 노드_이름맵 = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const 그래프_노드들: 그래프_노드[] = useMemo(
    () =>
      표시할_노드.map((n) => {
        const 강조됨 = 강조_노드id_집합.has(n.id)
        return {
          id: n.id,
          label: 노드_표시라벨(n.이름, n.유형),
          title: `${n.유형}: ${n.이름}`,
          color: 유형_팔레트[n.유형] ?? 보조텍스트색,
          shape: n.유형 === '사업' ? 'box' : 'dot',
          size: 강조됨 ? 34 : 22,
          borderWidth: 강조됨 ? 3 : 1,
        }
      }),
    [표시할_노드, 강조_노드id_집합, 유형_팔레트],
  )

  const 그래프_엣지들: 그래프_엣지[] = useMemo(
    () =>
      표시할_관계.map((r) => ({
        id: r.id,
        from: r.출발_노드_id,
        to: r.도착_노드_id,
        label: r.관계유형,
        title: r.설명 || '',
        color: '#FC5356',
      })),
    [표시할_관계],
  )

  function 사업_토글(id: number) {
    set선택된_사업id((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function 관계_삭제_실행() {
    if (클릭된_엣지id === null) return
    setBusy(true)
    try {
      await deleteOntologyRelation(클릭된_엣지id)
      set클릭된_엣지id(null)
      await 새로고침()
    } finally {
      setBusy(false)
    }
  }

  async function 관계_추가_실행() {
    if (클릭된_노드id === null || 연결대상id === null || !관계유형입력.trim()) return
    setBusy(true)
    try {
      await addOntologyRelationDirect(클릭된_노드id, 연결대상id, 관계유형입력.trim())
      set클릭된_노드id(null)
      set관계유형입력('')
      set연결대상id(null)
      await 새로고침()
    } finally {
      setBusy(false)
    }
  }

  async function 전체_초기화_실행() {
    setBusy(true)
    try {
      await resetOntology()
      set초기화_확인(false)
      await 새로고침()
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="page-loading">불러오는 중...</p>

  const 클릭된_엣지 = 클릭된_엣지id !== null ? relations.find((r) => r.id === 클릭된_엣지id) : null
  const 클릭된_노드 = 클릭된_노드id !== null ? 노드_이름맵.get(클릭된_노드id) : null

  return (
    <div className="page">
      <p className="sidebar-caption">
        AI 채팅에서 '이 사업은 저 사업의 후속이야', '이 두 사업은 같은 고객사야' 같은 식으로 이야기하거나,
        노트 본문에 <b>[[다른 노트 제목]]</b>을 쓰면 여기에 관계가 자동으로 쌓입니다. 사업뿐 아니라
        노트·고객사·기술·담당자 등 자유로운 개념도 노드가 될 수 있습니다. 그래프에서{' '}
        <b>노드를 클릭하면 관계 추가</b>, <b>선을 클릭하면 관계 삭제</b>를 할 수 있습니다.
      </p>

      <div className="project-popover-wrap">
        <button className="btn btn-secondary" onClick={() => set필터_열림((v) => !v)}>
          사업 선택 필터 {선택된_사업id.length > 0 ? `(${선택된_사업id.length}건 선택됨)` : ''}
        </button>
        {필터_열림 && (
          <div className="project-popover" style={{ width: 420 }}>
            <p className="sidebar-caption">선택한 사업들 중심으로 그래프를 좁혀서 보여줍니다. 비워두면 전체 표시.</p>
            <input
              className="text-input"
              placeholder="업체명·용역명 검색"
              value={필터_검색어}
              onChange={(e) => set필터_검색어(e.target.value)}
            />
            <div className="project-candidate-list">
              {필터_후보.map((b) => (
                <label key={b.id} className="ontology-filter-row">
                  <input type="checkbox" checked={선택된_사업id.includes(b.id)} onChange={() => 사업_토글(b.id)} />
                  {b.라벨}
                </label>
              ))}
            </div>
            {선택된_사업id.length > 0 && (
              <button className="btn btn-secondary" onClick={() => set선택된_사업id([])}>
                선택 초기화
              </button>
            )}
          </div>
        )}
      </div>

      {nodes.length === 0 || 표시할_관계.length === 0 ? (
        <div className="alert alert-info">
          {선택된_사업id.length > 0
            ? '선택한 사업들에 대해 아직 쌓인 관계가 없습니다. AI 채팅에서 이야기해보세요.'
            : '아직 쌓인 온톨로지가 없습니다. AI 채팅에서 이야기하거나 노트에 [[다른 노트 제목]]을 써보세요.'}
        </div>
      ) : (
        <>
          <div className="chart-box chart-box-full ontology-graph-box">
            <OntologyGraph
              nodes={그래프_노드들}
              edges={그래프_엣지들}
              height={460}
              onNodeClick={(id) => {
                set클릭된_노드id(id)
                set클릭된_엣지id(null)
                set연결대상id(null)
                set관계유형입력('')
              }}
              onEdgeClick={(id) => {
                set클릭된_엣지id(id)
                set클릭된_노드id(null)
              }}
            />
          </div>

          {클릭된_엣지 && (
            <div className="metric-card ontology-side-panel">
              <p>
                선택한 관계: <b>{노드_이름맵.get(클릭된_엣지.출발_노드_id)?.이름 ?? '?'}</b> —[
                {클릭된_엣지.관계유형}]→ <b>{노드_이름맵.get(클릭된_엣지.도착_노드_id)?.이름 ?? '?'}</b>
              </p>
              <div className="proposal-actions">
                <button className="btn btn-primary" disabled={busy} onClick={관계_삭제_실행}>
                  이 관계 삭제
                </button>
                <button className="btn btn-secondary" disabled={busy} onClick={() => set클릭된_엣지id(null)}>
                  닫기
                </button>
              </div>
            </div>
          )}

          {클릭된_노드 && (
            <div className="metric-card ontology-side-panel">
              <p>
                선택한 노드: <b>{클릭된_노드.이름}</b> ({클릭된_노드.유형}) — 다른 노드와 연결해보세요.
              </p>
              {클릭된_노드.노트_id != null && onOpenNote && (
                <button
                  className="btn btn-secondary"
                  onClick={() => onOpenNote(클릭된_노드.노트_id as number)}
                >
                  <Icon name="book" size={14} />
                  노트 열기
                </button>
              )}
              <select
                className="text-input"
                value={연결대상id ?? ''}
                onChange={(e) => set연결대상id(Number(e.target.value))}
              >
                <option value="">연결할 대상 선택</option>
                {nodes
                  .filter((n) => n.id !== 클릭된_노드id)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.이름} ({n.유형})
                    </option>
                  ))}
              </select>
              <input
                className="text-input"
                placeholder="관계유형 — 예: 후속사업, 동일고객, 유사기술"
                value={관계유형입력}
                onChange={(e) => set관계유형입력(e.target.value)}
              />
              <div className="proposal-actions">
                <button
                  className="btn btn-primary"
                  disabled={busy || !연결대상id || !관계유형입력.trim()}
                  onClick={관계_추가_실행}
                >
                  관계 추가
                </button>
                <button className="btn btn-secondary" disabled={busy} onClick={() => set클릭된_노드id(null)}>
                  닫기
                </button>
              </div>
            </div>
          )}

          <hr className="divider" />
          <p className="sidebar-caption">관계 {표시할_관계.length}건</p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>출발</th>
                  <th>관계유형</th>
                  <th>도착</th>
                  <th>설명</th>
                  <th>작성자</th>
                  <th>생성일시</th>
                </tr>
              </thead>
              <tbody>
                {[...표시할_관계]
                  .sort((a, b) => b.생성일시.localeCompare(a.생성일시))
                  .map((r) => (
                    <tr key={r.id}>
                      <td>{노드_이름맵.get(r.출발_노드_id)?.이름 ?? '?'}</td>
                      <td>{r.관계유형}</td>
                      <td>{노드_이름맵.get(r.도착_노드_id)?.이름 ?? '?'}</td>
                      <td>{r.설명}</td>
                      <td>{r.작성자}</td>
                      <td>{r.생성일시}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {nodes.length > 0 && (
        <details className="ontology-reset-box">
          <summary>온톨로지 전체 초기화</summary>
          <div className="alert alert-warning" style={{ marginTop: 8 }}>
            모든 사업/개념/노트 노드와 관계가 삭제됩니다. 되돌릴 수 없습니다(노트 자체는 남습니다).
          </div>
          <label className="radio-label" style={{ margin: '8px 0' }}>
            <input type="checkbox" checked={초기화_확인} onChange={(e) => set초기화_확인(e.target.checked)} />
            전체 초기화에 동의합니다.
          </label>
          <div>
            <button className="btn btn-primary" disabled={!초기화_확인 || busy} onClick={전체_초기화_실행}>
              온톨로지 전체 초기화
            </button>
          </div>
        </details>
      )}
    </div>
  )
}
