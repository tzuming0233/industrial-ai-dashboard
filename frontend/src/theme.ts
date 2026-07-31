// Claude.ai풍의 따뜻한 중성 팔레트(App.css :root와 동일한 값) — 채도 낮은 배경 +
// 테라코타 포인트. 변수 이름(전기블루 등)은 예전 KPC 남색 팔레트 시절 그대로 두되
// 실제 색상 값만 이 팔레트로 바꿔서, 차트 색과 화면 UI 색이 같이 움직이게 한다.
export const 남색 = '#C9683F'
export const 전기블루 = '#C9683F'
export const 엠버코랄 = '#D1503F'
export const 차트리즈 = '#6E9A6A'
export const 본문색 = '#2C2A26'
export const 보조텍스트색 = '#8A8477'
export const 차트_격자색 = '#E9E4DB'

export const 카테고리_팔레트 = [
  '#C9683F', '#4C7C8C', '#7C9A5C', '#D1A24C', '#8B6F9E', '#B5544A', '#5C8A7A', '#9C9284',
]

export const 상태_차트_색상: Record<string, string> = {
  미분류: '#C7C0B3',
  '사업 발굴': '#9C9284',
  '수주 계획': '#D1A24C',
  '제안 진행': '#C9683F',
  '계약 체결': '#6E9A6A',
  '사업 수행': '#8B6F9E',
}

export const 상태_배지_색상: Record<string, [string, string]> = {
  미분류: ['#F1EFEA', '#8A8477'],
  '사업 발굴': ['#EFEDE7', '#71695A'],
  '수주 계획': ['#FBF0DC', '#96721F'],
  '제안 진행': ['#F3E6DC', '#A8502F'],
  '계약 체결': ['#E7F1E5', '#4E7A4A'],
  '사업 수행': ['#EEE7F3', '#6B5580'],
}

export const 사업단계_옵션 = ['미분류', '사업 발굴', '수주 계획', '제안 진행', '계약 체결', '사업 수행']

export function 고정_색상맵(고유값들: string[]): Record<string, string> {
  const 정렬됨 = [...고유값들].sort()
  const 맵: Record<string, string> = {}
  정렬됨.forEach((v, i) => {
    맵[v] = 카테고리_팔레트[i % 카테고리_팔레트.length]
  })
  return 맵
}

// 카테고리를 여러 색으로 흩뿌리지 않고 테라코타 한 가지 색조의 명암 단계로만 구분한다(app.py의 _단조_색상맵과 동일한 방식).
export function 단조_색상맵(고유값들: string[]): Record<string, string> {
  const 정렬됨 = [...고유값들].sort()
  const 연한: [number, number, number] = [0xf3, 0xe6, 0xdc]
  const 진한: [number, number, number] = [0xa8, 0x50, 0x2f]
  const n = Math.max(정렬됨.length - 1, 1)
  const 맵: Record<string, string> = {}
  정렬됨.forEach((v, i) => {
    const t = i / n
    const rgb = [0, 1, 2].map((c) => Math.round(연한[c] + (진한[c] - 연한[c]) * t))
    맵[v] = `#${rgb.map((x) => x.toString(16).padStart(2, '0')).join('')}`
  })
  return 맵
}

export function 차트_공통레이아웃(showlegend = false) {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: 본문색, family: 'Segoe UI, Malgun Gothic, Pretendard, sans-serif', size: 12 },
    // margin은 최소값일 뿐 — automargin이 긴 한글 라벨(사업구분/담당자/사업명 등)에 맞춰
    // 실제 여백을 늘려준다. automargin 없이는 Plotly가 라벨을 잘라버린다.
    margin: { l: 40, r: 20, t: 40, b: 40 },
    showlegend,
    xaxis: { gridcolor: 차트_격자색, zerolinecolor: 차트_격자색, automargin: true },
    yaxis: { gridcolor: 차트_격자색, zerolinecolor: 차트_격자색, automargin: true },
  }
}
