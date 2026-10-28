import { useEffect, useId, useRef, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import './decision-dialog.css'
import './detail-overlay.css'

export function DetailOverlay({ title, subtitle, eyebrow, variant = 'modal', locked = false, pendingLabel = '正在保存，请稍候…', returnFocus, fallbackFocus, initialFocus, closeLabel = '关闭详情', footer, onClose, children }: {
  title: string; subtitle?: string; eyebrow?: string; variant?: 'modal' | 'drawer' | 'wide'; locked?: boolean
  returnFocus: HTMLElement | null; fallbackFocus?: HTMLElement | null; initialFocus?: RefObject<HTMLElement | null>; closeLabel?: string; pendingLabel?: string; footer?: ReactNode; onClose: () => void; children: ReactNode
}) {
  const element = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = element.current!
    const overflow = document.body.style.overflow
    dialog.showModal()
    initialFocus?.current?.focus()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      const target = returnFocus?.isConnected ? returnFocus : fallbackFocus
      if (target?.isConnected) target.focus()
    }
  }, [returnFocus, fallbackFocus, initialFocus])
  return createPortal(<dialog ref={element} className={`decision-dialog detail-overlay detail-overlay--${variant}`} aria-modal="true" aria-labelledby={titleId} onKeyDown={event => {
    if (event.key !== 'Tab') return
    const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], summary, [tabindex="0"]')].filter(control => control.getClientRects().length > 0)
    const first = controls[0], last = controls.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }} onCancel={event => {
    event.preventDefault()
    if (!locked) onClose()
  }}>
    <header className="decision-dialog-heading"><div>{eyebrow && <span>{eyebrow}</span>}<h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button type="button" autoFocus disabled={locked} onClick={onClose} aria-label={closeLabel}>关闭 <span aria-hidden="true">×</span></button></header>
    <div className="decision-dialog-body">{children}</div>
    <footer className="decision-dialog-footer">{locked ? pendingLabel : footer ?? 'Esc 关闭 · 返回原列表位置'}</footer>
  </dialog>, document.body)
}
