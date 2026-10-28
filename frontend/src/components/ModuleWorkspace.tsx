import type { ReactNode } from 'react'
import type { ModuleTabKey, NavigateTo } from '../navigation'
import { WorkspaceJourney } from './WorkspaceJourney'
import './modules.css'

export function ModuleWorkspace({ tab, projectId, onNavigate, children }: {
  tab: ModuleTabKey
  projectId: string
  onNavigate: NavigateTo
  children: ReactNode
}) {
  return <div className="module-surface" data-module={tab}>
    <WorkspaceJourney projectId={projectId} tab={tab} onNavigate={onNavigate} />
    {children}
  </div>
}
