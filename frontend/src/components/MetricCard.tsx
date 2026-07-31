type Props = {
  label: string
  value: string
  help?: string
}

export default function MetricCard({ label, value, help }: Props) {
  return (
    <div className="metric-card" title={help}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
    </div>
  )
}
