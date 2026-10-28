# PRE-REHEARSAL-03 再次复演前检查

2026-10-26，用户请求再次检查是否有其他问题。范围为最近预填、批量审核、上传恢复及完整演示主线，关联O1–O13和AC-01–21。按计划书与AGENTS先核对基线，只在独立库执行写入；日常项目只读。

## 实际发现并修复

1. DFMEA“仅填空白”的判断只看已保存值，重复预填会将未保存手工评分重置为样例。例如先填8，再手动改9，未保存又点预填会退回8。现在同时核对当前草稿，只补整行完全空白项，已有未保存输入也保留。
2. 样件交付已登记、后续上传失败时，登记区表单和文件选择仍残留，关闭明细后易误重复登记。现在登记成功立即清空登记区及原件选择，待传文件归该条交付明细；首次上传失败后在明细重试，只上传，不重复登记。登记本身失败仍保留输入。

未改后端、审核门槛、协议原件或参考基线，没有用通过状态遮盖上传失败。指南补充这两处恢复行为。

## TDD 与回归

- `npx vitest run src/panels/DesignPanel.test.tsx src/panels/SamplesPanel.test.tsx`：RED退出1，2失败/23通过（red.txt）。评分期望9实际8；登记上传失败后文件列表期望0实际1，均为真实产品行为失败。
- 同命令GREEN退出0，25通过（green.txt），包括原意见/版本、比对、已有评分保存行为；新上传断言验证create只1次、upload失败后重试共2次，未删除或放宽断言。
- `npm run test:coverage -- --maxWorkers=1`：退出0，32文件213通过；语句84.69%、分支73.89%、函数82.39%、行90.73%，frontend-full.txt。沿用main.tsx、测试文件与src/test排除，未增加覆盖排除；不将前端分支称为90%。
- `npm run lint` / `npm run build`：均退出0，lint.txt/build.txt。保留既有537.85kB拆包提示。
- `npx playwright test --config playwright.overview.config.ts`：退出0，10通过（browser-overview.txt）。增强真实浏览器用例：未保存9重复预填不覆盖，首个上传PUT注入503后只重传、原件选择及登记表清空，网络计数1次登记/2次上传，然后提交超差比对；全部在独立临时库。
- `npx playwright test --config playwright.cockpit.config.ts`：31通过/1旧脚本失败（browser-cockpit.txt）。旧requirement-review在空原因点击后仍期待弹窗不关闭，与用户已要求的“原因选填”冲突；随后尝试填写不存在弹窗导致超时。不是产品恢复失败，不回退选填规则。
- 更新该脚本：验证textarea非required、空原因按钮可用；原有填写原因、Esc保留、修订新版本、刷新审核历史和两条审核记录断言不变。旧默认截图目录从历史2026-10-22证据改为test-results/screenshots，复验明确传入本任务目录。
- 最终`npx playwright test --config playwright.cockpit.config.ts requirement-review`退出0，1通过（browser-requirement-final.txt）。因此cockpit的31+1及overview的10，共42个不同浏览器用例均已通过，不重复累计。无独立重构阶段；GREEN后扩大检查由本次用户明确复核要求和两处复现缺陷决定，检查通过后未无故重复全量。

## 完整独立排练

`python -X utf8 scripts/rehearse_demo.py --output-dir docs/test-evidence/2026-10-26/PRE-REHEARSAL-03/rehearsal`退出0，rehearsal.txt及rehearsal/rehearsal-report.json。它只新建独立SQLite库。

实际结果：Word/PDF各19条；需求审核、型谱/零件/工程版本、评审/DFMEA、试验/样件、两引擎、冲突闭环、材料包达到human_approved及ZIP校验通过；2600→2800覆盖序列80→60→80→100，旧执行保留；冻结导出后变更不改变旧ZIP；备份清空后PDF重新导入的需求稳定ID与旧批次不相交。原综合协议用于该完整变更排练，流程演示版19条/0澄清另由本轮浏览器实测。

本轮没有后端改动，没有重跑356后端全量或冒用上轮结果；本次后端验证是上述真实API完整排练。不是所有生产场景、任意协议识别或申报指标达标的证明。

## 实际项目只读检查

`node docs/test-evidence/2026-10-26/PRE-REHEARSAL-03/live-audit.cjs`退出0。实际5181的11个模块全部加载，数据库连接018，模块错误提示0、页面JS错误0、5xx响应0、业务写请求0。桌面1440和390px首页/样件页无页面横向溢出。证据live-audit.json、live-1至11及移动截图。

检查前后业务SHA为`ddbada5a540635de3999ede1584e4e3aff5eb13126f39a8de35908a980915272`。没有清空、恢复、审批或重启用户日常项目；纯前端由Vite加载更新，刷新可继续。独立测试库中的备份恢复和审批不影响日常库。新增源代码只有两处已复现界面恢复修复，其他业务沿用原实现。
