// Streamlit CSS 작업 때 검증한 KPC 팔레트를 그대로 재사용한다 (app.py의 _테마_토큰()과 동일).
export const 남색 = '#1C90FB'
export const 전기블루 = '#1C90FB'
export const 엠버코랄 = '#FC5356'
export const 차트리즈 = '#20C997'
export const 본문색 = '#1D2129'
export const 보조텍스트색 = '#8C8C8C'
export const 차트_격자색 = '#E6E6E6'

export const 카테고리_팔레트 = [
  '#1C90FB', '#5F65FF', '#20C997', '#F0C325', '#F8A457', '#FC5356', '#39B0D2', '#8C8C8C',
]

export const 상태_차트_색상: Record<string, string> = {
  미분류: '#C4C4C4',
  '사업 발굴': '#8C8C8C',
  '수주 계획': '#F0C325',
  '제안 진행': '#1C90FB',
  '계약 체결': '#20C997',
  '사업 수행': '#5F65FF',
}

export const 상태_배지_색상: Record<string, [string, string]> = {
  미분류: ['#F5F5F5', '#8C8C8C'],
  '사업 발굴': ['#F0F0F0', '#5B6B82'],
  '수주 계획': ['#FFF1D6', '#B7791F'],
  '제안 진행': ['#EFF7FF', '#1C90FB'],
  '계약 체결': ['#E6F9F0', '#20C997'],
  '사업 수행': ['#F1EEFF', '#5F65FF'],
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

// 카테고리를 여러 색으로 흩뿌리지 않고 남색 한 가지 색조의 명암 단계로만 구분한다(app.py의 _단조_색상맵과 동일).
export function 단조_색상맵(고유값들: string[]): Record<string, string> {
  const 정렬됨 = [...고유값들].sort()
  const 연한: [number, number, number] = [0xef, 0xf7, 0xff]
  const 진한: [number, number, number] = [0x14, 0x78, 0xd6]
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
