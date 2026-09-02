import type { 명확화_질문 } from '../api'

type Props = {
  질문: 명확화_질문
  onSelect: (label: string) => void
}

export default function QuestionCard({ 질문, onSelect }: Props) {
  return (
    <div className="proposal-card question-card">
      <p className="proposal-caption">{질문.질문}</p>
      <div className="question-options">
        {질문.선택지.map((opt, i) => (
          <button
            key={i}
            type="button"
            className="btn btn-secondary question-option-btn"
            onClick={() => onSelect(opt.label)}
          >
            <span className="question-option-label">{opt.label}</span>
            {opt.description && <span className="question-option-desc">{opt.description}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}
