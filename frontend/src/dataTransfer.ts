import { api } from './api'

export async function downloadSystemBackup() {
  const { blob, filename } = await api.downloadSystemBackup()
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url; link.download = filename ?? 'zhiyan-backup.json'
    document.body.append(link); link.click(); link.remove()
  } finally { URL.revokeObjectURL(url) }
}
