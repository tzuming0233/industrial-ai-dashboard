import type { ReactNode } from 'react'

// Claude.ai 스타일의 UI로 다듬으면서, 다채로운 이모지 대신 얇은 선(line) 아이콘으로 통일한다.
// 별도 아이콘 라이브러리를 새로 설치하지 않고 필요한 만큼만 직접 그린 최소 SVG 세트.
export type IconName =
  | 'sparkles'
  | 'chart'
  | 'table'
  | 'calendar'
  | 'plus'
  | 'folder'
  | 'search'
  | 'trash'
  | 'paperclip'
  | 'x'
  | 'send'
  | 'network'
  | 'book'
  | 'mic'
  | 'download'

const paths: Record<IconName, ReactNode> = {
  sparkles: (
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
  ),
  chart: <path d="M4 20V10M11 20V4M18 20v-7" />,
  table: <path d="M3 5h18M3 12h18M3 19h18M8 5v14M16 5v14" />,
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  folder: <path d="M3.5 6.5a1.5 1.5 0 0 1 1.5-1.5h4l2 2h9a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5z" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m20 20-4.5-4.5" /></>,
  trash: <path d="M4.5 6.5h15M9 6.5V4.8a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1.7M18 6.5l-.7 12.3a1.8 1.8 0 0 1-1.8 1.7H8.5a1.8 1.8 0 0 1-1.8-1.7L6 6.5" />,
  paperclip: <path d="M17.5 8.5 9.9 16.1a3 3 0 1 1-4.2-4.2l8.5-8.5a2 2 0 1 1 2.8 2.8l-8.1 8.1a1 1 0 1 1-1.4-1.4l7.4-7.4" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  send: <path d="M4 12 20 4l-6 16-3-7-7-3Z" />,
  network: (
    <>
      <circle cx="12" cy="5" r="2.3" />
      <circle cx="5" cy="19" r="2.3" />
      <circle cx="19" cy="19" r="2.3" />
      <path d="M12 7.3v4M10.3 15.5 7 17.7M13.7 15.5 17 17.7" />
    </>
  ),
  book: (
    <path d="M4 5.5A2 2 0 0 1 6 3.5h13a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2M4 5.5A2 2 0 0 0 6 7.5h14M4 5.5v14a2 2 0 0 0 2 2" />
  ),
  mic: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" />
    </>
  ),
  download: <path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5M4.5 17.5V20a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1v-2.5" />,
}

export default function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      {paths[name]}
    </svg>
  )
}
