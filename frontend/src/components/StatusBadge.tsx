import { 상태_배지_색상 } from '../theme'

export default function StatusBadge({ value }: { value: string }) {
  const [bg, fg] = 상태_배지_색상[value] ?? ['#F5F5F5', '#8C8C8C']
  return (
    <span className="status-badge" style={{ background: bg, color: fg }}>
      {value}
    </span>
  )
}
