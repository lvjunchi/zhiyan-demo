import { Notice } from '../ui'
import type { useSavedRefresh } from '../useSavedRefresh'

export function SavedRefreshNotice({ state, busy = false }: { state: ReturnType<typeof useSavedRefresh>; busy?: boolean }) {
  if (!state.pending) return null
  return <Notice kind="error"><p>{state.pending.label}已保存，但页面刷新失败：{state.pending.error}。请重新读取，勿重复提交。</p><button type="button" className="secondary" disabled={busy || state.retrying} onClick={() => void state.retry()}>{state.retrying ? '正在重新读取…' : '重新读取已保存结果'}</button></Notice>
}
