import { useEffect, useRef } from 'react'
import type { ForceGraph3DInstance } from '3d-force-graph'
import type { 그래프_노드, 그래프_엣지 } from './OntologyGraph'

type G3D_노드 = { id: number; label: string; title: string; color: string; val: number }
type G3D_링크 = { id: number; source: number; target: number; label: string; title: string; color: string }

type Props = {
  nodes: 그래프_노드[]
  edges: 그래프_엣지[]
  height?: number
  onNodeClick: (id: number) => void
  onEdgeClick?: (id: number) => void
}

// vis-network(2D)와 같은 데이터를 받아 three.js 기반 3D 힘-방향 그래프로 그린다. 라이브러리가
// 커서(three.js 포함) 실제로 3D 보기를 켰을 때만 동적 import한다.
export default function OntologyGraph3D({ nodes, edges, height = 460, onNodeClick, onEdgeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<ForceGraph3DInstance<G3D_노드, G3D_링크> | null>(null)
  const callbacksRef = useRef({ onNodeClick, onEdgeClick })
  callbacksRef.current = { onNodeClick, onEdgeClick }

  useEffect(() => {
    let 취소됨 = false

    import('3d-force-graph').then(({ default: ForceGraph3D }) => {
      if (취소됨 || !containerRef.current) return
      const graph = new ForceGraph3D(containerRef.current) as unknown as ForceGraph3DInstance<G3D_노드, G3D_링크>
      graph
        .width(containerRef.current.clientWidth)
        .height(height)
        .backgroundColor('rgba(0,0,0,0)')
        .nodeLabel((n) => n.title)
        .nodeColor((n) => n.color)
        .nodeVal((n) => n.val)
        .nodeRelSize(3)
        .linkLabel((l) => l.title || l.label)
        .linkColor((l) => l.color)
        .linkOpacity(0.6)
        .linkWidth(1)
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .onNodeClick((n) => callbacksRef.current.onNodeClick(n.id))
        .onLinkClick((l) => callbacksRef.current.onEdgeClick?.(l.id))
      graphRef.current = graph
      graph.graphData({
        nodes: nodes.map((n) => ({ id: n.id, label: n.label, title: n.title, color: n.color, val: n.size })),
        links: edges.map((e) => ({
          id: e.id, source: e.from, target: e.to, label: e.label, title: e.title, color: e.color,
        })),
      })
    })

    function 리사이즈() {
      if (containerRef.current) graphRef.current?.width(containerRef.current.clientWidth)
    }
    window.addEventListener('resize', 리사이즈)

    return () => {
      취소됨 = true
      window.removeEventListener('resize', 리사이즈)
      graphRef.current?._destructor()
      graphRef.current = null
    }
  }, [nodes, edges, height])

  return <div ref={containerRef} className="ontology-graph-container" style={{ height }} />
}
