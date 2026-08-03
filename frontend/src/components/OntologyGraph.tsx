import { useEffect, useRef } from 'react'
import { DataSet } from 'vis-data'
import { Network } from 'vis-network'
import { 본문색 } from '../theme'

export type 그래프_노드 = {
  id: number
  label: string
  title: string
  color: string
  shape: 'box' | 'dot'
  size: number
  borderWidth: number
}

export type 그래프_엣지 = {
  id: number
  from: number
  to: number
  label: string
  title: string
  color: string
}

type Props = {
  nodes: 그래프_노드[]
  edges: 그래프_엣지[]
  height?: number
  onNodeClick: (id: number) => void
  onEdgeClick: (id: number) => void
}

export default function OntologyGraph({ nodes, edges, height = 460, onNodeClick, onEdgeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const callbacksRef = useRef({ onNodeClick, onEdgeClick })
  callbacksRef.current = { onNodeClick, onEdgeClick }

  useEffect(() => {
    if (!containerRef.current) return

    const nodeSet = new DataSet(nodes)
    const edgeSet = new DataSet(
      edges.map((e) => ({ ...e, color: { color: e.color, highlight: e.color }, arrows: 'to', width: 2 })),
    )

    const network = new Network(
      containerRef.current,
      { nodes: nodeSet, edges: edgeSet },
      {
        height: `${height}px`,
        interaction: { hover: true, navigationButtons: true, keyboard: true },
        nodes: { font: { size: 16, face: 'Malgun Gothic, Pretendard, sans-serif', color: 본문색 } },
        edges: {
          font: { size: 12, align: 'top', face: 'Malgun Gothic, Pretendard, sans-serif', color: 본문색 },
          smooth: { enabled: true, type: 'continuous', roundness: 0.5 },
        },
        physics: {
          solver: 'repulsion',
          repulsion: { nodeDistance: 200, centralGravity: 0.15, springLength: 200, springStrength: 0.03, damping: 0.9 },
          stabilization: { enabled: true, iterations: 300, fit: true },
        },
      },
    )

    network.on('click', (params) => {
      if (params.nodes && params.nodes.length > 0) callbacksRef.current.onNodeClick(params.nodes[0])
      else if (params.edges && params.edges.length > 0) callbacksRef.current.onEdgeClick(params.edges[0])
    })

    return () => network.destroy()
  }, [nodes, edges, height])

  return <div ref={containerRef} className="ontology-graph-container" />
}
