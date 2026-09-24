import { useEffect, useMemo, useRef, useState } from 'react'
import Plot from 'react-plotly.js'
import {
  createAiDiagnosisSession,
  deleteAiDiagnosisSession,
  getAiDiagnosisLayers,
  getAiDiagnosisSession,
  listAiDiagnosisSessions,
  saveAiDiagnosisResponses,
  type AI진단_레이어,
  type AI진단_세션_요약,
} from '../api'
import Icon from '../components/Icon'
import MetricCard from '../components/MetricCard'
import { 전기블루, 차트_공통레이아웃, 차트_격자색 } from '../theme'

function 상대_날짜(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const 일차 = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (일차 <= 0) return '오늘'
  if (일차 === 1) return '어제'
  if (일차 < 7) return `${일차}일 전`
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
}

type 응답_상태 = Record<string, { 수준: number; 메모: string }>

// 진단 세션 목록 — 새 진단 시작, 과거 진단 열람/삭제.
function 세션_목록_뷰({
  세션_목록,
  onOpen,
  onCreate,
  onDelete,
}: {
  세션_목록: AI진단_세션_요약[]
  onOpen: (id: number) => void
  onCreate: (대상명: string, 메모: string) => Promise<void>
  onDelete: (id: number) => void
}) {
  const [모달_열림, set모달_열림] = useState(false)
  const [대상명, set대상명] = useState('')
  const [메모, set메모] = useState('')
  const [처리중, set처리중] = useState(false)
  const [오류, set오류] = useState<string | null>(null)
  const 입력_ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (모달_열림) 입력_ref.current?.focus()
  }, [모달_열림])

  async function 제출(e: React.FormEvent) {
    e.preventDefault()
    if (!대상명.trim() || 처리중) return
    set처리중(true)
    set오류(null)
    try {
      await onCreate(대상명.trim(), 메모.trim())
      set모달_열림(false)
      set대상명('')
      set메모('')
    } catch (err) {
      set오류(err instanceof Error ? err.message : String(err))
    } finally {
      set처리중(false)
    }
  }

  return (
    <div className="page">
      <div className="table-toolbar">
        <h2 style={{ margin: 0, fontSize: 18 }}>제조 AI수준진단</h2>
        <button type="button" className="btn btn-primary" onClick={() => set모달_열림(true)}>
          <Icon name="plus" size={14} />새 진단
        </button>
      </div>

      {세션_목록.length === 0 ? (
        <p className="sidebar-caption">
          아직 진단 기록이 없어요. "새 진단"으로 대상 기업·현장의 제조 AI 수준을 진단해보세요.
        </p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>대상명</th>
                <th>종합단계</th>
                <th>작성자</th>
                <th>최근 수정</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {세션_목록.map((s) => (
                <tr key={s.id} onClick={() => onOpen(s.id)} style={{ cursor: 'pointer' }}>
                  <td>{s.대상명}</td>
                  <td>
                    {s.종합단계.단계}/5 · {s.종합단계.이름}
                  </td>
                  <td>{s.작성자 || '-'}</td>
                  <td>{상대_날짜(s.수정일시)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn btn-secondary"
                      title="이 진단 삭제"
                      aria-label={`'${s.대상명}' 진단 삭제`}
                      onClick={() => onDelete(s.id)}
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {모달_열림 && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => e.target === e.currentTarget && !처리중 && set모달_열림(false)}
        >
          <form className="modal-card" onSubmit={제출} role="dialog" aria-modal="true" aria-label="새 진단">
            <h3 className="modal-title">새 진단</h3>
            <label className="modal-field">
              <span>대상명</span>
              <input
                ref={입력_ref}
                className="text-input"
                value={대상명}
                maxLength={80}
                placeholder="예: ○○제조㈜"
                onChange={(e) => set대상명(e.target.value)}
              />
            </label>
            <label className="modal-field">
              <span>메모 (선택)</span>
              <textarea
                className="text-input"
                rows={3}
                value={메모}
                maxLength={300}
                placeholder="진단 배경·현장 방문 일자 등"
                onChange={(e) => set메모(e.target.value)}
              />
            </label>
            {오류 && <p className="proposal-error">{오류}</p>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => set모달_열림(false)}>
                취소
              </button>
              <button type="submit" className="btn btn-primary" disabled={!대상명.trim() || 처리중}>
                {처리중 ? '만드는 중...' : '만들기'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

// 레이어 1개 카드 — 4단(미착수/P1/P2/P3) 세그먼트, AI 개입 지점 참고, 메모.
function 레이어_카드({
  레이어,
  값,
  onChange,
}: {
  레이어: AI진단_레이어
  값: { 수준: number; 메모: string }
  onChange: (변경: Partial<{ 수준: number; 메모: string }>) => void
}) {
  const [펼침, set펼침] = useState(false)
  const 현재_기준 = 레이어.수준들.find((lv) => lv.수준 === 값.수준)

  return (
    <div className="ai-diag-layer-card">
      <div className="ai-diag-layer-head">
        <span className="ai-diag-layer-code">{레이어.코드}</span>
        <div>
          <p className="ai-diag-layer-name">{레이어.이름}</p>
          <p className="ai-diag-layer-desc">{레이어.설명}</p>
        </div>
      </div>

      <div className="segmented">
        <button
          type="button"
          className={`segmented-item ${값.수준 === 0 ? 'segmented-item-active' : ''}`}
          onClick={() => onChange({ 수준: 0 })}
        >
          미착수
        </button>
        {레이어.수준들.map((lv) => (
          <button
            key={lv.수준}
            type="button"
            className={`segmented-item ${값.수준 === lv.수준 ? 'segmented-item-active' : ''}`}
            onClick={() => onChange({ 수준: lv.수준 })}
          >
            {lv.이름}
          </button>
        ))}
      </div>

      {현재_기준 && <p className="ai-diag-layer-criteria">{현재_기준.설명}</p>}

      <button type="button" className="ai-diag-layer-toggle" onClick={() => set펼침((v) => !v)}>
        <Icon name="chevron" size={12} />
        AI 개입 지점 참고 {펼침 ? '접기' : '보기'}
      </button>
      {펼침 && (
        <ul className="ai-diag-ai-points">
          {레이어.ai개입지점.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}

      <textarea
        className="text-input"
        rows={2}
        placeholder="메모(선택)"
        value={값.메모}
        onChange={(e) => onChange({ 메모: e.target.value })}
      />
    </div>
  )
}

// 진단 세션 1개 상세 — 레이어별 작성 + 레이더 차트 + 종합단계.
function 세션_상세_뷰({
  세션_id,
  레이어_목록,
  onBack,
  onDeleted,
}: {
  세션_id: number
  레이어_목록: AI진단_레이어[]
  onBack: () => void
  onDeleted: () => void
}) {
  const [세션, set세션] = useState<AI진단_세션_요약 | null>(null)
  const [응답, set응답] = useState<응답_상태>({})
  const [저장중, set저장중] = useState(false)
  const [로딩, set로딩] = useState(true)

  useEffect(() => {
    set로딩(true)
    getAiDiagnosisSession(세션_id)
      .then((상세) => {
        set세션(상세)
        const 초기: 응답_상태 = {}
        for (const 레이어 of 레이어_목록) 초기[레이어.코드] = { 수준: 0, 메모: '' }
        for (const r of 상세.응답) 초기[r.레이어코드] = { 수준: r.수준, 메모: r.메모 ?? '' }
        set응답(초기)
      })
      .finally(() => set로딩(false))
  }, [세션_id, 레이어_목록])

  async function 저장() {
    set저장중(true)
    try {
      const 저장됨 = await saveAiDiagnosisResponses(
        세션_id,
        레이어_목록.map((레이어) => ({
          레이어코드: 레이어.코드,
          수준: 응답[레이어.코드]?.수준 ?? 0,
          메모: 응답[레이어.코드]?.메모 ?? '',
        })),
      )
      set세션(저장됨)
    } finally {
      set저장중(false)
    }
  }

  async function 삭제() {
    if (!confirm('이 진단을 삭제할까요?')) return
    await deleteAiDiagnosisSession(세션_id)
    onDeleted()
  }

  const 레이더_데이터 = useMemo(() => {
    const theta = 레이어_목록.map((l) => l.코드)
    const r = 레이어_목록.map((l) => 응답[l.코드]?.수준 ?? 0)
    return { theta: [...theta, theta[0]], r: [...r, r[0]] }
  }, [레이어_목록, 응답])

  if (로딩 || !세션) {
    return (
      <div className="page">
        <div className="skeleton skeleton-chart" />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="table-toolbar">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          <Icon name="arrow-left" size={14} />
          목록으로
        </button>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={삭제}>
            <Icon name="trash" size={14} />
            삭제
          </button>
          <button type="button" className="btn btn-primary" onClick={저장} disabled={저장중}>
            {저장중 ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>

      <h2 style={{ margin: 0, fontSize: 18 }}>{세션.대상명}</h2>

      <div className="metric-row">
        <MetricCard
          label="종합 성숙 단계"
          value={`${세션.종합단계.단계}/5 · ${세션.종합단계.이름}`}
          help={세션.종합단계.부제}
          icon="gauge"
        />
      </div>

      <div className="chart-box chart-box-full">
        <h3 className="chart-title">레이어별 수준 (L1~L9)</h3>
        <Plot
          data={[
            {
              type: 'scatterpolar',
              theta: 레이더_데이터.theta,
              r: 레이더_데이터.r,
              fill: 'toself',
              fillcolor: 'rgba(28, 144, 251, 0.15)',
              line: { color: 전기블루, width: 2 },
              marker: { color: 전기블루, size: 6 },
              hovertemplate: '%{theta}: 수준 %{r}<extra></extra>',
            },
          ]}
          layout={{
            ...차트_공통레이아웃(),
            polar: {
              bgcolor: 'rgba(0,0,0,0)',
              radialaxis: { range: [0, 3], tickvals: [0, 1, 2, 3], gridcolor: 차트_격자색 },
              angularaxis: { gridcolor: 차트_격자색 },
            },
            margin: { l: 40, r: 40, t: 20, b: 20 },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%', height: '100%', flex: 1, minHeight: 0 }}
        />
      </div>

      <div className="ai-diag-layer-grid">
        {레이어_목록.map((레이어) => (
          <레이어_카드
            key={레이어.코드}
            레이어={레이어}
            값={응답[레이어.코드] ?? { 수준: 0, 메모: '' }}
            onChange={(변경) =>
              set응답((prev) => ({
                ...prev,
                [레이어.코드]: { ...(prev[레이어.코드] ?? { 수준: 0, 메모: '' }), ...변경 },
              }))
            }
          />
        ))}
      </div>
    </div>
  )
}

export default function AiDiagnosis() {
  const [레이어_목록, set레이어_목록] = useState<AI진단_레이어[]>([])
  const [세션_목록, set세션_목록] = useState<AI진단_세션_요약[]>([])
  const [로딩, set로딩] = useState(true)
  const [선택_id, set선택_id] = useState<number | null>(null)

  useEffect(() => {
    Promise.all([getAiDiagnosisLayers(), listAiDiagnosisSessions()])
      .then(([레이어들, 세션들]) => {
        set레이어_목록(레이어들)
        set세션_목록(세션들)
      })
      .finally(() => set로딩(false))
  }, [])

  async function 목록_새로고침() {
    set세션_목록(await listAiDiagnosisSessions())
  }

  async function 생성(대상명: string, 메모: string) {
    const { id } = await createAiDiagnosisSession(대상명, 메모)
    await 목록_새로고침()
    set선택_id(id)
  }

  async function 삭제(id: number) {
    if (!confirm('이 진단을 삭제할까요?')) return
    await deleteAiDiagnosisSession(id)
    await 목록_새로고침()
  }

  if (로딩) {
    return (
      <div className="page">
        <div className="skeleton skeleton-line" style={{ height: 36, maxWidth: 420 }} />
        <div className="skeleton skeleton-chart" />
      </div>
    )
  }

  if (선택_id != null) {
    return (
      <세션_상세_뷰
        세션_id={선택_id}
        레이어_목록={레이어_목록}
        onBack={() => {
          set선택_id(null)
          목록_새로고침()
        }}
        onDeleted={() => {
          set선택_id(null)
          목록_새로고침()
        }}
      />
    )
  }

  return (
    <세션_목록_뷰
      세션_목록={세션_목록}
      onOpen={set선택_id}
      onCreate={생성}
      onDelete={삭제}
    />
  )
}
