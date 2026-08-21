import { Suspense, lazy, useEffect, useState } from 'react'
import './App.css'
import {
  createConversation,
  deleteConversation,
  getMe,
  listConversations,
  login,
  logout,
  getBusiness,
  signup,
  type 대화,
  type 사업행,
} from './api'
import Sidebar from './components/Sidebar'
import ChatMain from './components/ChatMain'
import TopNav, { type Tab } from './components/TopNav'

// plotly.js가 커서(gzip 1MB+) 기본 탭(AI 채팅)에서는 안 실리도록 차트 페이지만 지연 로드한다.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const RevenueTable = lazy(() => import('./pages/RevenueTable'))
const Milestone = lazy(() => import('./pages/Milestone'))
const Notes = lazy(() => import('./pages/Notes'))
const DataManagement = lazy(() => import('./pages/DataManagement'))

function App() {
  const [인증됨, set인증됨] = useState<boolean | null>(null)
  const [내_이름, set내_이름] = useState<string | null>(null)
  const [모드, set모드] = useState<'로그인' | '회원가입'>('로그인')
  const [이름_입력, set이름_입력] = useState('')
  const [비밀번호, set비밀번호] = useState('')
  const [로그인에러, set로그인에러] = useState('')
  const [탭, set탭] = useState<Tab>('AI 채팅')

  const [conversations, setConversations] = useState<대화[]>([])
  const [businesses, setBusinesses] = useState<사업행[]>([])
  const [currentId, setCurrentId] = useState<number | null>(null)
  const [초기화중, set초기화중] = useState(true)
  // 사이드 채팅에서 메시지 전송·제안 적용/취소가 끝날 때마다 증가 — 지금 보고 있는
  // 탭(예: 위키의 그래프 뷰)이 DB 변경을 놓치지 않고 다시 불러오게 하는 공용 신호.
  const [데이터_갱신_신호, set데이터_갱신_신호] = useState(0)

  async function 내_세션_불러오기() {
    try {
      const r = await getMe()
      set인증됨(r.인증됨)
      set내_이름(r.이름)
    } catch {
      set인증됨(false)
      set내_이름(null)
    }
  }

  useEffect(() => {
    내_세션_불러오기()
  }, [])

  useEffect(() => {
    if (!인증됨) return
    ;(async () => {
      const [convList, bizList] = await Promise.all([listConversations(), getBusiness()])
      setBusinesses(bizList)
      if (convList.length === 0) {
        const { id } = await createConversation()
        setConversations(await listConversations())
        setCurrentId(id)
      } else {
        setConversations(convList)
        setCurrentId(convList[0].id)
      }
      set초기화중(false)
    })()
  }, [인증됨])

  async function refreshConversations() {
    setConversations(await listConversations())
  }

  async function onNew() {
    const { id } = await createConversation()
    await refreshConversations()
    setCurrentId(id)
  }

  async function onNewWithProject(사업_id: number) {
    const { id } = await createConversation(사업_id)
    await refreshConversations()
    setCurrentId(id)
  }

  async function onDelete(id: number) {
    await deleteConversation(id)
    const list = await listConversations()
    setConversations(list)
    if (currentId === id) {
      if (list.length > 0) {
        setCurrentId(list[0].id)
      } else {
        const { id: 새id } = await createConversation()
        setConversations(await listConversations())
        setCurrentId(새id)
      }
    }
  }

  const 로그인또는가입 = async (e: React.FormEvent) => {
    e.preventDefault()
    set로그인에러('')
    try {
      await (모드 === '로그인' ? login : signup)(이름_입력.trim(), 비밀번호)
      await 내_세션_불러오기()
    } catch (err) {
      set로그인에러(err instanceof Error ? err.message : String(err))
    }
  }

  async function 로그아웃() {
    await logout()
    window.location.reload()
  }

  if (인증됨 === null) return <p style={{ padding: 24 }}>확인 중...</p>

  if (!인증됨) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h2>산업AI팀 사업 통합관리</h2>
          <div className="segmented" style={{ marginBottom: 12 }}>
            <button
              type="button"
              className={`segmented-item ${모드 === '로그인' ? 'segmented-item-active' : ''}`}
              onClick={() => { set모드('로그인'); set로그인에러('') }}
            >
              로그인
            </button>
            <button
              type="button"
              className={`segmented-item ${모드 === '회원가입' ? 'segmented-item-active' : ''}`}
              onClick={() => { set모드('회원가입'); set로그인에러('') }}
            >
              회원가입
            </button>
          </div>
          <form onSubmit={로그인또는가입}>
            <input
              type="text"
              className="text-input"
              value={이름_입력}
              onChange={(e) => set이름_입력(e.target.value)}
              placeholder="이름"
              autoComplete="username"
            />
            <input
              type="password"
              className="text-input"
              value={비밀번호}
              onChange={(e) => set비밀번호(e.target.value)}
              placeholder="비밀번호"
              autoComplete={모드 === '로그인' ? 'current-password' : 'new-password'}
            />
            <button type="submit" className="btn btn-primary btn-block">
              {모드}
            </button>
          </form>
          {로그인에러 && <p className="proposal-error">{로그인에러}</p>}
        </div>
      </div>
    )
  }

  if (초기화중 || currentId === null) {
    return <p style={{ padding: 24 }}>불러오는 중...</p>
  }

  const AI채팅_탭 = 탭 === 'AI 채팅'

  return (
    <div className="app-shell">
      <TopNav current={탭} onChange={set탭} 사용자_이름={내_이름} onLogout={로그아웃} />
      <div className="app-body">
        {AI채팅_탭 ? (
          <Sidebar
            conversations={conversations}
            currentId={currentId}
            businesses={businesses}
            onSelect={setCurrentId}
            onNew={onNew}
            onNewWithProject={onNewWithProject}
            onDelete={onDelete}
          />
        ) : (
          <div className={`main-pane ${탭 === '위키' ? '' : 'main-pane-scroll'}`}>
            <Suspense fallback={<p className="page-loading">불러오는 중...</p>}>
              {탭 === '대시보드' && <Dashboard />}
              {탭 === '매출현황 표' && <RevenueTable />}
              {탭 === '마일스톤' && <Milestone />}
              {탭 === '위키' && <Notes 데이터_갱신_신호={데이터_갱신_신호} />}
              {탭 === '데이터 관리' && <DataManagement 데이터_갱신_신호={데이터_갱신_신호} />}
            </Suspense>
          </div>
        )}

        {/* 탭을 옮겨도 스트리밍 중인 응답이 끊기지 않도록 ChatMain은 항상 마운트된 채로
            유지하고, AI 채팅 탭에서는 넓게·다른 탭에서는 좁은 사이드 패널로만 보여준다. */}
        <div className={`chat-panel ${AI채팅_탭 ? 'chat-panel-wide' : 'chat-panel-narrow'}`}>
          <ChatMain
            key={currentId}
            conversationId={currentId}
            onActivity={() => {
              refreshConversations()
              set데이터_갱신_신호((v) => v + 1)
            }}
          />
        </div>
      </div>
    </div>
  )
}

export default App
