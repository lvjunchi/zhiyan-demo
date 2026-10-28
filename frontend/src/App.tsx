import { useEffect, useState } from 'react'
import { api } from './api'
import { Icon } from './components/Icon'
import { TruckMark } from './components/TruckMark'
import { ModuleWorkspace } from './components/ModuleWorkspace'
import { ObjectFocus } from './components/ObjectFocus'
import type { NavigationFocus } from './navigation'
import { downloadSystemBackup } from './dataTransfer'
import { DEMO_PROJECT_CODE } from './demo'
import {
  TAB_DESCRIPTIONS,
  TAB_GROUPS,
  TAB_LABELS,
  type TabKey,
} from './navigation'
import { BasesPanel } from './panels/BasesPanel'
import { ConsistencyPanel } from './panels/ConsistencyPanel'
import { CoordinationPanel } from './panels/CoordinationPanel'
import { DesignPanel } from './panels/DesignPanel'
import { OverviewPanel } from './panels/OverviewPanel'
import { PackagePanel } from './panels/PackagePanel'
import { ParsingPanel } from './panels/ParsingPanel'
import { RequirementsPanel } from './panels/RequirementsPanel'
import { SamplesPanel } from './panels/SamplesPanel'
import { TestingPanel } from './panels/TestingPanel'
import { SettingsPanel } from './panels/SettingsPanel'
import { applyPreferences, loadPreferences } from './preferences'
import './workspace.css'
import './readability.css'
import './finish.css'
import './components/workflow.css'
import './shell.css'
import './overview-refinements.css'
import './brand-shell.css'
import './overview-stage.css'
import './settings-refinements.css'
import type { Project } from './types'
import { Notice } from './ui'
import { toErrorMessage } from './uiSupport'

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        智
      </span>
      <div className="brand-copy">
        <strong>智研引擎</strong>
        <small>重型变速器协同研制平台</small>
      </div>
    </div>
  )
}

function App() {
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [connectionAttempt, setConnectionAttempt] = useState(0)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [expandedGroup, setExpandedGroup] = useState<string | null>(TAB_GROUPS[0].title)
  const [backupBusy, setBackupBusy] = useState(false)
  const [backupFocus, setBackupFocus] = useState(0)
  const [focusTarget, setFocusTarget] = useState<NavigationFocus | null>(null)
  function navigate(tab: TabKey, focus?: NavigationFocus) {
    const group = TAB_GROUPS.find(item => item.tabs.some(module => module.key === tab))
    if (group && !group.standalone) setExpandedGroup(group.title)
    setActiveTab(tab)
    setFocusTarget(focus ?? null)
  }

  async function handleBackup() {
    setBackupBusy(true); setError('')
    try { await downloadSystemBackup() }
    catch (err) { setError(toErrorMessage(err)) }
    finally { setBackupBusy(false) }
  }

  useEffect(() => {
    applyPreferences(loadPreferences())
    let cancelled = false

    async function loadProjects() {
      setProjectsLoading(true)
      setError('')
      try {
        const data = await api.listProjects()
        if (cancelled) return
        setSelectedProject(data.find((project) => project.display_code === DEMO_PROJECT_CODE) ?? null)
      } catch (err) {
        if (!cancelled) setError(toErrorMessage(err))
      } finally {
        if (!cancelled) setProjectsLoading(false)
      }
    }

    void loadProjects()
    return () => {
      cancelled = true
    }
  }, [connectionAttempt])

  if (projectsLoading) {
    return (
      <div className="app-shell loading-shell">
        <aside className="sidebar">
          <Brand />
        </aside>
        <main className="page">
          <h1>智研引擎 · 研发协同工作台</h1>
          <p className="state">正在加载项目…</p>
        </main>
      </div>
    )
  }

  function renderPanel(project: Project) {
    switch (activeTab) {
      case 'settings':
        return <SettingsPanel backupFocus={backupFocus} projectId={selectedProject?.id} />
      case 'overview':
        return (
          <OverviewPanel key={project.id} project={project} onNavigate={navigate} />
        )
      case 'parsing':
        return <ParsingPanel projectId={project.id} />
      case 'bases':
        return <BasesPanel projectId={project.id} />
      case 'design':
        return <DesignPanel projectId={project.id} />
      case 'testing':
        return <TestingPanel projectId={project.id} />
      case 'samples':
        return <SamplesPanel projectId={project.id} />
      case 'consistency':
        return <ConsistencyPanel projectId={project.id} />
      case 'coordination':
        return <CoordinationPanel projectId={project.id} />
      case 'packages':
        return <PackagePanel projectId={project.id} onNavigate={navigate} />
      case 'requirements':
      default:
        return <RequirementsPanel project={project} focusRequirementId={focusTarget?.objectId} />
    }
  }

  return (
    <div className={`app-shell studio-shell${activeTab === 'overview' ? ' cockpit-shell' : ''}`}>
      <header className="topbar platform-masthead" aria-label="平台品牌栏">
        <Brand />
        <span className="platform-name-divider" aria-hidden="true" />
        <p className="platform-title">复杂高端装备智能定制与自主验证平台</p>
          <div className="topbar-meta">
            <span className="env-badge">
              <span className="dot" aria-hidden="true" />
              本地 SQLite
            </span>
            <span className="review-badge">工程师审核机制</span>
            <button type="button" className="topbar-tool" onClick={() => void handleBackup()} disabled={backupBusy}>{backupBusy ? '正在备份…' : '备份 JSON'}</button>
            <button type="button" className="topbar-tool" onClick={() => { navigate('settings'); setBackupFocus(value => value + 1) }}>恢复备份</button>
          </div>
      </header>
      <aside className="sidebar">

        {selectedProject && (
          <div className="sidebar-project">
            <strong className="project-code">
              定制研发项目
            </strong>
            <span>{selectedProject.customer} · {selectedProject.product}</span>
          </div>
        )}

        {selectedProject && (
          <nav
            className="side-nav"
            role="tablist"
            aria-label="工作台模块"
          >
            <button
              type="button"
              role="tab"
              id="tab-overview"
              aria-selected={activeTab === 'overview'}
              aria-controls="panel-overview"
              className={`side-nav-item overview-item${
                activeTab === 'overview' ? ' active' : ''
              }`}
              onClick={() => navigate('overview')}
            >
              <Icon name="overview" size={18} />
              <span>项目总览</span>
            </button>

            {TAB_GROUPS.map((group) => (
              <div
                key={group.title}
                className={`nav-group${group.standalone ? ' nav-standalone' : ''}${expandedGroup === group.title ? ' is-expanded' : ''}${group.tabs.some(tab => tab.key === activeTab) ? ' contains-active' : ''}`}
                role="presentation"
              >
                {!group.standalone && <button
                  type="button"
                  className="nav-group-toggle"
                  aria-label={group.title}
                  aria-expanded={expandedGroup === group.title}
                  aria-controls={`nav-group-${group.tabs[0].key}`}
                  onClick={() => setExpandedGroup(value => value === group.title ? null : group.title)}
                >
                  <Icon name={group.tabs[0].icon} size={18} />
                  <span>{group.title}</span>
                  <svg className="nav-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m5.5 3.5 4 4.5-4 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>}
                <div className="nav-group-items" id={`nav-group-${group.tabs[0].key}`} hidden={!group.standalone && expandedGroup !== group.title}>
                {group.tabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    role="tab"
                    id={`tab-${tab.key}`}
                    aria-selected={activeTab === tab.key}
                    aria-controls={`panel-${tab.key}`}
                    className={`side-nav-item${
                      activeTab === tab.key ? ' active' : ''
                    }`}
                    onClick={() => navigate(tab.key)}
                  >
                    <Icon name={tab.icon} size={18} />
                    <span>{tab.label}</span>
                  </button>
                ))}
                </div>
              </div>
            ))}
            <button type="button" role="tab" id="tab-settings" aria-selected={activeTab === 'settings'} aria-controls="panel-settings" className={`side-nav-item settings-nav${activeTab === 'settings' ? ' active' : ''}`} onClick={() => navigate('settings')}><Icon name="settings" /><span>系统设置</span></button>
          </nav>
        )}

        <div className="sidebar-footer">
          <TruckMark />
          <strong>重型商用车 · 协同研制</strong>
          <span>AI + 工程知识 + 人机协同</span>
          <span className="local-system-tag">本地可操作演示系统</span>
        </div>
      </aside>

      <div className="workspace">


        <main className="page">
          <header className="page-header">
            <div>
              <h1>{TAB_LABELS[activeTab]}</h1>
              <p className="subtitle">
                {TAB_DESCRIPTIONS[activeTab]}
              </p>
            </div>
          </header>

          {focusTarget && <ObjectFocus key={`${activeTab}-${focusTarget.objectId ?? 'missing'}`} target={focusTarget} onReturn={() => navigate(focusTarget.returnTab ?? 'packages')} />}
          {error && <Notice kind="error">{error}</Notice>}

          {!selectedProject ? (
            <section className="panel">
              <p className="state">
                {error ? '项目数据暂时不可用，请检查本地服务。' : '尚未初始化演示项目，请先准备演示数据。'}
              </p>
              {error && <><p className="hint">请先运行项目根目录的 Start-Demo.cmd，看到“系统就绪”后重试。现有项目数据会保留。</p><button type="button" onClick={() => setConnectionAttempt(value => value + 1)}>重试连接</button></>}
            </section>
          ) : (
            selectedProject && (
              <div
                role="tabpanel"
                id={`panel-${activeTab}`}
                aria-labelledby={`tab-${activeTab}`}
                className="tab-panel"
              >
                {activeTab === 'overview' || activeTab === 'settings' ? renderPanel(selectedProject) : <ModuleWorkspace tab={activeTab} projectId={selectedProject.id} onNavigate={navigate}>{renderPanel(selectedProject)}</ModuleWorkspace>}
              </div>
            )
          )}
        </main>
      </div>
    </div>
  )
}

export default App
