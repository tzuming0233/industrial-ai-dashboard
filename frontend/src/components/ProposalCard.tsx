import type { 제안요약 } from '../api'

type Props = {
  요약: 제안요약
  처리중: boolean
  onApply: () => void
  onCancel: () => void
}

function 값표시(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  return String(v)
}

function 행테이블({ 행 }: { 행: Record<string, unknown>[] }) {
  if (!행.length) return <p className="proposal-empty">표시할 항목이 없습니다.</p>
  const 컬럼 = Object.keys(행[0])
  return (
    <div className="proposal-table-wrap">
      <table className="proposal-table">
        <thead>
          <tr>
            {컬럼.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {행.map((row, i) => (
            <tr key={i}>
              {컬럼.map((c) => (
                <td key={c}>{값표시(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ProposalCard({ 요약, 처리중, onApply, onCancel }: Props) {
  const { 유형 } = 요약

  return (
    <div className="proposal-card">
      {요약.오류 ? (
        <p className="proposal-error">{요약.오류}</p>
      ) : (
        <>
          {(유형 === '업로드' || 유형 === 'propose_add_business') && (
            <>
              {요약.경고?.map((w, i) => (
                <p key={i} className="proposal-warning">
                  {w}
                </p>
              ))}
              <p className="proposal-caption">{요약.행?.length ?? 0}건을 추가합니다.</p>
              {요약.행 && <행테이블 행={요약.행} />}
            </>
          )}

          {(유형 === 'propose_update_business' ||
            유형 === 'propose_add_note' ||
            유형 === 'propose_update_note') && (
            <>
              <p className="proposal-caption">
                {유형 === 'propose_add_note' ? `새 노트: ${요약.제목}` : 요약.제목}
              </p>
              {요약.변경?.map((c, i) => (
                <p key={i} className="proposal-change-row">
                  <b>{c.필드}</b>: {값표시(c.이전값)} → {값표시(c.새값)}
                </p>
              ))}
            </>
          )}

          {(유형 === 'propose_delete_business' || 유형 === 'propose_delete_note') && (
            <>
              <p className="proposal-warning">{요약.행?.length ?? 0}건이 삭제됩니다.</p>
              {요약.행 && <행테이블 행={요약.행} />}
            </>
          )}

          {(유형 === 'propose_add_relations' ||
            유형 === 'propose_delete_relations' ||
            유형 === 'propose_update_relations') && (
            <>
              {유형 === 'propose_delete_relations' && (
                <p className="proposal-warning">{요약.관계?.length ?? 0}개 관계가 삭제됩니다.</p>
              )}
              {유형 === 'propose_add_relations' && (
                <p className="proposal-caption">{요약.관계?.length ?? 0}개 관계를 온톨로지에 추가합니다.</p>
              )}
              {유형 === 'propose_update_relations' && (
                <p className="proposal-caption">{요약.관계?.length ?? 0}개 관계를 이렇게 수정합니다.</p>
              )}
              {요약.관계?.map((r, i) => (
                <div key={i} className="proposal-relation-row">
                  <b>{r.노드1}</b> —[{r.관계유형}]→ <b>{r.노드2}</b>
                  {r.설명 && <p className="proposal-caption">{r.설명}</p>}
                </div>
              ))}
            </>
          )}
        </>
      )}

      {!요약.오류 && (
        <div className="proposal-actions">
          <button className="btn btn-primary" disabled={처리중} onClick={onApply}>
            적용
          </button>
          <button className="btn btn-secondary" disabled={처리중} onClick={onCancel}>
            취소
          </button>
        </div>
      )}
    </div>
  )
}
