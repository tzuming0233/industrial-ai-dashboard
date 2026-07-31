import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { getDashboardSummary, type 대시보드요약 } from '../api'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import { 단조_색상맵, 상태_차트_색상, 전기블루, 차트_공통레이아웃, 사업단계_옵션 } from '../theme'

export default function Dashboard() {
  const [data, setData] = useState<대시보드요약 | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="page-loading">불러오는 중...</p>
  if (!data) return <p className="page-loading">데이터를 불러오지 못했습니다.</p>

  const 구분_목록 = [...new Set(data.구분별_건수.map((d) => String(d.구분)))]
  const 구분_색상맵 = 단조_색상맵(구분_목록)

  return (
    <div className="page">
      {data.마감임박.length === 0 ? (
        <div className="alert alert-success">30일 이내 마감 임박 사업이 없습니다.</div>
      ) : (
        <>
          <div className="alert alert-warning">
            마감 임박 {data.마감임박.length}건 (진행률 100% 미달 사업 중 종료일 30일 이내 또는 기한 초과)
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>업체명</th>
                  <th>용역명</th>
                  <th>종료일</th>
                  <th>D-day</th>
                  <th>사업단계</th>
                </tr>
              </thead>
              <tbody>
                {data.마감임박.map((row, i) => (
                  <tr key={i}>
                    <td>{row.업체명}</td>
                    <td>{row.용역명}</td>
                    <td>{row.종료일}</td>
                    <td>{row['D-day']}</td>
                    <td>
                      <StatusBadge value={row.사업단계} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="metric-row">
        <MetricCard label="전체 건수" value={String(data.전체_건수)} />
        <MetricCard label="사업구분 수" value={String(data.사업구분_수)} />
        <MetricCard label="구분(신규/이월) 수" value={String(data.구분_수)} />
        <MetricCard label="평균 진행률" value={`${data.평균_진행률.toFixed(0)}%`} />
      </div>

      <div className="metric-row">
        <MetricCard
          label={`${data.올해_목표.연도}년 매출 달성률`}
          value={data.올해_목표.매출_달성률 !== null ? `${data.올해_목표.매출_달성률.toFixed(1)}%` : '목표 미설정'}
          help={
            data.올해_목표.목표매출
              ? `실적 ${data.올해_목표.실적_매출.toLocaleString()}원 / 목표 ${data.올해_목표.목표매출.toLocaleString()}원`
              : undefined
          }
        />
        <MetricCard label={`${data.올해_목표.연도}년 손익 달성률`} value="데이터 없음" help="원가/비용 데이터가 아직 없어 계산할 수 없습니다." />
      </div>

      <div className="chart-row">
        <div className="chart-box">
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                x: data.사업구분별_건수.map((d) => d.건수).reverse(),
                y: data.사업구분별_건수.map((d) => String(d.사업구분)).reverse(),
                text: data.사업구분별_건수.map((d) => String(d.건수)).reverse(),
                textposition: 'outside',
                marker: { color: 전기블루 },
              },
            ]}
            layout={{ ...차트_공통레이아웃(), title: { text: '사업구분별 건수' }, height: 300 }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
        <div className="chart-box">
          <Plot
            data={data.구분별_건수.map((d) => ({
              type: 'bar',
              x: [String(d.구분)],
              y: [d.건수],
              text: [String(d.건수)],
              textposition: 'outside',
              marker: { color: 구분_색상맵[String(d.구분)] },
              name: String(d.구분),
              showlegend: false,
            }))}
            layout={{ ...차트_공통레이아웃(false), title: { text: '구분(신규/이월)별 건수' }, height: 300 }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
        <div className="chart-box">
          <Plot
            data={사업단계_옵션.map((단계) => {
              const 항목 = data.사업단계별_건수.find((d) => d.사업단계 === 단계)
              return {
                type: 'bar' as const,
                x: [단계],
                y: [항목?.건수 ?? 0],
                text: [String(항목?.건수 ?? 0)],
                textposition: 'outside' as const,
                marker: { color: 상태_차트_색상[단계] },
                name: 단계,
                showlegend: false,
              }
            })}
            layout={{
              ...차트_공통레이아웃(false),
              title: { text: '사업단계별 건수' },
              height: 300,
              xaxis: { ...차트_공통레이아웃(false).xaxis, tickangle: -20 },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>

      {data.담당자별_건수.length > 0 && (
        <div className="chart-box chart-box-full">
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                x: [...data.담당자별_건수].reverse().map((d) => d.건수),
                y: [...data.담당자별_건수].reverse().map((d) => String(d.담당자)),
                text: [...data.담당자별_건수].reverse().map((d) => String(d.건수)),
                textposition: 'outside',
                marker: { color: 전기블루 },
              },
            ]}
            layout={{
              ...차트_공통레이아웃(),
              title: { text: '담당자(PM)별 투입 건수' },
              height: Math.max(300, data.담당자별_건수.length * 32),
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      )}
    </div>
  )
}
