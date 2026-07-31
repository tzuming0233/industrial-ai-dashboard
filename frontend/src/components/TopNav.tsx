type Tab = 'AI 채팅' | '대시보드' | '매출현황 표' | '마일스톤'

const 탭_아이콘: Record<Tab, string> = {
  'AI 채팅': '🤖',
  대시보드: '📊',
  '매출현황 표': '📋',
  마일스톤: '🗓️',
}

const 탭_목록: Tab[] = ['AI 채팅', '대시보드', '매출현황 표', '마일스톤']

type Props = {
  current: Tab
  onChange: (tab: Tab) => void
}

export default function TopNav({ current, onChange }: Props) {
  return (
    <div className="top-nav">
      <span className="top-nav-title">산업AI팀 사업 통합관리</span>
      <div className="top-nav-tabs">
        {탭_목록.map((tab) => (
          <button
            key={tab}
            className={`top-nav-tab ${tab === current ? 'top-nav-tab-active' : ''}`}
            onClick={() => onChange(tab)}
          >
            {탭_아이콘[tab]} {tab}
          </button>
        ))}
      </div>
    </div>
  )
}

export type { Tab }
