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
  onEdgeClick?: (id: number) => void
  // 하단 "관계 추가" 매니퓰레이션 버튼으로 두 노드를 드래그해 연결하면 호출된다.
  // 실제 저장은 하지 않고(반환값으로 vis의 로컬 추가를 취소) 부모가 기존
  // 관계유형 입력 폼을 그 두 노드로 미리 채운 채 열도록 위임한다. 안 넘기면
  // (예: 노트 편집 화면의 미니 그래프) 드래그 편집 자체가 비활성화된다.
  onDragConnect?: (fromId: number, toId: number) => void
  // 노트 편집 화면 등 작은 임베드 뷰에서는 내비게이션 버튼을 숨긴다.
  compact?: boolean
}

const 매니퓰레이션_한글 = {
  edit: '편집',
  del: '삭제',
  back: '뒤로',
  addNode: '노드 추가',
  addDescription: '원하는 위치를 클릭해 노드를 추가하세요.',
  addEdge: '관계 추가',
  edgeDescription: '한 노드에서 다른 노드로 드래그해 연결하세요.',
  editNode: '노드 편집',
  editEdge: '관계 편집',
  editEdgeDescription: '연결의 끝점을 드래그해 다른 노드로 옮기세요.',
  createEdgeError: '노드가 아닌 곳에는 연결을 만들 수 없습니다.',
  deleteClusterError: '클러스터는 삭제할 수 없습니다.',
  editClusterError: '클러스터는 편집할 수 없습니다.',
}

export default function OntologyGraph({
  nodes,
  edges,
  height = 460,
  onNodeClick,
  onEdgeClick,
  onDragConnect,
  compact = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const callbacksRef = useRef({ onNodeClick, onEdgeClick, onDragConnect })
  callbacksRef.current = { onNodeClick, onEdgeClick, onDragConnect }

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
        interaction: { hover: true, navigationButtons: !compact, keyboard: !compact, zoomView: !compact },
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
        ...(onDragConnect
          ? {
              manipulation: {
                enabled: true,
                addNode: false,
                editNode: false,
                editEdge: false,
                deleteNode: false,
                deleteEdge: false,
                addEdge: (edgeData: { from: number; to: number }, callback: (data: unknown) => void) => {
                  if (edgeData.from !== edgeData.to) {
                    callbacksRef.current.onDragConnect?.(edgeData.from, edgeData.to)
                  }
                  callback(null) // 로컬 데이터셋에는 추가하지 않는다 — 실제 저장은 부모의 확인 폼을 거친다.
                },
                locale: 'ko',
                locales: { ko: 매니퓰레이션_한글 },
              },
            }
          : {}),
      },
    )

    network.on('click', (params) => {
      if (params.nodes && params.nodes.length > 0) callbacksRef.current.onNodeClick(params.nodes[0])
      else if (params.edges && params.edges.length > 0) callbacksRef.current.onEdgeClick?.(params.edges[0])
    })

    return () => network.destroy()
  }, [nodes, edges, height, compact, !!onDragConnect])

  return <div ref={containerRef} className="ontology-graph-container" style={{ height }} />
}
