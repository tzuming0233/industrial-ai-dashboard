import { Suspense, lazy, useEffect, useState } from 'react'
import './App.css'
import {
  createConversation,
  createProject,
  deleteConversation,
  listProjects,
  updateProject,
  getMe,
  listConversations,
  renameConversation,
  login,
  logout,
  getBusiness,
  signup,
  type 대화,
  type 사업행,
  type 프로젝트,
  type 프로젝트_상세,
} from './api'
import Sidebar from './components/Sidebar'
import ChatMain from './components/ChatMain'
import ProjectForm from './components/ProjectForm'
import ProjectPage from './components/ProjectPage'
import Icon from './components/Icon'
import TopNav, { type Tab, 탭_목록 } from './components/TopNav'

// 새로고침해도 보던 탭 그대로 있도록 로컬에 기억해둔다.
const _탭_저장키 = 'kpc-selected-tab'

function 저장된_탭_불러오기(): Tab {
  const 저장값 = localStorage.getItem(_탭_저장키)
  return (탭_목록 as string[]).includes(저장값 ?? '') ? (저장값 as Tab) : 'AI 채팅'
}

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
  const [탭, set탭] = useState<Tab>(저장된_탭_불러오기)
  // AI 채팅이 아닌 탭에서 오른쪽에 좁게 뜨는 채팅 패널을 접어둘 수 있게 — 접으면
  // main-pane이 flex:1이라 자동으로 그 폭만큼 넓어진다(레이아웃 변경 없이 폭만 조정).
  const [채팅_접힘, set채팅_접힘] = useState(false)

  useEffect(() => {
    localStorage.setItem(_탭_저장키, 탭)
  }, [탭])

  const [conversations, setConversations] = useState<대화[]>([])
  const [businesses, setBusinesses] = useState<사업행[]>([])
  const [currentId, setCurrentId] = useState<number | null>(null)
  const [projects, setProjects] = useState<프로젝트[]>([])
  // 값이 있으면 AI 채팅 탭의 본문에 채팅 대신 그 프로젝트 페이지를 보여준다.
  const [보는_프로젝트_id, set보는_프로젝트_id] = useState<number | null>(null)
  // 프로젝트 페이지 입력창에서 시작한 새 대화의 첫 질문 — ChatMain이 열리자마자 한 번 보낸다.
  const [초기_질문, set초기_질문] = useState<string | null>(null)
  const [프로젝트_폼, set프로젝트_폼] = useState<
    { 모드: '새로'; } | { 모드: '편집'; 상세: 프로젝트_상세 } | null
  >(null)
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
      const [convList, bizList, projectList] = await Promise.all([
        listConversations(),
        getBusiness(),
        listProjects(),
      ])
      setBusinesses(bizList)
      setProjects(projectList)
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
    // 대화가 생기거나 지워지면 프로젝트별 대화 수도 달라지므로 함께 갱신한다.
    const [convList, projectList] = await Promise.all([listConversations(), listProjects()])
    setConversations(convList)
    setProjects(projectList)
  }

  async function onNew() {
    const { id } = await createConversation()
    await refreshConversations()
    set보는_프로젝트_id(null)
    setCurrentId(id)
  }

  function onSelectConversation(id: number) {
    set보는_프로젝트_id(null)
    setCurrentId(id)
  }

  async function onStartProjectConversation(프로젝트_id: number, 첫_질문: string) {
    const { id } = await createConversation(프로젝트_id)
    set초기_질문(첫_질문)
    await refreshConversations()
    set보는_프로젝트_id(null)
    setCurrentId(id)
  }

  async function onSubmitProjectForm(값: { 이름: string; 설명: string; 사업_id: number | null }) {
    if (!프로젝트_폼) return
    if (프로젝트_폼.모드 === '새로') {
      const { id } = await createProject(값)
      await refreshConversations()
      set프로젝트_폼(null)
      set보는_프로젝트_id(id)
    } else {
      await updateProject(프로젝트_폼.상세.id, 값)
      await refreshConversations()
      set프로젝트_폼(null)
    }
  }

  async function onRename(id: number, 제목: string) {
    await renameConversation(id, 제목)
    await refreshConversations()
  }

  async function onDelete(id: number) {
    await deleteConversation(id)
    const list = await listConversations()
    setConversations(list)
    setProjects(await listProjects())
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
            onSelect={onSelectConversation}
            onNew={onNew}
            projects={projects}
            현재_프로젝트_id={보는_프로젝트_id}
            onOpenProject={set보는_프로젝트_id}
            onNewProject={() => set프로젝트_폼({ 모드: '새로' })}
            onDelete={onDelete}
            onRename={onRename}
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
            유지하고, AI 채팅 탭에서는 넓게·다른 탭에서는 좁은 사이드 패널로만 보여준다.
            그 좁은 패널은 접었다 펼 수 있고, 접으면 옆의 main-pane이 그만큼 넓어진다. */}
        <div
          className={`chat-panel ${
            AI채팅_탭 ? 'chat-panel-wide' : 채팅_접힘 ? 'chat-panel-collapsed' : 'chat-panel-narrow'
          }`}
        >
          {!AI채팅_탭 && (
            <button
              type="button"
              className="chat-panel-toggle"
              onClick={() => set채팅_접힘((v) => !v)}
              title={채팅_접힘 ? 'AI 채팅 펼치기' : 'AI 채팅 접기'}
              aria-label={채팅_접힘 ? 'AI 채팅 펼치기' : 'AI 채팅 접기'}
              aria-expanded={!채팅_접힘}
            >
              <Icon name="chevron" size={14} />
            </button>
          )}
          {AI채팅_탭 && 보는_프로젝트_id !== null && (
            <ProjectPage
              프로젝트_id={보는_프로젝트_id}
              conversations={conversations}
              onClose={() => set보는_프로젝트_id(null)}
              onOpenConversation={onSelectConversation}
              onStartConversation={onStartProjectConversation}
              onEdit={(상세) => set프로젝트_폼({ 모드: '편집', 상세 })}
              onChanged={refreshConversations}
              onDeleted={() => {
                set보는_프로젝트_id(null)
                refreshConversations()
              }}
            />
          )}
          <div
            className={`chat-panel-body ${
              (!AI채팅_탭 && 채팅_접힘) || (AI채팅_탭 && 보는_프로젝트_id !== null) ? 'chat-panel-body-hidden' : ''
            }`}
          >
            <ChatMain
              key={currentId}
              conversationId={currentId}
              사용자_이름={내_이름}
              초기_질문={초기_질문}
              onInitialConsumed={() => set초기_질문(null)}
              onOpenProject={(id) => {
                set탭('AI 채팅')
                set보는_프로젝트_id(id)
              }}
              onActivity={() => {
                refreshConversations()
                set데이터_갱신_신호((v) => v + 1)
              }}
            />
          </div>
        </div>
      </div>

      {프로젝트_폼 && (
        <ProjectForm
          제목={프로젝트_폼.모드 === '새로' ? '새 프로젝트' : '프로젝트 편집'}
          확인_라벨={프로젝트_폼.모드 === '새로' ? '만들기' : '저장'}
          초기값={
            프로젝트_폼.모드 === '새로'
              ? { 이름: '', 설명: '', 사업_id: null }
              : { 이름: 프로젝트_폼.상세.이름, 설명: 프로젝트_폼.상세.설명, 사업_id: 프로젝트_폼.상세.사업_id }
          }
          businesses={businesses}
          onSubmit={onSubmitProjectForm}
          onClose={() => set프로젝트_폼(null)}
        />
      )}
    </div>
  )
}

export default App
