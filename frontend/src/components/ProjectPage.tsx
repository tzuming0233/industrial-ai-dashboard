import { useEffect, useRef, useState } from 'react'
import {
  deleteProject,
  deleteProjectKnowledge,
  getProject,
  updateProject,
  uploadProjectKnowledge,
  type 대화,
  type 프로젝트_상세,
} from '../api'
import Icon from './Icon'

type Props = {
  프로젝트_id: number
  // 대화 목록이 바뀔 때(새 대화·제목 생성·삭제) 이 페이지의 대화 목록도 다시 불러온다.
  conversations: 대화[]
  onClose: () => void
  onOpenConversation: (id: number) => void
  onStartConversation: (프로젝트_id: number, 첫_질문: string) => void
  onEdit: (상세: 프로젝트_상세) => void
  onChanged: () => void
  onDeleted: () => void
}

const 지식_허용_확장자 = '.txt,.md,.csv,.xlsx,.xls,.pdf,.hwp,.docx'

function 상대_날짜(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const 일차 = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (일차 <= 0) return '오늘'
  if (일차 === 1) return '어제'
  if (일차 < 7) return `${일차}일 전`
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

// 클로드 앱의 프로젝트 페이지 — 제목/설명, 이 프로젝트에서 바로 새 대화를 시작하는 입력창,
// 프로젝트 대화 목록, 그리고 오른쪽에 지침·지식 파일 패널.
export default function ProjectPage({
  프로젝트_id,
  conversations,
  onClose,
  onOpenConversation,
  onStartConversation,
  onEdit,
  onChanged,
  onDeleted,
}: Props) {
  const [상세, set상세] = useState<프로젝트_상세 | null>(null)
  const [불러오기_오류, set불러오기_오류] = useState<string | null>(null)
  const [입력, set입력] = useState('')
  const [지침_편집중, set지침_편집중] = useState(false)
  const [지침_값, set지침_값] = useState('')
  const [지침_저장중, set지침_저장중] = useState(false)
  const [업로드중, set업로드중] = useState(false)
  const [지식_오류, set지식_오류] = useState<string | null>(null)
  const [삭제_확인, set삭제_확인] = useState(false)
  const 파일_ref = useRef<HTMLInputElement>(null)

  async function 새로_불러오기() {
    try {
      set상세(await getProject(프로젝트_id))
      set불러오기_오류(null)
    } catch (e) {
      set불러오기_오류(e instanceof Error ? e.message : String(e))
    }
  }

  // 다른 프로젝트로 넘어가면 화면 상태를 비우고, 대화 목록이 바뀔 때는 화면을 깜빡이지
  // 않고 데이터만 조용히 다시 불러온다.
  useEffect(() => {
    set상세(null)
    set지침_편집중(false)
    set삭제_확인(false)
    set지식_오류(null)
  }, [프로젝트_id])

  useEffect(() => {
    새로_불러오기()
  }, [프로젝트_id, conversations])

  function 시작() {
    const 질문 = 입력.trim()
    if (!질문) return
    onStartConversation(프로젝트_id, 질문)
  }

  async function 지침_저장() {
    set지침_저장중(true)
    try {
      await updateProject(프로젝트_id, { 지침: 지침_값 })
      set지침_편집중(false)
      await 새로_불러오기()
      onChanged()
    } catch (e) {
      set지식_오류(e instanceof Error ? e.message : String(e))
    } finally {
      set지침_저장중(false)
    }
  }

  async function 파일_추가(files: FileList | null) {
    if (!files?.length) return
    set업로드중(true)
    set지식_오류(null)
    // 여러 개를 골라도 하나씩 차례로 — 용량 초과 같은 오류가 어느 파일 때문인지 알 수 있게.
    for (const f of Array.from(files)) {
      try {
        await uploadProjectKnowledge(프로젝트_id, f)
      } catch (e) {
        set지식_오류(`${f.name}: ${e instanceof Error ? e.message : String(e)}`)
        break
      }
    }
    if (파일_ref.current) 파일_ref.current.value = ''
    set업로드중(false)
    await 새로_불러오기()
    onChanged()
  }

  async function 파일_삭제(지식_id: number) {
    try {
      await deleteProjectKnowledge(프로젝트_id, 지식_id)
      await 새로_불러오기()
      onChanged()
    } catch (e) {
      set지식_오류(e instanceof Error ? e.message : String(e))
    }
  }

  async function 프로젝트_삭제() {
    try {
      await deleteProject(프로젝트_id)
      onDeleted()
    } catch (e) {
      set불러오기_오류(e instanceof Error ? e.message : String(e))
    }
  }

  if (불러오기_오류 && !상세) {
    return (
      <div className="project-page">
        <button type="button" className="project-back-btn" onClick={onClose}>
          <Icon name="arrow-left" size={14} />
          대화로 돌아가기
        </button>
        <p className="proposal-error">{불러오기_오류}</p>
      </div>
    )
  }
  if (!상세) return <div className="project-page"><p className="sidebar-caption">불러오는 중...</p></div>

  const 사용률 = Math.min(100, Math.round((상세.지식_글자수 / 상세.지식_한도) * 100))

  return (
    <div className="project-page">
      <div className="project-page-inner">
        <button type="button" className="project-back-btn" onClick={onClose}>
          <Icon name="arrow-left" size={14} />
          대화로 돌아가기
        </button>

        <div className="project-header">
          <div className="project-header-text">
            <h2 className="project-title">
              <Icon name="folder" size={20} />
              {상세.이름}
            </h2>
            {상세.설명 && <p className="project-desc">{상세.설명}</p>}
            {상세.사업_라벨 && (
              <p className="project-linked-business">
                <Icon name="chart" size={12} />
                연결된 사업: {상세.사업_라벨}
              </p>
            )}
          </div>
          <div className="project-header-actions">
            <button type="button" className="btn btn-secondary" onClick={() => onEdit(상세)}>
              <Icon name="edit" size={14} />
              편집
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => set삭제_확인(true)}>
              <Icon name="trash" size={14} />
              삭제
            </button>
          </div>
        </div>

        {삭제_확인 && (
          <div className="delete-confirm project-delete-confirm">
            <p className="proposal-warning">
              '{상세.이름}' 프로젝트와 지식 파일을 삭제할까요? 속한 대화는 지워지지 않고 일반 대화로 남습니다.
            </p>
            <div className="proposal-actions">
              <button className="btn btn-primary" onClick={프로젝트_삭제}>
                삭제
              </button>
              <button className="btn btn-secondary" onClick={() => set삭제_확인(false)}>
                취소
              </button>
            </div>
          </div>
        )}

        <div className="project-columns">
          <div className="project-main">
            <div className="project-composer">
              <textarea
                className="project-composer-input"
                rows={2}
                value={입력}
                placeholder="이 프로젝트에서 새 대화를 시작하세요"
                onChange={(e) => set입력(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault()
                    시작()
                  }
                }}
              />
              <button
                type="button"
                className="btn btn-primary send-btn"
                onClick={시작}
                disabled={!입력.trim()}
                title="새 대화 시작"
                aria-label="새 대화 시작"
              >
                <Icon name="send" size={16} />
              </button>
            </div>

            <h3 className="project-section-title">대화 {상세.대화.length > 0 && `(${상세.대화.length})`}</h3>
            {상세.대화.length === 0 ? (
              <p className="sidebar-caption">
                아직 대화가 없어요. 위 입력창에 질문을 쓰면 이 프로젝트의 지침과 지식이 적용된 대화가 시작돼요.
              </p>
            ) : (
              <div className="project-conv-list">
                {상세.대화.map((c) => (
                  <button key={c.id} type="button" className="project-conv-row" onClick={() => onOpenConversation(c.id)}>
                    <span className="project-conv-title">{c.제목 || '새 대화'}</span>
                    <span className="project-conv-date">{상대_날짜(c.마지막_활동일시)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="project-side">
            <section className="project-panel">
              <div className="project-panel-head">
                <h3 className="project-section-title">지침</h3>
                {!지침_편집중 && (
                  <button
                    type="button"
                    className="project-panel-btn"
                    onClick={() => {
                      set지침_값(상세.지침)
                      set지침_편집중(true)
                    }}
                    aria-label="지침 편집"
                    title="지침 편집"
                  >
                    <Icon name={상세.지침 ? 'edit' : 'plus'} size={14} />
                  </button>
                )}
              </div>
              {지침_편집중 ? (
                <>
                  <textarea
                    className="text-input project-instruction-input"
                    rows={8}
                    value={지침_값}
                    maxLength={8000}
                    autoFocus
                    placeholder="예: 항상 존댓말로, 금액은 억 단위로 요약하고 표로 정리해줘."
                    onChange={(e) => set지침_값(e.target.value)}
                  />
                  <div className="project-panel-actions">
                    <button type="button" className="btn btn-primary" onClick={지침_저장} disabled={지침_저장중}>
                      저장
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => set지침_편집중(false)}>
                      취소
                    </button>
                  </div>
                </>
              ) : 상세.지침 ? (
                <p className="project-instruction-text">{상세.지침}</p>
              ) : (
                <p className="sidebar-caption">
                  이 프로젝트의 모든 대화에 적용할 지침(말투, 형식, 역할)을 정해두세요.
                </p>
              )}
            </section>

            <section className="project-panel">
              <div className="project-panel-head">
                <h3 className="project-section-title">지식</h3>
                <button
                  type="button"
                  className="project-panel-btn"
                  onClick={() => 파일_ref.current?.click()}
                  disabled={업로드중}
                  aria-label="지식 파일 추가"
                  title="지식 파일 추가"
                >
                  <Icon name="plus" size={14} />
                </button>
                <input
                  ref={파일_ref}
                  type="file"
                  multiple
                  accept={지식_허용_확장자}
                  style={{ display: 'none' }}
                  onChange={(e) => 파일_추가(e.target.files)}
                />
              </div>

              {상세.지식.length === 0 ? (
                <p className="sidebar-caption">
                  규정·제안서·회의록 같은 자료를 올리면 이 프로젝트의 모든 대화에서 AI가 근거로 참고해요.
                  ({지식_허용_확장자.replaceAll(',', ' ')})
                </p>
              ) : (
                <ul className="project-knowledge-list">
                  {상세.지식.map((k) => (
                    <li key={k.id} className="project-knowledge-row">
                      <Icon name="file" size={14} />
                      <span className="project-knowledge-name" title={k.파일명}>
                        {k.파일명}
                      </span>
                      <span className="project-knowledge-size">{k.글자수.toLocaleString()}자</span>
                      <button
                        type="button"
                        className="project-panel-btn"
                        onClick={() => 파일_삭제(k.id)}
                        aria-label={`${k.파일명} 삭제`}
                        title="삭제"
                      >
                        <Icon name="x" size={13} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {업로드중 && <p className="sidebar-caption">파일을 읽는 중...</p>}
              {지식_오류 && <p className="proposal-error">{지식_오류}</p>}

              {상세.지식.length > 0 && (
                <div className="project-capacity" title={`${상세.지식_글자수.toLocaleString()} / ${상세.지식_한도.toLocaleString()}자`}>
                  <div className="project-capacity-bar">
                    <div
                      className={`project-capacity-fill ${사용률 >= 90 ? 'project-capacity-fill-full' : ''}`}
                      style={{ width: `${사용률}%` }}
                    />
                  </div>
                  <span>용량 {사용률}% 사용</span>
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
