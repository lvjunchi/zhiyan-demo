import type { SourceDocumentCreate } from './types'

export interface ImportDraft {
  projectId: string
  importId?: string
  displayCode: string
  docType: SourceDocumentCreate['doc_type']
  version: string
  content: string
  mappingText: string
  original?: SourceDocumentCreate['original_file']
  sourceId?: string
  updatedAt: string
}
const databaseName = 'zhiyan-import-drafts-v1'
const key = (projectId: string, importId?: string) => JSON.stringify([projectId, importId ?? 'manual'])
let pending: Promise<unknown> = Promise.resolve()
function ordered<T>(operation: () => Promise<T>): Promise<T> {
  const next = pending.then(operation, operation)
  pending = next.catch(() => undefined)
  return next
}
export const flushImportDrafts = () => pending

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('浏览器不支持草稿存储')); return }
    const request = indexedDB.open(databaseName, 1)
    request.onupgradeneeded = () => {
      for (const name of ['drafts', 'originals']) request.result.createObjectStore(name, { keyPath: 'key' }).createIndex('projectId', 'projectId')
    }
    request.onerror = () => reject(request.error ?? new Error('草稿存储无法打开'))
    request.onblocked = () => reject(new Error('草稿存储被其他页面占用'))
    request.onsuccess = () => resolve(request.result)
  })
}

function object(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function decode(value: unknown, originalValue: unknown, projectId: string): ImportDraft {
  if (!object(value) || value.projectId !== projectId || typeof value.hasOriginal !== 'boolean' || !['displayCode', 'version', 'content', 'mappingText', 'updatedAt'].every(field => typeof value[field] === 'string')
    || !['protocol', 'change_notice', 'drawing', 'test_report', 'communication', 'other'].includes(String(value.docType))
    || (value.importId !== undefined && typeof value.importId !== 'string') || (value.sourceId !== undefined && typeof value.sourceId !== 'string')
    || value.key !== key(projectId, value.importId as string | undefined)) throw new Error('核对草稿格式无效，请重新选择原文件')
  let original: ImportDraft['original']
  if (value.hasOriginal) {
    if (!object(originalValue) || originalValue.projectId !== projectId || originalValue.key !== value.key || !object(originalValue.original)) throw new Error('草稿原件缺失，请重新选择原文件')
    const file = originalValue.original
    if (typeof file.filename !== 'string' || typeof file.data_base64 !== 'string' || file.data_base64.length > 12 * 1024 * 1024 || typeof file.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(file.sha256)) throw new Error('草稿原件信息无效，请重新选择原文件')
    original = { filename: file.filename, data_base64: file.data_base64, sha256: file.sha256 }
  }
  return { projectId, importId: value.importId as string | undefined, displayCode: String(value.displayCode), docType: value.docType as ImportDraft['docType'], version: String(value.version), content: String(value.content), mappingText: String(value.mappingText), original, sourceId: value.sourceId as string | undefined, updatedAt: String(value.updatedAt) }
}

export function saveImportDraft(draft: ImportDraft): Promise<void> {
  return ordered(async () => {
    const db = await database()
    return new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(['drafts', 'originals'], 'readwrite')
      transaction.oncomplete = () => { db.close(); resolve() }
      transaction.onabort = () => { db.close(); reject(transaction.error ?? new Error('核对草稿未能保存')) }
      try {
      const id = key(draft.projectId, draft.importId)
      const { original, ...form } = draft
      transaction.objectStore('drafts').put({ ...form, key: id, hasOriginal: Boolean(original) })
      const files = transaction.objectStore('originals')
      if (!original) files.delete(id)
      else {
        const current = files.get(id)
        current.onsuccess = () => {
          const value: unknown = current.result
          if (!object(value) || !object(value.original) || value.original.sha256 !== original.sha256) files.put({ key: id, projectId: draft.projectId, original })
        }
      }
      } catch (error) { transaction.abort(); db.close(); reject(error) }
    })
  })
}

export function readImportDrafts(projectId: string): Promise<ImportDraft[]> {
  return ordered(async () => {
    const db = await database()
    return new Promise<ImportDraft[]>((resolve, reject) => {
      const transaction = db.transaction(['drafts', 'originals'], 'readonly')
      const forms = transaction.objectStore('drafts').index('projectId').getAll(projectId)
      const files = transaction.objectStore('originals').index('projectId').getAll(projectId)
      transaction.oncomplete = () => {
        db.close()
        try {
          const originals = new Map<string, unknown>((files.result as unknown[]).filter(object).map(row => [String(row.key), row]))
          resolve((forms.result as unknown[]).map(row => decode(row, object(row) ? originals.get(String(row.key)) : undefined, projectId)).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)))
        } catch (error) { reject(error) }
      }
      transaction.onabort = () => { db.close(); reject(transaction.error ?? new Error('核对草稿未能读取')) }
    })
  })
}

export function removeImportDraft(projectId: string, importId?: string): Promise<void> {
  return ordered(async () => {
    const db = await database()
    return new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(['drafts', 'originals'], 'readwrite')
      for (const name of ['drafts', 'originals']) transaction.objectStore(name).delete(key(projectId, importId))
      transaction.oncomplete = () => { db.close(); resolve() }
      transaction.onabort = () => { db.close(); reject(transaction.error ?? new Error('核对草稿未能移除')) }
    })
  })
}

export function clearImportDrafts(projectId?: string): Promise<void> {
  return ordered(async () => {
    const db = await database()
    return new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(['drafts', 'originals'], 'readwrite')
      for (const name of ['drafts', 'originals']) {
        const store = transaction.objectStore(name)
        if (!projectId) store.clear()
        else {
          const request = store.index('projectId').openKeyCursor(projectId)
          request.onsuccess = () => { const cursor = request.result; if (cursor) { store.delete(cursor.primaryKey); cursor.continue() } }
        }
      }
      transaction.oncomplete = () => { db.close(); resolve() }
      transaction.onabort = () => { db.close(); reject(transaction.error ?? new Error('核对草稿未能清理')) }
    })
  })
}
