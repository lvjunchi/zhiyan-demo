import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TabKey } from '../navigation'
import type { Project, ProjectOverview } from '../types'
import { toErrorMessage } from '../uiSupport'
import { ProjectShowcase } from './ProjectShowcase'
type Navigate = (tab: TabKey) => void

export function OverviewPanel(props: Parameters<typeof OverviewWorkspace>[0]) {
  return <OverviewWorkspace key={props.project.id} {...props} />
}

function OverviewWorkspace({ project, onNavigate }: { project: Project; onNavigate: Navigate }) {
  const [data, setData] = useState<ProjectOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    let cancelled = false
    api.getProjectOverview(project.id).then((overview) => { if (!cancelled) setData(overview) })
      .catch((err: unknown) => { if (!cancelled) setError(toErrorMessage(err)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [project.id, reloadKey])
  function reload() { setLoading(true); setError(''); setReloadKey(value => value + 1) }
  if (loading) return <section className="panel"><p className="state">正在加载项目总览…</p></section>
  if (error) return <section className="panel"><div className="notice error" role="alert">{error}</div><button type="button" onClick={reload}>重新加载</button></section>
  if (!data) return null
  return <ProjectShowcase data={data} onNavigate={onNavigate} onReload={reload} />
}
