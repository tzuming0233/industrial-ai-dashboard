import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  applyProposal,
  cancelProposal,
  getMessages,
  streamMessage,
  type 대기중_제안,
  type 메시지,
} from '../api'
import ProposalCard from './ProposalCard'
import Icon from './Icon'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

type Props = {
  conversationId: number
  onActivity: () => void
}

const 허용_확장자 = '.csv,.xlsx,.xls,.pdf,.hwp'

export default function ChatMain({ conversationId, onActivity }: Props) {
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

  const fileInputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const { 지원됨: 음성지원, 듣는중, 토글: 음성_토글 } = useSpeechRecognition((text) => {
    setInputText((prev) => (prev ? `${prev} ${text}` : text))
  })

  useEffect(() => {
    setLoading(true)
    setError(null)
    setPendingProposal(null)
    setStreamingText('')
    setIsStreaming(false)
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

  function 전송(e: React.FormEvent) {
    e.preventDefault()
    if (isStreaming) return
    const 질문 = inputText.trim()
    const 파일 = attachedFile
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
    setError(null)
    setStreamingStatus(null)
    setStreamingText('')
    setIsStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    streamMessage(
      conversationId,
      질문,
      파일,
      {
        onToken: (text) => {
          setStreamingText((prev) => prev + text)
          setStreamingStatus(null)
        },
        onStatus: (message) => setStreamingStatus(message),
        onDone: (data) => {
          setIsStreaming(false)
          setStreamingText('')
          setStreamingStatus(null)
          if (data.text) {
            setMessages((prev) => [...prev, { role: 'assistant', content: data.text }])
          }
          if (data.제안 && data.action_token) {
            setPendingProposal({ 요약: data.제안, action_token: data.action_token })
          }
          onActivity()
        },
        onError: (message) => {
          setIsStreaming(false)
          setStreamingText('')
          setStreamingStatus(null)
          setError(message)
        },
      },
      controller.signal,
    ).catch(() => {
      /* onError 핸들러가 이미 상태를 처리함 */
    })
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
        {loading && <p className="sidebar-caption">불러오는 중...</p>}
        {!loading && messages.length === 0 && !isStreaming && (
          <p className="chat-empty-hint">
            예: '이번달 종료되는 사업은?' / '가나전자 사업을 완료 상태로 바꿔줘' — 엑셀·CSV·PDF·HWP
            파일을 첨부하면 무조건 데이터로 반영하지 않고, 검토·상의가 필요한지 반영이 필요한지
            먼저 판단합니다.
          </p>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="bubble-row bubble-row-user">
              <div className="bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <div key={i} className="assistant-text">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            </div>
          ),
        )}

        {isStreaming && (
          <div className="assistant-text">
            {streamingStatus && (
              <p className="typing-indicator typing-indicator-status">
                <span className="typing-dot" />
                {streamingStatus}
              </p>
            )}
            {streamingText ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
            ) : (
              !streamingStatus && <span className="typing-indicator">AI가 답변을 생성 중...</span>
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

        {error && <p className="proposal-error">오류: {error}</p>}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-row" onSubmit={전송}>
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
            className="btn btn-secondary attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming}
            title="파일 첨부"
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
            >
              <Icon name="mic" size={16} />
            </button>
          )}
          <input
            className="text-input chat-text-input"
            placeholder={듣는중 ? '듣고 있어요...' : '질문을 입력하거나 파일을 첨부하세요'}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isStreaming}
          />
          <button className="btn btn-primary send-btn" type="submit" disabled={isStreaming} title="전송">
            <Icon name="send" size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}
