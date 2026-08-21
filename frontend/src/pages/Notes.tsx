import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createNote,
  deleteNote,
  getNote,
  getNotes,
  organizeNote,
  updateNote,
  type 노트,
  type 노트_요약,
} from '../api'
import Icon from '../components/Icon'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

export default function Notes() {
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

  useEffect(() => {
    if (선택id === null) {
      set선택된_노트(null)
      return
    }
    set상세_로딩(true)
    set정리_미리보기(null)
    set삭제확인(false)
    set뷰_모드('원본')
    getNote(선택id)
      .then((n) => {
        set선택된_노트(n)
        set제목_입력(n.제목)
        set내용_입력(n.내용 ?? '')
        set태그_입력(n.태그 ?? '')
      })
      .finally(() => set상세_로딩(false))
  }, [선택id])

  const 필터된_목록 = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    if (!q) return 목록
    return 목록.filter(
      (n) => n.제목.toLowerCase().includes(q) || (n.태그 ?? '').toLowerCase().includes(q),
    )
  }, [목록, 검색어])

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
      await updateNote(선택id, { 제목: 제목_입력, 내용: 내용_입력, 태그: 태그_입력 })
      await 목록_새로고침()
      const 최신 = await getNote(선택id)
      set선택된_노트(최신)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set저장중(false)
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
                placeholder="노트 내용을 마크다운으로 작성하세요..."
              />
            ) : (
              <div className="notes-wiki-view assistant-text">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{선택된_노트.위키_내용}</ReactMarkdown>
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
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{정리_미리보기}</ReactMarkdown>
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
  )
}
