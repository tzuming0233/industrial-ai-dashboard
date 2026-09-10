import { useEffect, useRef, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  applyProposal,
  cancelProposal,
  downloadGeneratedFile,
  fileDownloadUrl,
  getMessages,
  retryMessage,
  stopMessage,
  streamMessage,
  type 대기중_제안,
  type 메시지,
  type 명확화_질문,
  type 생성_파일,
} from '../api'
import ProposalCard from './ProposalCard'
import QuestionCard from './QuestionCard'
import Icon from './Icon'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

type Props = {
  conversationId: number
  onActivity: () => void
  사용자_이름: string | null
}

// 클로드 앱처럼 시간대별로 다른 인사말 + 이름.
function 인사말_생성(이름: string | null): string {
  const 시 = new Date().getHours()
  const 시간대 = 시 < 12 ? '좋은 아침이에요' : 시 < 18 ? '안녕하세요' : '늦은 시간까지 고생 많아요'
  return 이름 ? `${시간대}, ${이름}님` : 시간대
}

const 예시_프롬프트_목록 = [
  '이번달 종료되는 사업은?',
  '사업단계별로 몇 건씩이야?',
  '가나전자 사업을 완료 상태로 바꿔줘',
  '최근 계약된 사업 요약해줘',
]

const 허용_확장자 = '.csv,.xlsx,.xls,.pdf,.hwp,.png,.jpg,.jpeg,.gif,.webp'

// 새로고침해도 마지막에 고른 모델 그대로 유지되도록 로컬에 기억해둔다.
const _모델_저장키 = 'kpc-chat-model'
type 모델선택 = '기본' | '빠른'

function 저장된_모델_불러오기(): 모델선택 {
  return localStorage.getItem(_모델_저장키) === '빠른' ? '빠른' : '기본'
}

// 클로드 앱처럼 여러 줄 코드블록마다 복사 버튼을 붙인다 — 스트리밍 도중에도(코드
// 블록 자체가 완성됐다면) 바로 눌러 복사할 수 있다.
function 코드블록({ children }: { children?: ReactNode }) {
  const ref = useRef<HTMLPreElement>(null)
  const [복사됨, set복사됨] = useState(false)

  async function 복사() {
    const text = ref.current?.textContent ?? ''
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      set복사됨(true)
      setTimeout(() => set복사됨(false), 1500)
    } catch {
      // 클립보드 권한이 없는 환경 — 버튼은 그대로 두고 조용히 무시.
    }
  }

  return (
    <div className="code-block-wrap">
      <button type="button" className="code-copy-btn" onClick={복사}>
        <Icon name={복사됨 ? 'check' : 'copy'} size={12} />
        {복사됨 ? '복사됨' : '복사'}
      </button>
      <pre ref={ref}>{children}</pre>
    </div>
  )
}

const 마크다운_컴포넌트 = { pre: 코드블록 }

// 답변 전체를 클로드 앱처럼 한 번에 복사 — 스트리밍이 끝난 완성된 메시지에만 붙인다.
function 답변_복사_버튼({ text }: { text: string }) {
  const [복사됨, set복사됨] = useState(false)

  async function 복사() {
    try {
      await navigator.clipboard.writeText(text)
      set복사됨(true)
      setTimeout(() => set복사됨(false), 1500)
    } catch {
      // 클립보드 권한이 없는 환경 — 버튼은 그대로 두고 조용히 무시.
    }
  }

  return (
    <button type="button" className="assistant-action-btn" onClick={복사} title="답변 복사">
      <Icon name={복사됨 ? 'check' : 'copy'} size={13} />
      {복사됨 ? '복사됨' : '복사'}
    </button>
  )
}

export default function ChatMain({ conversationId, onActivity, 사용자_이름 }: Props) {
  const [loading, setLoading] = useState(true)
  const [messages, setMessages] = useState<메시지[]>([])
  const [연결된_사업_라벨, set연결된_사업_라벨] = useState<string | null>(null)
  const [pendingProposal, setPendingProposal] = useState<대기중_제안 | null>(null)
  const [proposalBusy, setProposalBusy] = useState(false)

  const [inputText, setInputText] = useState('')
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [최근_생성파일, set최근_생성파일] = useState<생성_파일 | null>(null)
  const [pendingQuestion, setPendingQuestion] = useState<명확화_질문 | null>(null)
  const [모델, set모델] = useState<모델선택>(저장된_모델_불러오기)

  useEffect(() => {
    localStorage.setItem(_모델_저장키, 모델)
  }, [모델])

  const fileInputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // 사용자가 '중단'을 눌러 일부러 스트림을 끊은 경우, streamMessage의 onError가
  // 이걸 진짜 네트워크 오류로 오인해 화면에 "오류: ..."를 띄우지 않도록 구분한다.
  const 중단_중_ref = useRef(false)

  // 클로드 앱처럼 여러 줄까지 자동으로 늘어나는 입력창(최대 높이는 CSS에서 캡).
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [inputText])

  const { 지원됨: 음성지원, 듣는중, 토글: 음성_토글 } = useSpeechRecognition((text) => {
    setInputText((prev) => (prev ? `${prev} ${text}` : text))
  })

  useEffect(() => {
    setLoading(true)
    setError(null)
    setPendingProposal(null)
    setPendingQuestion(null)
    setStreamingText('')
    setIsStreaming(false)
    set최근_생성파일(null)
    abortRef.current?.abort()

    getMessages(conversationId)
      .then((data) => {
        setMessages(data.메시지)
        set연결된_사업_라벨(data.사업_라벨)
        setPendingProposal(data.제안)
      })
      .finally(() => setLoading(false))

    return () => abortRef.current?.abort()
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, streamingText, pendingProposal])

  // 보내기()/재생성() 둘 다 이벤트 처리는 완전히 같다 — 스트림 소스(신규 전송 vs
  // 재생성)만 다르므로 핸들러 객체를 공유한다.
  function 스트림_핸들러_생성() {
    return {
      onToken: (text: string) => {
        setStreamingText((prev) => prev + text)
        setStreamingStatus(null)
      },
      onStatus: (message: string) => setStreamingStatus(message),
      onDone: (data: {
        text: string
        제안: 대기중_제안['요약'] | null
        action_token: string | null
        생성_파일: 생성_파일 | null
        질문_대기: 명확화_질문 | null
      }) => {
        setIsStreaming(false)
        setStreamingText('')
        setStreamingStatus(null)
        if (data.text) {
          setMessages((prev) => [...prev, { role: 'assistant', content: data.text }])
        }
        if (data.제안 && data.action_token) {
          setPendingProposal({ 요약: data.제안, action_token: data.action_token })
        }
        set최근_생성파일(data.생성_파일 ?? null)
        setPendingQuestion(data.질문_대기 ?? null)
        onActivity()
      },
      onError: (message: string) => {
        if (중단_중_ref.current) {
          // 사용자가 직접 중단한 것 — 이미 중단()에서 상태 정리를 끝냈으니
          // 이걸 오류로 표시하지 않는다.
          중단_중_ref.current = false
          return
        }
        setIsStreaming(false)
        setStreamingText('')
        setStreamingStatus(null)
        setError(message)
      },
    }
  }

  function 보내기(질문: string, 파일: File | null) {
    if (isStreaming) return
    if (!질문 && !파일) return

    let 표시_메시지 = 질문
    if (파일) 표시_메시지 = (표시_메시지 + `\n\n📎 ${파일.name}`).trim()
    if (표시_메시지) {
      setMessages((prev) => [...prev, { role: 'user', content: 표시_메시지 }])
    }

    setInputText('')
    setAttachedFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    setPendingProposal(null)
    setPendingQuestion(null)
    setError(null)
    setStreamingStatus(null)
    setStreamingText('')
    set최근_생성파일(null)
    setIsStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    streamMessage(conversationId, 질문, 파일, 스트림_핸들러_생성(), controller.signal, 모델).catch(() => {
      /* onError 핸들러가 이미 상태를 처리함 */
    })
  }

  function 전송(e: React.FormEvent) {
    e.preventDefault()
    보내기(inputText.trim(), attachedFile)
  }

  // 클로드 앱의 '재생성' 버튼 — 마지막 답변을 지우고 그 직전 질문으로 다시 받는다.
  // 새 사용자 메시지는 추가하지 않는다(서버가 이미 있던 질문을 재사용).
  function 재생성() {
    if (isStreaming) return
    setMessages((prev) => prev.slice(0, -1))
    setPendingProposal(null)
    setPendingQuestion(null)
    setError(null)
    setStreamingStatus(null)
    setStreamingText('')
    set최근_생성파일(null)
    setIsStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    retryMessage(conversationId, 스트림_핸들러_생성(), controller.signal, 모델).catch(() => {
      /* onError 핸들러가 이미 상태를 처리함 */
    })
  }

  // 클로드 앱의 생성 중단 버튼 — 지금까지 받은 부분 텍스트를 그대로 화면에 확정하고
  // 서버에도 저장시킨다(안 그러면 새로고침했을 때 방금 본 답변이 사라진다).
  function 중단() {
    중단_중_ref.current = true
    abortRef.current?.abort()
    const 부분_텍스트 = streamingText
    if (부분_텍스트) {
      setMessages((prev) => [...prev, { role: 'assistant', content: 부분_텍스트 }])
    }
    setIsStreaming(false)
    setStreamingText('')
    setStreamingStatus(null)
    stopMessage(conversationId, 부분_텍스트).catch(() => {
      /* 화면엔 이미 반영됐으니 저장 실패는 조용히 무시 */
    })
    onActivity()
  }

  function 선택지_클릭(label: string) {
    setPendingQuestion(null)
    보내기(label, null)
  }

  async function 제안_적용() {
    if (!pendingProposal) return
    setProposalBusy(true)
    try {
      const res = await applyProposal(conversationId, pendingProposal.action_token)
      if (!res.적용됨 && res.메시지) setError(res.메시지)
      setPendingProposal(null)
      const data = await getMessages(conversationId)
      setMessages(data.메시지)
      onActivity()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setProposalBusy(false)
    }
  }

  async function 제안_취소() {
    if (!pendingProposal) return
    setProposalBusy(true)
    try {
      await cancelProposal(conversationId, pendingProposal.action_token)
      setPendingProposal(null)
      const data = await getMessages(conversationId)
      setMessages(data.메시지)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setProposalBusy(false)
    }
  }

  return (
    <div className="chat-main">
      {연결된_사업_라벨 && (
        <p className="chat-project-caption">
          <Icon name="folder" size={13} />
          연결된 사업: {연결된_사업_라벨}
        </p>
      )}

      <div className="chat-messages">
       <div className="chat-column">
        {loading && <p className="sidebar-caption">불러오는 중...</p>}
        {!loading && messages.length === 0 && !isStreaming && (
          <div className="chat-hero">
            <h2 className="chat-hero-greeting">{인사말_생성(사용자_이름)}</h2>
            <p className="chat-hero-sub">무엇을 도와드릴까요?</p>
            <div className="chat-hero-prompts">
              {예시_프롬프트_목록.map((p) => (
                <button key={p} type="button" className="chat-hero-prompt-card" onClick={() => 보내기(p, null)}>
                  {p}
                </button>
              ))}
            </div>
            <p className="chat-hero-caption">
              엑셀·CSV·PDF·HWP·이미지 파일을 첨부하면 무조건 데이터로 반영하지 않고,
              검토·상의가 필요한지 반영이 필요한지 먼저 판단합니다.
            </p>
          </div>
        )}

        {messages.map((m, i) => {
          if (m.role === 'user') {
            return (
              <div key={i} className="bubble-row bubble-row-user">
                <div className="bubble">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
              </div>
            )
          }
          // 재생성은 마지막 답변에만, 그리고 직전 질문에 파일 첨부가 없었을 때만 —
          // 첨부 파일 원본은 저장돼있지 않아 재생성 시 다시 읽힐 수 없다.
          const 이전_사용자_메시지 = messages[i - 1]
          const 재생성_가능 =
            i === messages.length - 1 && !isStreaming && !이전_사용자_메시지?.content.includes('📎')
          return (
            <div key={i} className="assistant-text">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={마크다운_컴포넌트}>
                {m.content}
              </ReactMarkdown>
              <div className="assistant-actions">
                <답변_복사_버튼 text={m.content} />
                {재생성_가능 && (
                  <button type="button" className="assistant-action-btn" onClick={재생성} title="다시 생성">
                    <Icon name="refresh" size={13} />
                    다시 생성
                  </button>
                )}
              </div>
            </div>
          )
        })}

        {!isStreaming && 최근_생성파일 && (
          <>
            {['text/html', 'image/svg+xml'].includes(최근_생성파일.mime타입) ? (
              <div className="generated-file-actions">
                <a
                  className="generated-file-chip"
                  href={fileDownloadUrl(최근_생성파일.id)}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Icon name="sparkles" size={14} />
                  {최근_생성파일.파일명} 미리보기 (새 탭)
                </a>
                <button
                  type="button"
                  className="generated-file-chip generated-file-download-btn"
                  onClick={() => downloadGeneratedFile(최근_생성파일!.id, 최근_생성파일!.파일명)}
                  title="파일로 다운로드"
                >
                  <Icon name="download" size={14} />
                  다운로드
                </button>
              </div>
            ) : (
              <a
                className="generated-file-chip"
                href={fileDownloadUrl(최근_생성파일.id)}
                download={최근_생성파일.파일명}
              >
                <Icon name="download" size={14} />
                {최근_생성파일.파일명}
              </a>
            )}
          </>
        )}

        {isStreaming && (
          <div className="assistant-text">
            {streamingStatus && (
              <p className="typing-indicator typing-indicator-status">
                <span className="typing-dot" />
                <span className="status-shimmer">{streamingStatus}</span>
              </p>
            )}
            {streamingText ? (
              <>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={마크다운_컴포넌트}>
                  {streamingText}
                </ReactMarkdown>
                <span className="stream-cursor" />
              </>
            ) : (
              !streamingStatus && <span className="typing-indicator status-shimmer">AI가 답변을 생성 중...</span>
            )}
          </div>
        )}

        {pendingProposal && (
          <ProposalCard
            요약={pendingProposal.요약}
            처리중={proposalBusy}
            onApply={제안_적용}
            onCancel={제안_취소}
          />
        )}

        {!isStreaming && pendingQuestion && (
          <QuestionCard 질문={pendingQuestion} onSelect={선택지_클릭} />
        )}

        {error && <p className="proposal-error">오류: {error}</p>}
        <div ref={bottomRef} />
       </div>
      </div>

      <form className="chat-input-row" onSubmit={전송}>
       <div className="chat-column">
        {attachedFile && (
          <div className="attached-file-chip">
            <Icon name="paperclip" size={13} />
            {attachedFile.name}
            <button type="button" onClick={() => setAttachedFile(null)} aria-label="첨부 제거">
              <Icon name="x" size={12} />
            </button>
          </div>
        )}
        <div className="chat-input-controls">
          <input
            ref={fileInputRef}
            type="file"
            accept={허용_확장자}
            style={{ display: 'none' }}
            onChange={(e) => setAttachedFile(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className={`btn btn-secondary model-toggle-btn ${모델 === '빠른' ? 'model-toggle-fast' : ''}`}
            onClick={() => set모델((m) => (m === '기본' ? '빠른' : '기본'))}
            disabled={isStreaming}
            title={
              모델 === '빠른'
                ? '빠른 답변 모드 — 속도·비용은 아끼지만 복잡한 판단은 기본 모드보다 부정확할 수 있어요. 클릭하면 기본 모드로'
                : '기본 모드 — 클릭하면 단순 조회에 적합한 빠른 답변 모드로 전환'
            }
            aria-pressed={모델 === '빠른'}
          >
            <Icon name="zap" size={14} />
            {모델 === '빠른' ? '빠른 답변' : '기본'}
          </button>
          <button
            type="button"
            className="btn btn-secondary attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming}
            title="파일 첨부"
            aria-label="파일 첨부"
          >
            <Icon name="paperclip" size={16} />
          </button>
          {음성지원 && (
            <button
              type="button"
              className={`btn btn-secondary attach-btn ${듣는중 ? 'mic-btn-active' : ''}`}
              onClick={음성_토글}
              disabled={isStreaming}
              title={듣는중 ? '음성 입력 중지' : '음성으로 입력'}
              aria-label={듣는중 ? '음성 입력 중지' : '음성으로 입력'}
              aria-pressed={듣는중}
            >
              <Icon name="mic" size={16} />
            </button>
          )}
          <textarea
            ref={textareaRef}
            className="text-input chat-text-input"
            placeholder={듣는중 ? '듣고 있어요...' : '질문을 입력하거나 파일을 첨부하세요'}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                보내기(inputText.trim(), attachedFile)
              }
            }}
            disabled={isStreaming}
            rows={1}
          />
          <button
            className="btn btn-primary send-btn"
            type={isStreaming ? 'button' : 'submit'}
            onClick={isStreaming ? 중단 : undefined}
            title={isStreaming ? '생성 중단' : '전송'}
            aria-label={isStreaming ? '생성 중단' : '전송'}
          >
            <Icon name={isStreaming ? 'stop' : 'send'} size={16} />
          </button>
        </div>
       </div>
      </form>
    </div>
  )
}
