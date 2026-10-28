import type { ReactNode } from 'react'

export function Notice({
  kind,
  children,
}: {
  kind: 'error' | 'success' | 'info'
  children: ReactNode
}) {
  return (
    <div
      className={`notice ${kind}`}
      role={kind === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  )
}

export function Badge({
  className,
  children,
}: {
  className: string
  children: ReactNode
}) {
  return <span className={`status ${className}`}>{children}</span>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="state">{children}</p>
}
