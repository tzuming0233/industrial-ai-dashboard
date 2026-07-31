import { useEffect, useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import { getBusiness, getHistory, type 사업행, type 이력행 } from '../api'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import { 단조_색상맵, 상태_차트_색상, 엠버코랄, 차트_공통레이아웃, 본문색 } from '../theme'

const 하루_MS = 24 * 60 * 60 * 1000

type 그룹기준 = '사업구분' | '담당자'

export default function Milestone() {
  const [rows, setRows] = useState<사업행[]>([])
  const [history, setHistory] = useState<이력행[]>([])
  const [loading, setLoading] = useState(true)
  const [그룹, set그룹] = useState<그룹기준>('사업구분')

  useEffect(() => {
    Promise.all([getBusiness(), getHistory()])
      .then(([biz, hist]) => {
        setRows(biz)
        setHistory(hist)
      })
      .finally(() => setLoading(false))
  }, [])

  const 마일스톤_df = useMemo(() => {
    const 오늘 = new Date()
    return rows
      .filter((r) => r.시작일 && r.종료일)
      .map((r) => {
        const 시작 = new Date(r.시작일!).getTime()
        const 종료 = new Date(r.종료일!).getTime()
        const 기간 = Math.max(종료 - 시작, 하루_MS)
        const 진행률 = Math.min(Math.max(r.진행률 ?? 0, 0), 100)
        const 진행_종료 = 시작 + 기간 * (진행률 / 100)
        const dday = Math.round((종료 - 오늘.getTime()) / 하루_MS)
        const 그룹값 = (r[그룹] || '미지정') as string
        return {
          ...r,
          표시명: `${r.업체명} · ${r.용역명}`,
          시작_ms: 시작,
          종료_ms: 종료,
          진행_종료_ms: 진행_종료,
          진행률_숫자: 진행률,
          dday,
          그룹값,
        }
      })
      .sort((a, b) => a.종료_ms - b.종료_ms)
  }, [rows, 그룹])

  const kpi = useMemo(() => {
    const 전체 = 마일스톤_df.length
    const 지연 = 마일스톤_df.filter((r) => r.dday < 0 && r.진행률_숫자 < 100).length
    const 진행중 = 마일스톤_df.filter((r) => ['제안 진행', '계약 체결', '사업 수행'].includes(r.사업단계)).length
    const 평균진행률 = 전체 ? 마일스톤_df.reduce((s, r) => s + r.진행률_숫자, 0) / 전체 : 0
    return { 전체, 지연, 진행중, 평균진행률 }
  }, [마일스톤_df])

  const 전환_목록 = useMemo(() => {
    const 패턴 = /사업단계:\s*(.+?)\s*→\s*([^;]+)/g
    const 표시명_맵 = new Map(마일스톤_df.map((r) => [r.id, r.표시명]))
    const 결과: { 일시: string; 표시명: string; 새단계: string }[] = []
    for (const h of history) {
      if (h.유형 !== '수정' || !h.내용) continue
      const 표시명 = 표시명_맵.get(h.사업_id)
      if (!표시명) continue
      for (const m of h.내용.matchAll(패턴)) {
        결과.push({ 일시: h.작성일시, 표시명, 새단계: m[2].trim() })
      }
    }
    return 결과
  }, [history, 마일스톤_df])

  if (loading) return <p className="page-loading">불러오는 중...</p>

  if (마일스톤_df.length === 0) {
    return (
      <div className="page">
        <div className="alert alert-info">선택된 조건에 시작일/종료일이 모두 있는 건이 없습니다.</div>
      </div>
    )
  }

  const 그룹값_목록 = [...new Set(마일스톤_df.map((r) => r.그룹값))]
  const 색상맵 = 단조_색상맵(그룹값_목록)
  const y_순서 = 마일스톤_df.map((r) => r.표시명)
  const 오늘_iso = new Date().toISOString().slice(0, 10)

  const 배경_traces = 그룹값_목록.map((g) => {
    const 서브 = 마일스톤_df.filter((r) => r.그룹값 === g)
    return {
      type: 'bar' as const,
      orientation: 'h' as const,
      base: 서브.map((r) => new Date(r.시작_ms).toISOString().slice(0, 10)),
      x: 서브.map((r) => r.종료_ms - r.시작_ms),
      y: 서브.map((r) => r.표시명),
      name: g,
      marker: { color: 색상맵[g] },
      opacity: 0.32,
      hovertemplate: '%{y}<extra></extra>',
    }
  })

  const 진행_traces = 그룹값_목록.map((g) => {
    const 서브 = 마일스톤_df.filter((r) => r.그룹값 === g)
    return {
      type: 'bar' as const,
      orientation: 'h' as const,
      base: 서브.map((r) => new Date(r.시작_ms).toISOString().slice(0, 10)),
      x: 서브.map((r) => r.진행_종료_ms - r.시작_ms),
      y: 서브.map((r) => r.표시명),
      width: 0.4,
      marker: { color: 색상맵[g] },
      showlegend: false,
      hoverinfo: 'skip' as const,
    }
  })

  const 텍스트_trace = {
    type: 'scatter' as const,
    mode: 'text' as const,
    x: 마일스톤_df.map((r) => new Date(r.진행_종료_ms).toISOString().slice(0, 10)),
    y: 마일스톤_df.map((r) => r.표시명),
    text: 마일스톤_df.map((r) => `${r.진행률_숫자.toFixed(0)}%`),
    textposition: 'middle right' as const,
    textfont: { size: 11, color: 본문색 },
    showlegend: false,
    hoverinfo: 'skip' as const,
  }

  const 전환_trace = {
    type: 'scatter' as const,
    mode: 'markers' as const,
    x: 전환_목록.map((t) => t.일시),
    y: 전환_목록.map((t) => t.표시명),
    marker: {
      symbol: 'diamond',
      size: 11,
      line: { width: 1, color: 본문색 },
      color: 전환_목록.map((t) => 상태_차트_색상[t.새단계] ?? '#8C8C8C'),
    },
    text: 전환_목록.map((t) => t.새단계),
    hovertemplate: '%{y}<br>%{text} 전환: %{x|%Y-%m-%d}<extra></extra>',
    showlegend: false,
  }

  return (
    <div className="page">
      <h2 className="page-title">마일스톤 타임라인</h2>
      <p className="sidebar-caption">
        연한 막대는 전체 용역기간, 진한 막대는 진행률만큼 채워진 실제 진행 구간입니다. ◆ 마커는
        이력에 기록된 실제 단계 전환(사업단계 변경) 시점을 보여줍니다.
      </p>

      <div className="metric-row">
        <MetricCard label="전체 마일스톤" value={`${kpi.전체}건`} />
        <MetricCard label="마감 초과(미완료)" value={`${kpi.지연}건`} />
        <MetricCard label="진행중" value={`${kpi.진행중}건`} />
        <MetricCard label="평균 진행률" value={`${kpi.평균진행률.toFixed(0)}%`} />
      </div>

      <div className="radio-row">
        {(['사업구분', '담당자'] as 그룹기준[]).map((g) => (
          <label key={g} className="radio-label">
            <input type="radio" checked={그룹 === g} onChange={() => set그룹(g)} />
            {g}
          </label>
        ))}
      </div>

      <div className="chart-box chart-box-full">
        <Plot
          data={[...배경_traces, ...진행_traces, 텍스트_trace, 전환_trace]}
          layout={{
            ...차트_공통레이아웃(true),
            title: { text: `마일스톤 타임라인 · ${kpi.전체}건` },
            barmode: 'overlay',
            height: Math.max(320, 마일스톤_df.length * 30),
            xaxis: { ...차트_공통레이아웃().xaxis, type: 'date' },
            yaxis: {
              ...차트_공통레이아웃().yaxis,
              categoryorder: 'array',
              categoryarray: y_순서,
              autorange: 'reversed',
            },
            shapes: [
              {
                type: 'line',
                x0: 오늘_iso,
                x1: 오늘_iso,
                yref: 'paper',
                y0: 0,
                y1: 1,
                line: { color: 엠버코랄, dash: 'dash' },
              },
            ],
            annotations: [
              {
                x: 오늘_iso,
                yref: 'paper',
                y: 1,
                text: '오늘',
                showarrow: false,
                yanchor: 'bottom',
                font: { color: 엠버코랄, size: 11 },
              },
            ],
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%', height: '100%' }}
        />
      </div>

      <hr className="divider" />
      <p className="sidebar-caption">
        마일스톤 요약 (마감 임박·초과 순, 붉게 표시된 행은 완료되지 않은 채 기한을 넘긴 건입니다)
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>표시명</th>
              <th>담당자</th>
              <th>사업단계</th>
              <th>진행률</th>
              <th>종료일</th>
              <th>D-day</th>
            </tr>
          </thead>
          <tbody>
            {[...마일스톤_df]
              .sort((a, b) => a.dday - b.dday)
              .map((r) => {
                const 지연 = r.dday < 0 && r.진행률_숫자 < 100
                return (
                  <tr key={r.id} className={지연 ? 'row-delayed' : undefined}>
                    <td>{r.표시명}</td>
                    <td>{r.담당자}</td>
                    <td>
                      <StatusBadge value={r.사업단계} />
                    </td>
                    <td>{r.진행률_숫자.toFixed(0)}%</td>
                    <td>{r.종료일}</td>
                    <td>{r.dday}</td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
