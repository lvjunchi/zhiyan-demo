import { useEffect, useState } from 'react'
import type { NavigationFocus } from '../navigation'
import { Notice } from '../ui'

export function ObjectFocus({ target, onReturn }: { target: NavigationFocus; onReturn: () => void }) {
  const [found, setFound] = useState(false)
  const [waiting, setWaiting] = useState(true)
  useEffect(() => {
    if (!target.objectId) return
    let marked: HTMLElement | undefined
    const locate = () => {
      const element = [...document.querySelectorAll<HTMLElement>('[data-object-id]')].find(item => item.dataset.objectId === target.objectId && item.getClientRects().length > 0)
      if (element && element !== marked) {
        marked?.removeAttribute('data-focus-target')
        marked = element
        element.setAttribute('data-focus-target', 'true')
        element.scrollIntoView({ behavior: 'auto', block: 'center' })
        setFound(true)
      }
    }
    const observer = new MutationObserver(locate)
    observer.observe(document.querySelector('.tab-panel') ?? document.body, { subtree: true, childList: true })
    const frame = requestAnimationFrame(locate)
    const timer = window.setTimeout(() => setWaiting(false), 2000)
    return () => { observer.disconnect(); cancelAnimationFrame(frame); clearTimeout(timer); marked?.removeAttribute('data-focus-target') }
  }, [target.objectId])
  return <Notice kind="info"><div className="object-focus-notice"><div><strong>{target.origin === 'change' ? '来自需求变更' : '来自评审材料'}：{target.message}</strong><p>{target.objectId ?? '当前工作区'}{target.revision ? ` · 引用 V${target.revision}，请与当前版本核对` : ''} · {found ? '已高亮关联记录' : target.objectId && waiting ? '正在查找关联记录…' : target.objectId ? '当前列表未展示该对象，请查看历史版本或相关记录' : '请在本工作区补齐所缺产物'}</p></div><button type="button" className="secondary" onClick={onReturn}>{target.origin === 'change' ? '返回变更工作区' : '返回评审材料'}</button></div></Notice>
}
