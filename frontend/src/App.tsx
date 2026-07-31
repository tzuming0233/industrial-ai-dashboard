import { useEffect, useState } from 'react'
import './App.css'
import {
  api,
  createConversation,
  deleteConversation,
  listConversations,
  getBusiness,
  type 대화,
  type 사업행,
} from './api'
import Sidebar from './components/Sidebar'
import ChatMain from './components/ChatMain'

function App() {
  const [인증됨, set인증됨] = useState<boolean | null>(null)
  const [비밀번호, set비밀번호] = useState('')
  const [로그인에러, set로그인에러] = useState('')

  const [conversations, setConversations] = useState<대화[]>([])
  const [businesses, setBusinesses] = useState<사업행[]>([])
  const [currentId, setCurrentId] = useState<number | null>(null)
  const [초기화중, set초기화중] = useState(true)

  useEffect(() => {
    api<{ 인증됨: boolean }>('/api/me')
      .then((r) => set인증됨(r.인증됨))
      .catch(() => set인증됨(false))
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

  const 로그인 = async (e: React.FormEvent) => {
    e.preventDefault()
    set로그인에러('')
    try {
      await api('/api/login', { method: 'POST', body: JSON.stringify({ password: 비밀번호 }) })
      set인증됨(true)
    } catch {
      set로그인에러('비밀번호가 올바르지 않습니다.')
    }
  }

  if (인증됨 === null) return <p style={{ padding: 24 }}>확인 중...</p>

  if (!인증됨) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h2>산업AI팀 사업 통합관리</h2>
          <form onSubmit={로그인}>
            <input
              type="password"
              className="text-input"
              value={비밀번호}
              onChange={(e) => set비밀번호(e.target.value)}
              placeholder="비밀번호"
            />
            <button type="submit" className="btn btn-primary btn-block">
              로그인
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

  return (
    <div className="app-layout">
      <Sidebar
        conversations={conversations}
        currentId={currentId}
        businesses={businesses}
        onSelect={setCurrentId}
        onNew={onNew}
        onNewWithProject={onNewWithProject}
        onDelete={onDelete}
      />
      <ChatMain key={currentId} conversationId={currentId} onActivity={refreshConversations} />
    </div>
  )
}

export default App
