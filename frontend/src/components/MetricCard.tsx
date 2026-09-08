import Icon, { type IconName } from './Icon'

type Props = {
  label: string
  value: string
  help?: string
  icon?: IconName
  // 아직 값이 없어서 보여주는 안내 문구("목표 미설정" 등)일 때 — 실제 데이터와
  // 시각적으로 구분되도록 톤을 낮춘다.
  muted?: boolean
}

export default function MetricCard({ label, value, help, icon, muted }: Props) {
  return (
    <div className="metric-card" title={help}>
      {icon && (
        <div className="metric-icon">
          <Icon name={icon} size={16} />
        </div>
      )}
      <div>
        <p className="metric-label">{label}</p>
        <p className={`metric-value ${muted ? 'metric-value-muted' : ''}`}>{value}</p>
      </div>
    </div>
  )
}
