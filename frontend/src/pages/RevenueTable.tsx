import { useEffect, useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import { exportCsv, exportXlsx, getBusiness, type 사업행 } from '../api'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import { 엠버코랄, 차트_공통레이아웃, 차트리즈 } from '../theme'

type 표시행 = 사업행 & { 미수금: number; 수금률: number }

function 원(v: number): string {
  return `${Math.round(v).toLocaleString()}원`
}

export default function RevenueTable() {
  const [rows, setRows] = useState<사업행[]>([])
  const [loading, setLoading] = useState(true)
  const [검색어, set검색어] = useState('')

  useEffect(() => {
    getBusiness()
      .then(setRows)
      .finally(() => setLoading(false))
  }, [])

  const 표시_행: 표시행[] = useMemo(() => {
    const q = 검색어.trim().toLowerCase()
    const 필터됨 = q
      ? rows.filter((r) => r.업체명?.toLowerCase().includes(q) || r.용역명?.toLowerCase().includes(q))
      : rows
    return 필터됨.map((r) => {
      const 계약금액 = r.계약금액 ?? 0
      const 기수입금액 = r.기수입금액 ?? 0
      return {
        ...r,
        미수금: 계약금액 - 기수입금액,
        수금률: 계약금액 ? Math.round((기수입금액 / 계약금액) * 1000) / 10 : 0,
      }
    })
  }, [rows, 검색어])

  const 총계약금액 = 표시_행.reduce((s, r) => s + (r.계약금액 ?? 0), 0)
  const 총기수입금액 = 표시_행.reduce((s, r) => s + (r.기수입금액 ?? 0), 0)
  const 총미수금 = 표시_행.reduce((s, r) => s + r.미수금, 0)
  const 총당해년도수입금액 = 표시_행.reduce((s, r) => s + (r.당해년도수입금액 ?? 0), 0)
  const 평균수금률 = 총계약금액 ? (총기수입금액 / 총계약금액) * 100 : 0

  const 사업구분별_재무 = useMemo(() => {
    const 맵 = new Map<string, { 기수입금액: number; 미수금: number }>()
    for (const r of 표시_행) {
      const key = r.사업구분 || '(미지정)'
      const cur = 맵.get(key) ?? { 기수입금액: 0, 미수금: 0 }
      cur.기수입금액 += r.기수입금액 ?? 0
      cur.미수금 += r.미수금
      맵.set(key, cur)
    }
    return [...맵.entries()]
      .map(([사업구분, v]) => ({ 사업구분, ...v }))
      .sort((a, b) => a.기수입금액 - b.기수입금액)
  }, [표시_행])

  if (loading) return <p className="page-loading">불러오는 중...</p>

  return (
    <div className="page">
      <input
        className="text-input"
        placeholder="업체명·용역명 검색 (예: 한국공대, 스마트공장)"
        value={검색어}
        onChange={(e) => set검색어(e.target.value)}
      />

      <div className="metric-row metric-row-5">
        <MetricCard label="총 계약금액" value={원(총계약금액)} />
        <MetricCard label="총 기수입금액" value={원(총기수입금액)} />
        <MetricCard label="총 미수금" value={원(총미수금)} />
        <MetricCard label="당해년도 수입금액" value={원(총당해년도수입금액)} />
        <MetricCard label="평균 수금률" value={`${평균수금률.toFixed(0)}%`} />
      </div>

      {총계약금액 > 0 && (
        <div className="chart-box chart-box-full">
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                name: '기수입금액',
                x: 사업구분별_재무.map((d) => d.기수입금액),
                y: 사업구분별_재무.map((d) => d.사업구분),
                marker: { color: 차트리즈 },
              },
              {
                type: 'bar',
                orientation: 'h',
                name: '미수금',
                x: 사업구분별_재무.map((d) => d.미수금),
                y: 사업구분별_재무.map((d) => d.사업구분),
                marker: { color: 엠버코랄 },
              },
            ]}
            layout={{
              ...차트_공통레이아웃(true),
              title: { text: '사업구분별 수금 현황 (기수입 vs 미수금)' },
              barmode: 'stack',
              height: Math.max(280, 사업구분별_재무.length * 34),
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      )}

      <div className="table-toolbar">
        <span className="sidebar-caption">총 {표시_행.length}건</span>
        <div className="table-toolbar-actions">
          <button
            className="btn btn-secondary"
            onClick={() => exportXlsx(표시_행, '사업현황_필터결과.xlsx')}
          >
            엑셀로 내보내기 (.xlsx)
          </button>
          <button className="btn btn-secondary" onClick={() => exportCsv(표시_행, '사업현황_필터결과.csv')}>
            CSV로 내보내기
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>구분</th>
              <th>업체명</th>
              <th>용역명</th>
              <th>사업구분</th>
              <th>담당자</th>
              <th>사업단계</th>
              <th>진행률</th>
              <th>시작일</th>
              <th>종료일</th>
              <th>계약금액</th>
              <th>기수입금액</th>
              <th>당해년도수입금액</th>
              <th>미수금</th>
              <th>수금률</th>
            </tr>
          </thead>
          <tbody>
            {표시_행.map((r) => (
              <tr key={r.id}>
                <td>{r.구분}</td>
                <td>{r.업체명}</td>
                <td>{r.용역명}</td>
                <td>{r.사업구분}</td>
                <td>{r.담당자}</td>
                <td>
                  <StatusBadge value={r.사업단계} />
                </td>
                <td>{r.진행률}%</td>
                <td>{r.시작일}</td>
                <td>{r.종료일}</td>
                <td>{(r.계약금액 ?? 0).toLocaleString()}</td>
                <td>{(r.기수입금액 ?? 0).toLocaleString()}</td>
                <td>{(r.당해년도수입금액 ?? 0).toLocaleString()}</td>
                <td>{r.미수금.toLocaleString()}</td>
                <td>{r.수금률.toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
