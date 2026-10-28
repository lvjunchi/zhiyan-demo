import { useEffect, useState } from 'react'
import { api } from '../api'
import { Icon } from '../components/Icon'
import { loadPreferences, savePreferences } from '../preferences'
import { Notice } from '../ui'
import { DEMO_ACTOR, toErrorMessage } from '../uiSupport'
import { BackupPanel } from './BackupPanel'
import { ProjectClearPanel } from './ProjectClearPanel'

interface Health { status: string; database: string; schema_version: string }
export function SettingsPanel({ backupFocus = 0, projectId }: { backupFocus?: number; projectId?: string }) {
  const [preferences, setPreferences] = useState(loadPreferences)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState('')
  const [checking, setChecking] = useState(true)
  const [reload, setReload] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api.getHealth().then((result) => { if (!cancelled) setHealth(result) })
      .catch((err: unknown) => { if (!cancelled) setHealthError(toErrorMessage(err)) })
      .finally(() => { if (!cancelled) setChecking(false) })
    return () => { cancelled = true }
  }, [reload])
  function save() {
    setMessage(''); setError('')
    try { savePreferences(preferences); setMessage('显示设置已保存，重新打开系统后仍会生效。') }
    catch (err) { setError(`设置未能保存：${toErrorMessage(err)}`) }
  }
  return <div className="settings-layout">
    <section className="panel settings-intro"><span className="settings-emblem"><Icon name="settings" size={25} /></span><div><span className="settings-eyebrow">工作台管理</span><h2>系统配置与数据管理</h2><p>统一管理界面偏好、本地运行环境与项目数据。</p></div><span className="settings-local-label">本机设置</span></section>
    <section className="panel settings-card settings-display"><header><div className="settings-section-heading"><span className="settings-card-icon"><Icon name="overview" size={20} /></span><div><h2>显示与交互</h2><p>调整阅读密度与动效，保存后在当前浏览器生效。</p></div></div></header>
      <label className="settings-field">信息密度<select value={preferences.density} onChange={(event) => setPreferences({ ...preferences, density: event.target.value as 'comfortable' | 'compact' })}><option value="comfortable">舒适 · 更清晰的阅读间距</option><option value="compact">紧凑 · 同屏显示更多内容</option></select></label>
      <label className="settings-toggle"><input type="checkbox" aria-label="减少界面动效" checked={preferences.reduceMotion} onChange={(event) => setPreferences({ ...preferences, reduceMotion: event.target.checked })} /><span>减少界面动效<small>关闭装饰动画与过渡，便于稳定展示和阅读。</small></span></label>
      <button type="button" className="showcase-primary" onClick={save}>保存显示设置</button>
      {message && <Notice kind="success">{message}</Notice>}{error && <Notice kind="error">{error}</Notice>}
    </section>
    <section className="panel settings-card settings-runtime"><header><div className="settings-section-heading"><span className="settings-card-icon"><Icon name="consistency" size={20} /></span><div><h2>运行状态</h2><p>检测本地服务与数据库连接，状态来自实际探测。</p></div></div></header>
      <div className={`settings-status ${healthError ? 'is-failed' : checking ? 'is-checking' : ''}`}><span className={`settings-status-dot ${healthError ? 'failed' : checking ? 'checking' : ''}`} /><strong>{checking ? '正在检查本地服务…' : healthError ? '本地服务连接失败' : health?.status === 'ok' && health.database === 'connected' ? '数据库已连接' : '服务状态异常'}</strong></div>
      {healthError && <p className="settings-health-error">{healthError}</p>}
      {health && !checking && !healthError && <dl className="settings-facts"><div><dt>数据存储</dt><dd>SQLite · 本地持久化</dd></div><div><dt>数据库迁移版本</dt><dd>{health.schema_version}</dd></div></dl>}
      <button type="button" className="secondary" disabled={checking} onClick={() => { setChecking(true); setHealth(null); setHealthError(''); setReload((value) => value + 1) }}>重新检查连接</button>
    </section>
    <div className="settings-data-area"><div className="settings-area-heading"><span className="settings-card-icon"><Icon name="packages" size={20} /></span><div><h2>数据管理</h2><p>备份与恢复完整工作数据，按需重新开始当前项目。</p></div></div>
      <BackupPanel focusRequest={backupFocus} />
      {projectId && <ProjectClearPanel key={projectId} projectId={projectId} />}
    </div>
    <section className="panel settings-card settings-about"><header><div className="settings-section-heading"><span className="settings-card-icon"><Icon name="requirements" size={20} /></span><div><h2>系统与能力说明</h2><p>智研引擎 · 复杂高端装备智能定制与自主验证平台</p></div></div></header>
      <dl className="settings-facts"><div><dt>应用范围</dt><dd>本地单用户 Demo，使用合成或脱敏数据。</dd></div><div><dt>辅助生成</dt><dd>需求解析、型谱匹配与设计草案使用受控规则；模拟或人工结果在产物中标明。</dd></div><div><dt>真实业务记录</dt><dd>需求版本、引用、审核、失效传播、冲突处理与材料包快照由后端保存。</dd></div><div><dt>审核记录身份</dt><dd>{DEMO_ACTOR} · 本地操作标识，用于审核留痕；当前不提供登录认证或权限隔离。</dd></div><div><dt>申报指标</dt><dd>准确率、效率提升和预警提前期属于申报目标，尚未实测达标。</dd></div></dl>
    </section>
  </div>
}
