import type { ReactNode } from 'react'
import { DetailOverlay } from './DetailOverlay'

export function DecisionDialog({ title, subtitle, locked, returnFocus, onClose, children }: {
  title: string; subtitle: string; locked: boolean; returnFocus: HTMLElement | null; onClose: () => void; children: ReactNode
}) {
  return <DetailOverlay title={title} subtitle={subtitle} eyebrow="工程决策 · 版本档案" locked={locked} returnFocus={returnFocus} closeLabel="关闭版本详情" onClose={onClose} footer="审核仅作用于当前版本；历史记录保留。Esc 关闭 · 返回原列表位置">{children}</DetailOverlay>
}
