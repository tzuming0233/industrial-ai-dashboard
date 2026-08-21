import { useEffect, useRef, useState } from 'react'
import {
  addStaffing,
  deleteStaffing,
  exportXlsx,
  getAnnualTargets,
  getBusiness,
  getStaffing,
  saveAnnualTarget,
  saveBusinessRows,
  type 사업행,
  type 연간목표행,
  type 투입인력행,
  type 편집_사업행,
} from '../api'
import Icon from '../components/Icon'
import { 사업단계_옵션 } from '../theme'

const 주관참여구분_옵션 = ['', '주관', '참여']

const 빈_행: 편집_사업행 = {
  id: null, 구분: '', 업체명: '', 용역명: '', 사업구분: '', 담당자: '', 주관참여구분: '',
  사업단계: '미분류', 진행률: 0, 시작일: null, 종료일: null,
  계약금액: 0, 기수입금액: 0, 당해년도수입금액: 0,
}

type Props = {
  데이터_갱신_신호?: number
}

export default function DataManagement({ 데이터_갱신_신호 }: Props) {
  const [rows, setRows] = useState<편집_사업행[]>([])
  const [loading, setLoading] = useState(true)
  const [수정됨, set수정됨] = useState(false)
  const [외부_변경_배너, set외부_변경_배너] = useState(false)
  const [작성자, set작성자] = useState('')
  const [저장중, set저장중] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [targets, setTargets] = useState<연간목표행[]>([])
  const [목표_연도, set목표_연도] = useState(new Date().getFullYear())
  const [목표매출_억, set목표매출_억] = useState('0')
  const [목표손익_억, set목표손익_억] = useState('0')
  const [목표_저장중, set목표_저장중] = useState(false)

  const [businesses, setBusinesses] = useState<사업행[]>([])
  const [선택된_사업id, set선택된_사업id] = useState<number | null>(null)
  const [staffing, setStaffing] = useState<투입인력행[]>([])
  const [새_이름, set새_이름] = useState('')
  const [새_역할, set새_역할] = useState('')

  async function 새로고침() {
    const biz = await getBusiness()
    setBusinesses(biz)
    setRows(biz.map((b) => ({ ...b })))
    if (선택된_사업id === null && biz.length > 0) set선택된_사업id(biz[0].id)
  }

  useEffect(() => {
    Promise.all([새로고침(), getAnnualTargets().then(setTargets)]).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const 첫_렌더_완료 = useRef(false)
  useEffect(() => {
    if (!첫_렌더_완료.current) {
      첫_렌더_완료.current = true
      return
    }
    if (수정됨) {
      set외부_변경_배너(true)
    } else {
      새로고침()
      getAnnualTargets().then(setTargets)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [데이터_갱신_신호])

  useEffect(() => {
    if (선택된_사업id === null) {
      setStaffing([])
      return
    }
    getStaffing(선택된_사업id).then(setStaffing)
  }, [선택된_사업id])

  function 값_변경<K extends keyof 편집_사업행>(idx: number, 필드: K, 값: 편집_사업행[K]) {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [필드]: 값 } : r)))
    set수정됨(true)
  }

  function 행_추가() {
    setRows((prev) => [...prev, { ...빈_행 }])
    set수정됨(true)
  }

  function 행_삭제(idx: number) {
    setRows((prev) => prev.filter((_, i) => i !== idx))
    set수정됨(true)
  }

  async function 저장() {
    setError(null)
    set저장중(true)
    try {
      await saveBusinessRows(rows, 작성자)
      set수정됨(false)
      set외부_변경_배너(false)
      await 새로고침()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      set저장중(false)
    }
  }

  function 강제_새로고침() {
    set수정됨(false)
    set외부_변경_배너(false)
    새로고침()
    getAnnualTargets().then(setTargets)
  }

  async function 목표_저장_실행() {
    set목표_저장중(true)
    try {
      const 매출 = Math.round(parseFloat(목표매출_억 || '0') * 1e8)
      const 손익 = Math.round(parseFloat(목표손익_억 || '0') * 1e8)
      await saveAnnualTarget(목표_연도, 매출, 손익)
      setTargets(await getAnnualTargets())
    } finally {
      set목표_저장중(false)
    }
  }

  async function 인력_추가_실행() {
    if (선택된_사업id === null || !새_이름.trim()) return
    await addStaffing(선택된_사업id, 새_이름.trim(), 새_역할.trim())
    set새_이름('')
    set새_역할('')
    setStaffing(await getStaffing(선택된_사업id))
  }

  async function 인력_삭제_실행(id: number) {
    await deleteStaffing(id)
    if (선택된_사업id !== null) setStaffing(await getStaffing(선택된_사업id))
  }

  if (loading) return <p className="page-loading">불러오는 중...</p>

  return (
    <div className="page">
      <h2 className="page-title">데이터 관리</h2>
      <p className="sidebar-caption">
        표를 엑셀처럼 직접 수정하세요. 맨 아래 "새 행 추가"로 데이터를 입력하거나, 행의 "삭제"로 뺀 뒤
        "변경사항 저장"을 눌러야 실제로 반영됩니다. 엑셀/CSV 업로드나 자연어로 추가·수정하려면 오른쪽 AI
        채팅에 파일을 첨부하거나 요청하세요.
      </p>

      {외부_변경_배너 && (
        <div className="alert alert-warning">
          다른 곳(AI 채팅 등)에서 데이터가 바뀌었을 수 있습니다 — 새로고침하면 지금 편집 중인 내용은
          사라집니다.{' '}
          <button className="btn btn-secondary" onClick={강제_새로고침}>
            새로고침
          </button>
        </div>
      )}

      <button className="btn btn-secondary" onClick={() => exportXlsx(rows, '사업현황_전체.xlsx')}>
        <Icon name="download" size={14} />
        전체 데이터 엑셀로 내보내기 (.xlsx)
      </button>

      <div className="table-wrap">
        <table className="data-table editable-table">
          <thead>
            <tr>
              <th>구분</th>
              <th>업체명</th>
              <th>용역명</th>
              <th>사업구분</th>
              <th>담당자</th>
              <th>주관/참여</th>
              <th>사업단계</th>
              <th>진행률</th>
              <th>시작일</th>
              <th>종료일</th>
              <th>계약금액</th>
              <th>기수입금액</th>
              <th>당해년도수입금액</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={r.id ?? `new-${idx}`}>
                <td>
                  <input className="text-input" value={r.구분} onChange={(e) => 값_변경(idx, '구분', e.target.value)} />
                </td>
                <td>
                  <input className="text-input" value={r.업체명} onChange={(e) => 값_변경(idx, '업체명', e.target.value)} />
                </td>
                <td>
                  <input className="text-input" value={r.용역명} onChange={(e) => 값_변경(idx, '용역명', e.target.value)} />
                </td>
                <td>
                  <input
                    className="text-input"
                    value={r.사업구분}
                    onChange={(e) => 값_변경(idx, '사업구분', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    value={r.담당자 ?? ''}
                    onChange={(e) => 값_변경(idx, '담당자', e.target.value)}
                  />
                </td>
                <td>
                  <select
                    className="text-input"
                    value={r.주관참여구분 ?? ''}
                    onChange={(e) => 값_변경(idx, '주관참여구분', e.target.value)}
                  >
                    {주관참여구분_옵션.map((v) => (
                      <option key={v} value={v}>
                        {v || '(미지정)'}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    className="text-input"
                    value={r.사업단계}
                    onChange={(e) => 값_변경(idx, '사업단계', e.target.value)}
                  >
                    {사업단계_옵션.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    className="text-input"
                    type="number"
                    min={0}
                    max={100}
                    value={r.진행률}
                    onChange={(e) => 값_변경(idx, '진행률', Number(e.target.value))}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    type="date"
                    value={r.시작일 ?? ''}
                    onChange={(e) => 값_변경(idx, '시작일', e.target.value || null)}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    type="date"
                    value={r.종료일 ?? ''}
                    onChange={(e) => 값_변경(idx, '종료일', e.target.value || null)}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    type="number"
                    value={r.계약금액}
                    onChange={(e) => 값_변경(idx, '계약금액', Number(e.target.value))}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    type="number"
                    value={r.기수입금액}
                    onChange={(e) => 값_변경(idx, '기수입금액', Number(e.target.value))}
                  />
                </td>
                <td>
                  <input
                    className="text-input"
                    type="number"
                    value={r.당해년도수입금액}
                    onChange={(e) => 값_변경(idx, '당해년도수입금액', Number(e.target.value))}
                  />
                </td>
                <td>
                  <button className="btn btn-secondary" onClick={() => 행_삭제(idx)} title="이 행 삭제">
                    <Icon name="trash" size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button className="btn btn-secondary" onClick={행_추가}>
        <Icon name="plus" size={14} />
        새 행 추가
      </button>

      <div className="metric-card">
        <input
          className="text-input"
          placeholder="작성자 (이 변경을 기록할 이름)"
          value={작성자}
          onChange={(e) => set작성자(e.target.value)}
        />
        <div className="proposal-actions">
          <button className="btn btn-primary" disabled={저장중} onClick={저장}>
            변경사항 저장
          </button>
        </div>
        {error && <p className="proposal-error">오류: {error}</p>}
      </div>

      <hr className="divider" />
      <h2 className="page-title">연간 목표 설정</h2>
      <p className="sidebar-caption">대시보드 상단의 매출/손익 달성률은 여기서 설정한 목표를 기준으로 계산됩니다.</p>
      <div className="metric-card">
        <div className="metric-row">
          <input
            className="text-input"
            type="number"
            placeholder="연도"
            value={목표_연도}
            onChange={(e) => set목표_연도(Number(e.target.value))}
          />
          <input
            className="text-input"
            type="number"
            step="0.1"
            placeholder="목표매출(억원)"
            value={목표매출_억}
            onChange={(e) => set목표매출_억(e.target.value)}
          />
          <input
            className="text-input"
            type="number"
            step="0.1"
            placeholder="목표손익(억원)"
            value={목표손익_억}
            onChange={(e) => set목표손익_억(e.target.value)}
          />
        </div>
        <div className="proposal-actions">
          <button className="btn btn-primary" disabled={목표_저장중} onClick={목표_저장_실행}>
            목표 저장
          </button>
        </div>
      </div>
      {targets.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>연도</th>
                <th>목표매출(억원)</th>
                <th>목표손익(억원)</th>
              </tr>
            </thead>
            <tbody>
              {[...targets]
                .sort((a, b) => b.연도 - a.연도)
                .map((t) => (
                  <tr key={t.id}>
                    <td>{t.연도}</td>
                    <td>{(t.목표매출 / 1e8).toFixed(1)}</td>
                    <td>{(t.목표손익 / 1e8).toFixed(1)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      <hr className="divider" />
      <h2 className="page-title">투입 인력 관리</h2>
      <p className="sidebar-caption">사업 하나를 골라 참여 인력을 추가·삭제합니다.</p>
      {businesses.length === 0 ? (
        <p className="sidebar-caption">등록된 사업이 없습니다.</p>
      ) : (
        <div className="metric-card">
          <select
            className="text-input"
            value={선택된_사업id ?? ''}
            onChange={(e) => set선택된_사업id(Number(e.target.value))}
          >
            {[...businesses]
              .sort((a, b) => (a.종료일 ?? '').localeCompare(b.종료일 ?? ''))
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.업체명} · {b.용역명}
                </option>
              ))}
          </select>

          {staffing.length === 0 ? (
            <p className="sidebar-caption">등록된 투입 인력이 없습니다.</p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>이름</th>
                    <th>역할</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {staffing.map((s) => (
                    <tr key={s.id}>
                      <td>{s.이름}</td>
                      <td>{s.역할 || '-'}</td>
                      <td>
                        <button className="btn btn-secondary" onClick={() => 인력_삭제_실행(s.id)}>
                          삭제
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="metric-row">
            <input
              className="text-input"
              placeholder="이름"
              value={새_이름}
              onChange={(e) => set새_이름(e.target.value)}
            />
            <input
              className="text-input"
              placeholder="역할(선택) — 예: PM, 실무자"
              value={새_역할}
              onChange={(e) => set새_역할(e.target.value)}
            />
            <button className="btn btn-secondary" disabled={!새_이름.trim()} onClick={인력_추가_실행}>
              추가
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
