import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createNote,
  deleteNote,
  getNote,
  getNotes,
  getNoteVersions,
  getOntologyNodes,
  getOntologyRelations,
  organizeNote,
  restoreNoteVersion,
  updateNote,
  type 노트,
  type 노트_버전행,
  type 노트_요약,
  type 온톨로지_관계,
  type 온톨로지_노드,
} from '../api'
import Icon from '../components/Icon'
import OntologyGraph, { type 그래프_노드, type 그래프_엣지 } from '../components/OntologyGraph'
import OntologyView from '../components/OntologyView'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

type Props = {
  데이터_갱신_신호?: number
}

// `[[제목]]`은 그래프로 자동 연결되는 위키링크로, 본문에 쓴 `#태그`는 자동 인식되는
// 태그로 각각 클릭 가능한 링크로 바꿔서 보여준다 — 대괄호 안쪽은 통째로 먼저 매치되므로
// `[[제목#섹션]]`처럼 안에 #이 있어도 태그 규칙과 섞이지 않는다.
const 위키_렌더_패턴 = /\[\[([^\]]+)\]\]|#(?!\s)([\w가-힣]+)/g

function 위키텍스트_전처리(md: string): string {
  return md.replace(위키_렌더_패턴, (_match, 위키링크?: string, 태그?: string) => {
    if (위키링크 !== undefined) {
      const 표시 = 위키링크.split('|')[0].trim()
      const 링크제목 = 표시.split('#')[0].trim()
      return `[${표시}](#wikilink/${encodeURIComponent(링크제목)})`
    }
    return `[#${태그}](#tagchip/${encodeURIComponent(태그 ?? '')})`
  })
}

export default function Notes({ 데이터_갱신_신호 }: Props) {
  const [보기_모드, set보기_모드] = useState<'노트' | '그래프'>('노트')
  const [목록, set목록] = useState<노트_요약[]>([])
  const [loading, setLoading] = useState(true)
  const [검색어, set검색어] = useState('')
  const [선택id, set선택id] = useState<number | null>(null)
  const [선택된_노트, set선택된_노트] = useState<노트 | null>(null)
  const [상세_로딩, set상세_로딩] = useState(false)

  const [제목_입력, set제목_입력] = useState('')
  const [내용_입력, set내용_입력] = useState('')
  const [태그_입력, set태그_입력] = useState('')
  const [저장중, set저장중] = useState(false)

  const [뷰_모드, set뷰_모드] = useState<'원본' | '위키'>('원본')
  const [정리중, set정리중] = useState(false)
  const [정리_미리보기, set정리_미리보기] = useState<string | null>(null)

  const [삭제확인, set삭제확인] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [고정컨텍스트, set고정컨텍스트] = useState(false)
  const [버전목록, set버전목록] = useState<노트_버전행[]>([])
  const [이력_열림, set이력_열림] = useState(false)
  const [복원중, set복원중] = useState<number | null>(null)

  const [온톨로지_노드_목록, set온톨로지_노드_목록] = useState<온톨로지_노드[]>([])
  const [온톨로지_관계_목록, set온톨로지_관계_목록] = useState<온톨로지_관계[]>([])

  const { 지원됨: 음성지원, 듣는중, 토글: 음성_토글 } = useSpeechRecognition((text) => {
    set내용_입력((prev) => (prev ? `${prev} ${text}` : text))
  })

  async function 목록_새로고침() {
    const data = await getNotes()
    set목록(data)
    return data
  }

  useEffect(() => {
    목록_새로고침().finally(() => setLoading(false))
  }, [])

  async function 온톨로지_새로고침() {
    const [n, r] = await Promise.all([getOntologyNodes(), getOntologyRelations()])
    set온톨로지_노드_목록(n)
    set온톨로지_관계_목록(r)
  }

  useEffect(() => {
    온톨로지_새로고침()
  }, [])

  const 온톨로지_첫_렌더_완료 = useRef(false)
  useEffect(() => {
    if (!온톨로지_첫_렌더_완료.current) {
      온톨로지_첫_렌더_완료.current = true
      return
    }
    온톨로지_새로고침()
  }, [데이터_갱신_신호])

  useEffect(() => {
    if (선택id === null) {
      set선택된_노트(null)
      return
    }
    set상세_로딩(true)
    set정리_미리보기(null)
    set삭제확인(false)
    set뷰_모드('원본')
    set이력_열림(false)
    getNote(선택id)
      .then((n) => {
        set선택된_노트(n)
        set제목_입력(n.제목)
        set내용_입력(n.내용 ?? '')
        set태그_입력(n.태그 ?? '')
        set고정컨텍스트(Boolean(n.고정컨텍스트))
      })
      .finally(() => set상세_로딩(false))
    getNoteVersions(선택id).then(set버전목록)
  }, [선택id])

  const 미니그래프 = useMemo(() => {
    if (선택id === null) return null
    const 노드 = 온톨로지_노드_목록.find((n) => n.노트_id === 선택id)
    if (!노드) return null
    const 관계 = 온톨로지_관계_목록.filter((r) => r.출발_노드_id === 노드.id || r.도착_노드_id === 노드.id)
    if (관계.length === 0) return null

    const 노드맵 = new Map(온톨로지_노드_목록.map((n) => [n.id, n]))
    const 연결된_id = new Set([노드.id, ...관계.map((r) => r.출발_노드_id), ...관계.map((r) => r.도착_노드_id)])

    const 그래프_노드들: 그래프_노드[] = [...연결된_id].map((id) => {
      const n = 노드맵.get(id)
      const 원본이름 = n?.이름 ?? '?'
      const 표시 = n?.유형 === '사업' && 원본이름.includes(' · ') ? 원본이름.split(' · ').slice(1).join(' · ') : 원본이름
      return {
        id,
        label: 표시.length <= 14 ? 표시 : 표시.slice(0, 14) + '…',
        title: n ? `${n.유형}: ${n.이름}` : '',
        color: id === 노드.id ? '#1478d6' : '#8c8c8c',
        shape: n?.유형 === '사업' ? 'box' : 'dot',
        size: id === 노드.id ? 28 : 20,
        borderWidth: id === 노드.id ? 3 : 1,
      }
    })
    const 그래프_엣지들: 그래프_엣지[] = 관계.map((r) => ({
      id: r.id,
      from: r.출발_노드_id,
      to: r.도착_노드_id,
      label: r.관계유형,
      title: r.설명 || '',
      color: '#FC5356',
    }))
    return { 노드들: 그래프_노드들, 엣지들: 그래프_엣지들, 노드맵 }
  }, [선택id, 온톨로지_노드_목록, 온톨로지_관계_목록])

  const 태그_목록 = useMemo(() => {
    const 전체 = new Set<string>()
    for (const n of 목록) {
      for (const t of (n.태그 ?? '').split(',')) {
        const trimmed = t.trim()
        if (trimmed) 전체.add(trimmed)
      }
    }
    return [...전체].sort()
  }, [목록])

  const 필터된_목록 = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    if (!q) return 목록
    return 목록.filter(
      (n) => n.제목.toLowerCase().includes(q) || (n.태그 ?? '').toLowerCase().includes(q),
    )
  }, [목록, 검색어])

  function 위키링크_클릭(제목: string) {
    const 대상 = 목록.find((n) => n.제목 === 제목)
    if (대상) set선택id(대상.id)
  }

  const 마크다운_링크_컴포넌트 = {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => {
      if (href?.startsWith('#wikilink/')) {
        const 제목 = decodeURIComponent(href.slice('#wikilink/'.length))
        return (
          <a
            href="#"
            className="wikilink"
            onClick={(e) => {
              e.preventDefault()
              위키링크_클릭(제목)
            }}
          >
            {children}
          </a>
        )
      }
      if (href?.startsWith('#tagchip/')) {
        const 태그 = decodeURIComponent(href.slice('#tagchip/'.length))
        return (
          <a
            href="#"
            className="tag-chip-inline"
            onClick={(e) => {
              e.preventDefault()
              set검색어(태그)
            }}
          >
            {children}
          </a>
        )
      }
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      )
    },
  }

  async function 새_노트() {
    const { id } = await createNote('새 노트', '', '')
    await 목록_새로고침()
    set선택id(id)
  }

  async function 저장() {
    if (선택id === null) return
    setError(null)
    set저장중(true)
    try {
      await updateNote(선택id, { 제목: 제목_입력, 내용: 내용_입력, 태그: 태그_입력, 고정컨텍스트 })
      await 목록_새로고침()
      const 최신 = await getNote(선택id)
      set선택된_노트(최신)
      set버전목록(await getNoteVersions(선택id))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set저장중(false)
    }
  }

  async function 버전_복원_실행(버전_id: number) {
    if (선택id === null) return
    set복원중(버전_id)
    try {
      await restoreNoteVersion(선택id, 버전_id)
      const 최신 = await getNote(선택id)
      set선택된_노트(최신)
      set제목_입력(최신.제목)
      set내용_입력(최신.내용 ?? '')
      set태그_입력(최신.태그 ?? '')
      set버전목록(await getNoteVersions(선택id))
      await 목록_새로고침()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set복원중(null)
    }
  }

  async function 삭제_실행() {
    if (선택id === null) return
    await deleteNote(선택id)
    set선택id(null)
    set삭제확인(false)
    await 목록_새로고침()
  }

  async function AI로_정리() {
    if (선택id === null || !내용_입력.trim()) return
    setError(null)
    set정리중(true)
    try {
      const { 위키_내용 } = await organizeNote(선택id)
      set정리_미리보기(위키_내용)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set정리중(false)
    }
  }

  async function 정리본_적용() {
    if (선택id === null || 정리_미리보기 === null) return
    setError(null)
    set저장중(true)
    try {
      await updateNote(선택id, { 위키_내용: 정리_미리보기 })
      const 최신 = await getNote(선택id)
      set선택된_노트(최신)
      set정리_미리보기(null)
      set뷰_모드('위키')
      await 목록_새로고침()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set저장중(false)
    }
  }

  if (loading) return <p className="page-loading">불러오는 중...</p>

  return (
    <div className="notes-page-wrap">
      <div className="notes-page-header">
        <h2 className="page-title">위키</h2>
        <div className="segmented">
          <button
            className={`segmented-item ${보기_모드 === '노트' ? 'segmented-item-active' : ''}`}
            onClick={() => set보기_모드('노트')}
          >
            노트
          </button>
          <button
            className={`segmented-item ${보기_모드 === '그래프' ? 'segmented-item-active' : ''}`}
            onClick={() => set보기_모드('그래프')}
          >
            그래프
          </button>
        </div>
      </div>

      {보기_모드 === '그래프' ? (
        <div className="notes-graph-wrap">
          <OntologyView
            데이터_갱신_신호={데이터_갱신_신호}
            onOpenNote={(노트_id) => {
              set보기_모드('노트')
              set선택id(노트_id)
            }}
          />
        </div>
      ) : (
    <div className="notes-page">
      <div className="notes-sidebar">
        <button className="btn btn-primary btn-block sidebar-action-btn" onClick={새_노트}>
          <Icon name="plus" size={15} />
          새 노트
        </button>
        <div className="search-input-wrap">
          <Icon name="search" size={14} />
          <input
            className="text-input search-input"
            placeholder="제목·태그 검색"
            value={검색어}
            onChange={(e) => set검색어(e.target.value)}
          />
        </div>
        {태그_목록.length > 0 && (
          <div className="tag-chip-row">
            {태그_목록.map((t) => (
              <button
                key={t}
                className={`tag-chip ${검색어 === t ? 'tag-chip-active' : ''}`}
                onClick={() => set검색어((prev) => (prev === t ? '' : t))}
              >
                #{t}
              </button>
            ))}
          </div>
        )}
        <div className="conv-list">
          {필터된_목록.length === 0 && <p className="sidebar-caption">노트가 없습니다.</p>}
          {필터된_목록.map((n) => (
            <div key={n.id} className={`conv-row ${n.id === 선택id ? 'conv-row-active' : ''}`}>
              <button className="conv-row-title" onClick={() => set선택id(n.id)}>
                {n.제목 || '(제목 없음)'}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="notes-editor">
        {선택id === null ? (
          <p className="chat-empty-hint">왼쪽에서 노트를 선택하거나 새 노트를 만들어보세요.</p>
        ) : 상세_로딩 || !선택된_노트 ? (
          <p className="page-loading">불러오는 중...</p>
        ) : (
          <>
            <div className="notes-editor-header">
              <input
                className="text-input notes-title-input"
                value={제목_입력}
                onChange={(e) => set제목_입력(e.target.value)}
                placeholder="제목"
              />
              <button
                className="btn btn-secondary"
                onClick={() => set삭제확인(true)}
                title="노트 삭제"
              >
                <Icon name="trash" size={15} />
              </button>
            </div>

            <div className="notes-meta-row">
              {선택된_노트.최근수정자 && (
                <span className="sidebar-caption">최근 수정: {선택된_노트.최근수정자}</span>
              )}
              <label className="radio-label notes-pin-toggle">
                <input
                  type="checkbox"
                  checked={고정컨텍스트}
                  onChange={(e) => set고정컨텍스트(e.target.checked)}
                />
                이 노트를 AI에게 항상 알려주기(규칙·용어집 등)
              </label>
              {버전목록.length > 0 && (
                <button className="btn btn-secondary notes-history-toggle" onClick={() => set이력_열림((v) => !v)}>
                  <Icon name="clock" size={13} />
                  이력 {버전목록.length}건
                </button>
              )}
            </div>

            {이력_열림 && (
              <div className="notes-history-box">
                {버전목록.map((v) => (
                  <div key={v.id} className="notes-history-row">
                    <span className="sidebar-caption">
                      {v.저장일시} · {v.작성자}
                    </span>
                    <button
                      className="btn btn-secondary"
                      disabled={복원중 === v.id}
                      onClick={() => 버전_복원_실행(v.id)}
                    >
                      이 버전으로 복원
                    </button>
                  </div>
                ))}
              </div>
            )}

            {미니그래프 && (
              <div className="notes-mini-graph-box">
                <p className="sidebar-caption">
                  이 노트와 연결된 노드 {미니그래프.엣지들.length}건 — 다른 노트를 클릭하면 바로 이동합니다.
                </p>
                <OntologyGraph
                  nodes={미니그래프.노드들}
                  edges={미니그래프.엣지들}
                  height={180}
                  compact
                  onNodeClick={(id) => {
                    const n = 미니그래프.노드맵.get(id)
                    if (n?.노트_id != null && n.노트_id !== 선택id) set선택id(n.노트_id)
                  }}
                />
              </div>
            )}

            {삭제확인 && (
              <div className="delete-confirm">
                <p className="proposal-warning">이 노트를 삭제할까요? 되돌릴 수 없습니다.</p>
                <div className="proposal-actions">
                  <button className="btn btn-primary" onClick={삭제_실행}>
                    삭제
                  </button>
                  <button className="btn btn-secondary" onClick={() => set삭제확인(false)}>
                    취소
                  </button>
                </div>
              </div>
            )}

            <input
              className="text-input"
              value={태그_입력}
              onChange={(e) => set태그_입력(e.target.value)}
              placeholder="태그 (콤마로 구분)"
            />

            {선택된_노트.위키_내용 && (
              <div className="segmented">
                <button
                  className={`segmented-item ${뷰_모드 === '원본' ? 'segmented-item-active' : ''}`}
                  onClick={() => set뷰_모드('원본')}
                >
                  원본
                </button>
                <button
                  className={`segmented-item ${뷰_모드 === '위키' ? 'segmented-item-active' : ''}`}
                  onClick={() => set뷰_모드('위키')}
                >
                  위키
                </button>
              </div>
            )}

            {뷰_모드 === '원본' || !선택된_노트.위키_내용 ? (
              <textarea
                className="text-input notes-textarea"
                value={내용_입력}
                onChange={(e) => set내용_입력(e.target.value)}
                placeholder="노트 내용을 마크다운으로 작성하세요... [[다른 노트 제목]]을 쓰면 그래프에 자동으로 연결됩니다."
              />
            ) : (
              <div className="notes-wiki-view assistant-text">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={마크다운_링크_컴포넌트}>
                  {위키텍스트_전처리(선택된_노트.위키_내용)}
                </ReactMarkdown>
              </div>
            )}

            <div className="notes-toolbar">
              <button className="btn btn-primary" disabled={저장중} onClick={저장}>
                저장
              </button>
              <button className="btn btn-secondary" disabled={정리중 || !내용_입력.trim()} onClick={AI로_정리}>
                <Icon name="sparkles" size={14} />
                AI로 위키 정리
              </button>
              {음성지원 && (뷰_모드 === '원본' || !선택된_노트.위키_내용) && (
                <button
                  className={`btn btn-secondary ${듣는중 ? 'mic-btn-active' : ''}`}
                  onClick={음성_토글}
                  title={듣는중 ? '음성 입력 중지' : '음성으로 입력'}
                >
                  <Icon name="mic" size={14} />
                  {듣는중 ? '듣는 중...' : '음성으로 입력'}
                </button>
              )}
            </div>

            {정리중 && <p className="typing-indicator">AI가 노트를 정리하는 중...</p>}

            {정리_미리보기 !== null && (
              <div className="proposal-card notes-organize-preview">
                <p className="proposal-caption">AI가 정리한 위키 버전 (원본은 그대로 유지됩니다)</p>
                <div className="notes-wiki-view assistant-text">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={마크다운_링크_컴포넌트}>
                    {위키텍스트_전처리(정리_미리보기)}
                  </ReactMarkdown>
                </div>
                <div className="proposal-actions">
                  <button className="btn btn-primary" disabled={저장중} onClick={정리본_적용}>
                    적용
                  </button>
                  <button className="btn btn-secondary" onClick={() => set정리_미리보기(null)}>
                    취소
                  </button>
                </div>
              </div>
            )}

            {error && <p className="proposal-error">오류: {error}</p>}
          </>
        )}
      </div>
    </div>
      )}
    </div>
  )
}
