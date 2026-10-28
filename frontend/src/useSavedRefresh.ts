import { useRef, useState } from 'react'
import { toErrorMessage } from './uiSupport'

type PendingRead = { label: string; read: () => Promise<unknown>; error: string }

// Call only after a successful write. Recovery must never repeat that write.
export function useSavedRefresh() {
  const [pending, setPending] = useState<PendingRead | null>(null)
  const [retrying, setRetrying] = useState(false)
  const retryLock = useRef(false)
  async function afterSave(label: string, read: () => Promise<unknown>) {
    try { await read(); setPending(null) }
    catch (error) { setPending({ label, read, error: toErrorMessage(error) }) }
  }
  async function retry() {
    if (!pending || retryLock.current) return
    retryLock.current = true
    setRetrying(true)
    try { await afterSave(pending.label, pending.read) }
    finally { setRetrying(false); retryLock.current = false }
  }
  return { pending, blocked: pending !== null, retrying, afterSave, retry }
}
