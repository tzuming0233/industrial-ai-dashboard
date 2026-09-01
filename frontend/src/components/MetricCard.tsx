import Icon, { type IconName } from './Icon'

type Props = {
  label: string
  value: string
  help?: string
  icon?: IconName
}

export default function MetricCard({ label, value, help, icon }: Props) {
  return (
    <div className="metric-card" title={help}>
      {icon && (
        <div className="metric-icon">
          <Icon name={icon} size={16} />
        </div>
      )}
      <div>
        <p className="metric-label">{label}</p>
        <p className="metric-value">{value}</p>
      </div>
    </div>
  )
}
