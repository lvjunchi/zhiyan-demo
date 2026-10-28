import { ProductImage } from '../components/ProductImage'
import { PartIllustration } from '../components/PartIllustration'
import { Icon } from '../components/Icon'
import type { TabKey } from '../navigation'
import type { ProjectOverview } from '../types'

export function OverviewIntroduction({ data, onNavigate }: { data: ProjectOverview; onNavigate: (tab: TabKey) => void }) {
  const resources = data.cockpit?.resources
  return <div className="overview-introduction">
    <section className="intro-hero" aria-label="项目启动介绍">
      <div className="intro-copy"><span className="intro-eyebrow">重型商用车 · 定制研发</span><h2>{data.project.name}</h2><p>{data.project.customer} / {data.project.product}</p><h3>让技术协议贯通研制全过程</h3><p>以需求为起点，关联选型与变型设计、试验验证和评审材料。保留每次修订的来源、版本与确认记录。</p><div className="intro-start"><span><i />尚未导入技术协议</span><button type="button" onClick={() => onNavigate('parsing')}>开始导入技术协议<Icon name="arrow" size={17} /></button></div><small>导入并解析后，首页将切换为当前项目的业务看板。</small></div>
      <section className="intro-gallery" aria-label="产品与零件展示"><div className="intro-product"><ProductImage /><span>重型变速器 · 产品参考</span></div><div className="intro-parts">{(['housing', 'shaft', 'gears'] as const).map((kind, i) => <figure key={kind}><PartIllustration kind={kind} /><figcaption>{['主箱壳体', '传动轴', '齿轮组'][i]}</figcaption></figure>)}</div><small>零件为结构示意，不代表当前项目设计结果</small></section>
    </section>
    <section className="intro-capabilities" aria-label="三智能体介绍"><header><h3>三智能体协同研制</h3><span>需求驱动 · 工程师确认 · 证据可追溯</span></header><div>{([
      ['parsing', '需求解析智能体', '将协议原文转为可审核的工程需求', '来源定位 / 条款澄清 / 需求确认'],
      ['bases', '变型设计智能体', '从受控候选识别基型差异与复用机会', '基型选型 / 零件决策 / 设计评审'],
      ['testing', '试验验证智能体', '关联验证要求、试验用例与执行证据', '方案用例 / 样件比对 / 评审材料'],
    ] as const).map(([icon, title, text, detail]) => <article key={title}><Icon name={icon} size={24} /><div><h3>{title}</h3><p>{text}</p><small>{detail}</small></div></article>)}</div></section>
    <div className="intro-foundation"><section className="intro-engines" aria-label="两引擎介绍"><h3>两引擎贯穿全流程</h3><div><article><Icon name="consistency" size={23} /><div><h3>一致性检测</h3><p>核对参数、版本、引用与工况，保留冲突证据和处置记录。</p></div></article><article><Icon name="alert" size={23} /><div><h3>协同风险预警</h3><p>依据沟通时间戳、议题反复及参与情况计算风险；数据不足时明确提示。</p></div></article></div></section>
      <section className="intro-resources" aria-label="基础库概况"><h3>工程知识底座</h3><div><button type="button" onClick={() => onNavigate('bases')}><Icon name="bases" /><strong>{resources ? `${resources.product_bases} 款` : '—'}</strong><span>受控产品型谱</span></button><button type="button" onClick={() => onNavigate('design')}><Icon name="overview" /><strong>{resources ? `${resources.history_projects} 个` : '—'}</strong><span>合成历史项目</span></button><button type="button" onClick={() => onNavigate('consistency')}><Icon name="consistency" /><strong>可追溯</strong><span>参数 / 版本 / 工况规则</span></button></div><small>基础库数量来自本地库；初始介绍不计入项目完成状态。</small></section></div>
  </div>
}
