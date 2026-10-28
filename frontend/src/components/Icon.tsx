import type { ReactNode } from 'react'
import type { IconName } from '../navigation'

const PATHS: Record<IconName, ReactNode> = {
  settings: <><path d="m9 3-1 3-3 1-2 4 2 3v3l4 3 3-1 3 1 4-3v-3l2-3-2-4-3-1-1-3Z" /><circle cx="12" cy="12" r="3" /></>,
  overview: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  requirements: (
    <>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M10 12h6M10 16h6M10 8h2" />
    </>
  ),
  parsing: (
    <>
      <path d="M6 3h8l4 4v13H6z" />
      <path d="M14 3v4h4" />
      <circle cx="11" cy="13" r="2.4" />
      <path d="m13 15 2 2" />
    </>
  ),
  bases: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 16 9 5 9-5" />
    </>
  ),
  design: (
    <>
      <path d="M12 3 4 6v6c0 4.4 3.4 7.6 8 9 4.6-1.4 8-4.6 8-9V6l-8-3Z" />
      <path d="m8.5 12 2.3 2.3 4.7-4.6" />
    </>
  ),
  testing: (
    <>
      <path d="M9 3h6" />
      <path d="M10 3v6.2L5.4 17a2.2 2.2 0 0 0 1.9 3.3h9.4a2.2 2.2 0 0 0 1.9-3.3L14 9.2V3" />
      <path d="M7.5 15h9" />
    </>
  ),
  samples: (
    <>
      <path d="M12 3 4 7v10l8 4 8-4V7l-8-4Z" />
      <path d="m4 7 8 4 8-4M12 11v10" />
    </>
  ),
  consistency: (
    <>
      <path d="M20 12a8 8 0 1 1-2.3-5.7" />
      <path d="M20 4v5h-5" />
      <path d="m8.5 12 2.3 2.3 4.7-4.6" />
    </>
  ),
  coordination: (
    <>
      <circle cx="9" cy="8" r="3" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M3 20c0-3.2 2.7-5 6-5s6 1.8 6 5" />
      <path d="M15 15.3c2.7.2 5 1.8 5 4.7" />
    </>
  ),
  packages: (
    <>
      <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="M4 7.5 12 12l8-4.5M12 12v9" />
      <path d="M8 5.2 16 9.7" />
    </>
  ),
  alert: (
    <>
      <path d="M12 3 2.8 20h18.4L12 3Z" />
      <path d="M12 9v5M12 17.5v.2" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.2 12.2 2.5 2.5 5.2-5.4" />
    </>
  ),
  arrow: <path d="M5 12h13m-5-5 5 5-5 5" />,
  download: (
    <>
      <path d="M12 3v12m-4.5-4.5L12 15l4.5-4.5" />
      <path d="M4 19h16" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
}

export function Icon({
  name,
  size = 18,
  className,
}: {
  name: IconName
  size?: number
  className?: string
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
