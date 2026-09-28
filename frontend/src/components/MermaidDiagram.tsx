import { useEffect, useRef, useState } from 'react'

// mermaid는 번들이 커서(파서 chevrotain 포함) 실제로 ```mermaid 블록을 만난 메시지가
// 있을 때만 동적 import로 불러온다 — AI 채팅을 쓰는 모든 사용자가 매번 다운로드하지
// 않아도 되게.
let mermaid모듈_프라미스: Promise<typeof import('mermaid').default> | null = null

function mermaid_준비() {
  if (!mermaid모듈_프라미스) {
    mermaid모듈_프라미스 = import('mermaid').then((m) => {
      m.default.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' })
      return m.default
    })
  }
  return mermaid모듈_프라미스
}

let 다이어그램_순번 = 0

export default function MermaidDiagram({ code }: { code: string }) {
  const [svg, setSvg] = useState<string | null>(null)
  const [오류, set오류] = useState<string | null>(null)
  const id_ref = useRef(`mermaid-diagram-${++다이어그램_순번}`)

  useEffect(() => {
    let 취소됨 = false
    mermaid_준비()
      .then((mermaid) => mermaid.render(id_ref.current, code))
      .then(({ svg }) => {
        if (!취소됨) {
          setSvg(svg)
          set오류(null)
        }
      })
      .catch((e) => {
        if (!취소됨) set오류(e instanceof Error ? e.message : String(e))
      })
    return () => {
      취소됨 = true
    }
  }, [code])

  if (오류) {
    return (
      <div className="code-block-wrap">
        <pre>{code}</pre>
        <p className="proposal-error">다이어그램을 그리지 못했습니다: {오류}</p>
      </div>
    )
  }
  if (!svg) return <p className="sidebar-caption">다이어그램을 그리는 중...</p>
  // eslint-disable-next-line react/no-danger -- mermaid가 자체 sanitizer(securityLevel: 'strict')로 만든 SVG
  return <div className="mermaid-diagram" dangerouslySetInnerHTML={{ __html: svg }} />
}
