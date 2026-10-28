export type TabKey =
  | 'overview'
  | 'requirements'
  | 'parsing'
  | 'bases'
  | 'design'
  | 'testing'
  | 'samples'
  | 'consistency'
  | 'coordination'
  | 'packages'
  | 'settings'

export type ModuleTabKey = Exclude<TabKey, 'overview' | 'settings'>
export interface NavigationFocus { objectId?: string; revision?: number; message: string; origin?: 'change'; returnTab?: ModuleTabKey }
export type NavigateTo = (tab: TabKey, focus?: NavigationFocus) => void

export type IconName =
  | 'settings'
  | 'overview'
  | 'requirements'
  | 'parsing'
  | 'bases'
  | 'design'
  | 'testing'
  | 'samples'
  | 'consistency'
  | 'coordination'
  | 'packages'
  | 'alert'
  | 'check'
  | 'arrow'
  | 'download'
  | 'clock'

export interface ModuleTab {
  key: ModuleTabKey
  label: string
  description: string
  icon: IconName
}

export const TAB_GROUPS: {
  title: string
  hint: string
  standalone?: boolean
  tabs: ModuleTab[]
}[] = [
  {
    title: '需求解析智能体',
    hint: '协议 → 结构化需求',
    tabs: [
      {
        key: 'parsing',
        label: '协议解析与澄清',
        description: '来源文档、A–I 字段、问题闭环',
        icon: 'parsing',
      },
      {
        key: 'requirements',
        label: '需求清单',
        description: '结构化需求、版本与审核状态',
        icon: 'requirements',
      },
      {
        key: 'bases',
        label: '型谱选型与变型',
        description: '型谱 Top-3、变型点、可复用件',
        icon: 'bases',
      },
    ],
  },
  {
    title: '变型设计智能体',
    hint: '相似项目 → 设计草案',
    tabs: [
      {
        key: 'design',
        label: '设计成果',
        description: '相似项目、评审清单、DFMEA',
        icon: 'design',
      },
    ],
  },
  {
    title: '试验验证智能体',
    hint: '方案 → 用例 → 样件',
    tabs: [
      {
        key: 'testing',
        label: '试验验证与追溯',
        description: '试验方案、用例、追溯矩阵',
        icon: 'testing',
      },
      {
        key: 'samples',
        label: '样件检验',
        description: '样件交付、图纸参数与比对',
        icon: 'samples',
      },
    ],
  },
  {
    title: '贯穿引擎',
    hint: '一致性 · 协同风险',
    tabs: [
      {
        key: 'consistency',
        label: '一致性检测',
        description: '参数、版本、引用与工况冲突',
        icon: 'consistency',
      },
      {
        key: 'coordination',
        label: '协同风险',
        description: '响应时延、议题反复、缺席率',
        icon: 'coordination',
      },
    ],
  },
  {
    title: '评审交付',
    hint: '成果汇编与快照冻结',
    standalone: true,
    tabs: [{ key: 'packages', label: '评审材料', description: '门禁材料包、快照与 ZIP 导出', icon: 'packages' }],
  },
]

export const MODULE_TABS: ModuleTab[] = TAB_GROUPS.flatMap(
  (group) => group.tabs,
)

/** Navigation suggestion only; approval and gate rules remain on the backend. */
export function nextModule(tab: ModuleTabKey): ModuleTabKey | undefined {
  return MODULE_TABS[MODULE_TABS.findIndex(item => item.key === tab) + 1]?.key
}

export const TAB_LABELS: Record<TabKey, string> = {
  overview: '项目总览',
  settings: '系统设置',
  ...Object.fromEntries(
    MODULE_TABS.map((tab) => [tab.key, tab.label]),
  ),
} as Record<TabKey, string>

export const TAB_DESCRIPTIONS: Record<TabKey, string> = {
  overview: '项目关键指标、主线进度与门禁状态',
  settings: '界面偏好、本地运行状态与系统能力配置',
  ...Object.fromEntries(
    MODULE_TABS.map((tab) => [tab.key, tab.description]),
  ),
} as Record<TabKey, string>

export const TAB_GROUP_TITLES: Record<TabKey, string> = {
  overview: '工作台',
  settings: '系统管理',
  ...Object.fromEntries(
    TAB_GROUPS.flatMap((group) =>
      group.tabs.map((tab) => [tab.key, group.title]),
    ),
  ),
} as Record<TabKey, string>
