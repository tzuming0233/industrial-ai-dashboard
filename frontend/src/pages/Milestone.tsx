import { useMemo, useState, useEffect } from 'react'
import { getBusiness, getHistory, type 사업행, type 이력행 } from '../api'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import { 상태_차트_색상, 카테고리_팔레트 } from '../theme'

const 하루_MS = 24 * 60 * 60 * 1000

type 그룹기준 = '사업구분' | '담당자'

function 월_레이블(ms: number): string {
  const d = new Date(ms)
  return `${d.getFullYear()}. ${d.getMonth() + 1}`
}

export default function Milestone() {
  const [rows, setRows] = useState<사업행[]>([])
  const [history, setHistory] = useState<이력행[]>([])
  const [loading, setLoading] = useState(true)
  const [그룹, set그룹] = useState<그룹기준>('사업구분')
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    Promise.all([getBusiness(), getHistory()])
      .then(([biz, hist]) => {
        setRows(biz)
        setHistory(hist)
      })
      .finally(() => setLoading(false))
  }, [])

  const 마일스톤_목록 = useMemo(() => {
    const 오늘 = Date.now()
    return rows
      .filter((r) => r.시작일 && r.종료일)
      .map((r) => {
        const 시작 = new Date(r.시작일!).getTime()
        const 종료 = new Date(r.종료일!).getTime()
        const 기간 = Math.max(종료 - 시작, 하루_MS)
        const 진행률 = Math.min(Math.max(r.진행률 ?? 0, 0), 100)
        const dday = Math.round((종료 - 오늘) / 하루_MS)
        return {
          ...r,
          표시명: `${r.업체명} · ${r.용역명}`,
          시작_ms: 시작,
          종료_ms: 종료,
          기간_ms: 기간,
          진행률_숫자: 진행률,
          dday,
          그룹값: (r[그룹] || '미지정') as string,
        }
      })
      .sort((a, b) => a.종료_ms - b.종료_ms)
  }, [rows, 그룹])

  const kpi = useMemo(() => {
    const 전체 = 마일스톤_목록.length
    const 지연 = 마일스톤_목록.filter((r) => r.dday < 0 && r.진행률_숫자 < 100).length
    const 진행중 = 마일스톤_목록.filter((r) => ['제안 진행', '계약 체결', '사업 수행'].includes(r.사업단계)).length
    const 평균진행률 = 전체 ? 마일스톤_목록.reduce((s, r) => s + r.진행률_숫자, 0) / 전체 : 0
    return { 전체, 지연, 진행중, 평균진행률 }
  }, [마일스톤_목록])

  const 그룹값_목록 = useMemo(() => [...new Set(마일스톤_목록.map((r) => r.그룹값))].sort(), [마일스톤_목록])
  const 색상맵 = useMemo(() => {
    const 맵: Record<string, string> = {}
    그룹값_목록.forEach((g, i) => (맵[g] = 카테고리_팔레트[i % 카테고리_팔레트.length]))
    return 맵
  }, [그룹값_목록])

  const 전환_목록 = useMemo(() => {
    const 패턴 = /사업단계:\s*(.+?)\s*→\s*([^;]+)/g
    const id_집합 = new Map(마일스톤_목록.map((r) => [r.id, r]))
    const 결과: { 사업_id: number; 일시_ms: number; 새단계: string }[] = []
    for (const h of history) {
      if (h.유형 !== '수정' || !h.내용 || !id_집합.has(h.사업_id)) continue
      const 일시_ms = new Date(h.작성일시).getTime()
      if (Number.isNaN(일시_ms)) continue
      for (const m of h.내용.matchAll(패턴)) {
        결과.push({ 사업_id: h.사업_id, 일시_ms, 새단계: m[2].trim() })
      }
    }
    return 결과
  }, [history, 마일스톤_목록])

  // 타임라인 전체 가로 범위 — 모든 사업의 시작/종료일을 아우르고, 앞뒤로 살짝 여유를 둔다.
  const 범위 = useMemo(() => {
    if (마일스톤_목록.length === 0) return null
    const 오늘 = Date.now()
    const 전체_시작 = Math.min(...마일스톤_목록.map((r) => r.시작_ms), 오늘)
    const 전체_끝 = Math.max(...마일스톤_목록.map((r) => r.종료_ms), 오늘)
    const 여유 = Math.max((전체_끝 - 전체_시작) * 0.04, 하루_MS * 3)
    return { 시작: 전체_시작 - 여유, 끝: 전체_끝 + 여유 }
  }, [마일스톤_목록])

  const 월_눈금 = useMemo(() => {
    if (!범위) return []
    const 목록: { ms: number; pct: number }[] = []
    const d = new Date(범위.시작)
    d.setDate(1)
    d.setHours(0, 0, 0, 0)
    while (d.getTime() < 범위.끝) {
      const ms = d.getTime()
      if (ms >= 범위.시작) 목록.push({ ms, pct: ((ms - 범위.시작) / (범위.끝 - 범위.시작)) * 100 })
      d.setMonth(d.getMonth() + 1)
    }
    return 목록
  }, [범위])

  if (loading) {
    return (
      <div className="page">
        <div className="metric-row">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton skeleton-card" />)}
        </div>
        <div className="skeleton skeleton-chart" style={{ height: 260 }} />
        <div className="skeleton-row" style={{ marginTop: 4 }}>
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton skeleton-line" />)}
        </div>
      </div>
    )
  }

  if (마일스톤_목록.length === 0 || !범위) {
    return (
      <div className="page">
        <div className="alert alert-info">선택된 조건에 시작일/종료일이 모두 있는 건이 없습니다.</div>
      </div>
    )
  }

  const 전체_기간 = 범위.끝 - 범위.시작
  const pct = (ms: number) => ((ms - 범위.시작) / 전체_기간) * 100
  const 오늘_pct = pct(Date.now())

  return (
    <div className="page">
      <h2 className="page-title">마일스톤 타임라인</h2>

      <div className="metric-row">
        <MetricCard label="전체 마일스톤" value={`${kpi.전체}건`} />
        <MetricCard label="마감 초과(미완료)" value={`${kpi.지연}건`} />
        <MetricCard label="진행중" value={`${kpi.진행중}건`} />
        <MetricCard label="평균 진행률" value={`${kpi.평균진행률.toFixed(0)}%`} />
      </div>

      <div className="segmented">
        {(['사업구분', '담당자'] as 그룹기준[]).map((g) => (
          <button
            key={g}
            className={`segmented-item ${그룹 === g ? 'segmented-item-active' : ''}`}
            onClick={() => set그룹(g)}
          >
            {g}별 보기
          </button>
        ))}
      </div>

      <div className="timeline-legend">
        {그룹값_목록.map((g) => (
          <span key={g} className="timeline-legend-item">
            <span className="timeline-legend-dot" style={{ background: 색상맵[g] }} />
            {g}
          </span>
        ))}
      </div>

      <div className="timeline-card">
        <div className="timeline-header">
          <div className="timeline-label-spacer" />
          <div className="timeline-header-track">
            {월_눈금.map((m) => (
              <span key={m.ms} className="timeline-month-label" style={{ left: `${m.pct}%` }}>
                {월_레이블(m.ms)}
              </span>
            ))}
          </div>
        </div>

        <div className="timeline-body">
          <div className="timeline-overlay">
            {월_눈금.map((m) => (
              <div key={m.ms} className="timeline-gridline" style={{ left: `${m.pct}%` }} />
            ))}
            <div className="timeline-today-line" style={{ left: `${오늘_pct}%` }}>
              <span className="timeline-today-label">오늘</span>
            </div>
          </div>

          {마일스톤_목록.map((r) => {
            const left = pct(r.시작_ms)
            const width = pct(r.종료_ms) - left
            const 지연 = r.dday < 0 && r.진행률_숫자 < 100
            const 이_사업_전환 = 전환_목록.filter((t) => t.사업_id === r.id)
            return (
              <div
                key={r.id}
                className={`timeline-row ${지연 ? 'timeline-row-delayed' : ''}`}
                onMouseEnter={() => setHover(r.id)}
                onMouseLeave={() => setHover((h) => (h === r.id ? null : h))}
              >
                <div className="timeline-label" title={r.표시명}>
                  {r.표시명}
                </div>
                <div className="timeline-track">
                  <div
                    className="timeline-bar"
                    style={{ left: `${left}%`, width: `${width}%`, background: `${색상맵[r.그룹값]}33` }}
                  >
                    <div
                      className="timeline-bar-fill"
                      style={{ width: `${r.진행률_숫자}%`, background: 색상맵[r.그룹값] }}
                    />
                  </div>
                  <span className="timeline-bar-pct" style={{ left: `${left + width}%` }}>
                    {r.진행률_숫자.toFixed(0)}%
                  </span>
                  {이_사업_전환.map((t, i) => (
                    <span
                      key={i}
                      className="timeline-marker"
                      style={{
                        left: `${pct(t.일시_ms)}%`,
                        background: 상태_차트_색상[t.새단계] ?? '#8C8C8C',
                      }}
                      title={`${t.새단계} 전환: ${new Date(t.일시_ms).toISOString().slice(0, 10)}`}
                    />
                  ))}
                  {hover === r.id && (
                    <div className="timeline-tooltip" style={{ left: `${left}%` }}>
                      <b>{r.표시명}</b>
                      <br />
                      {r.시작일} ~ {r.종료일} · {r.진행률_숫자.toFixed(0)}%
                      <br />
                      {r.담당자 ? `담당자: ${r.담당자} · ` : ''}
                      {r.dday >= 0 ? `D-${r.dday}` : `${Math.abs(r.dday)}일 초과`}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
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
              <th className="num">진행률</th>
              <th>종료일</th>
              <th className="num">D-day</th>
            </tr>
          </thead>
          <tbody>
            {[...마일스톤_목록]
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
                    <td className="num">{r.진행률_숫자.toFixed(0)}%</td>
                    <td>{r.종료일}</td>
                    <td className="num">{r.dday}</td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
