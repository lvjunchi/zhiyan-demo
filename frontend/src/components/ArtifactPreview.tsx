import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { reviewStatusLabels } from '../uiSupport'
import { modeLabel } from '../businessPresentation'

export function ArtifactPreview({ title, code, revision, status, mode: sourceMode, children }: { title: string; code: string; revision?: number; status: string; mode: string; children: ReactNode }) {
  const mode = modeLabel(sourceMode)
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLElement>(null)
  const titleId = useId()
  useEffect(() => {
    if (!open) return
    const triggerElement = trigger.current
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
      if (event.key === 'Tab') {
        const controls = [...(dialog.current?.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex="0"]') ?? [])].filter(el => !el.hasAttribute('disabled'))
        const first = controls[0], last = controls.at(-1)
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', keydown)
    return () => { document.removeEventListener('keydown', keydown); document.body.style.overflow = previousOverflow; triggerElement?.focus() }
  }, [open])
  return <><button type="button" ref={trigger} className="secondary preview-trigger" onClick={() => setOpen(true)}>预览{title}</button>{open && createPortal(<div className="artifact-overlay"><section ref={dialog} className="artifact-preview" role="dialog" aria-modal="true" aria-labelledby={titleId}><header><div><span className="work-eyebrow">ENGINEERING OUTPUT</span><h2 id={titleId}>{title}预览</h2><p>{code}{revision !== undefined ? ` · V${revision}` : ''} · <span className={`status ${status}`}>{reviewStatusLabels[status as keyof typeof reviewStatusLabels] ?? status}</span> · {mode}</p></div><button type="button" className="secondary" onClick={() => setOpen(false)}>关闭预览</button></header><div className="artifact-preview-body">{children}</div><footer>只读成果预览 · 生成结果须经人工复核 · 版本与来源以记录为准</footer></section></div>, document.body)}</>
}
