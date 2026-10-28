# UI-Q 三处详情交互优化

日期：2026-10-21。顺序：UI-Q1 需求来源/版本 → UI-Q2 冲突处置 → UI-Q3 样件比对。关联 O1/O12、一致性引擎，AC-04/13/14/18/19/20/21 的受控交互范围。

## 结果

- 需求清单“来源 / 版本”：右侧抽屉，保留来源文档、原文/下载、版本选择与字段差异；失败可重试，关闭回原按钮，搜索筛选不丢失。
- 一致性检测“关闭冲突”：右侧抽屉集中显示证据、对象版本、复检/审核及处置表单。关闭面板不关闭冲突；失败意见/证据保留，成功更新原行并回到该行焦点。保存仍发送真实 expected_revision、处置与审计证据。
- 样件检验“查看 / 比对”：宽幅弹窗，保留文件上传、图纸参数、单位、实测、后端结论/原因、比对确认。非404读取错误显示重试，不伪作无记录；同一样件的页面草稿保留，不同样件和项目隔离。目视检查数值栏“不适用”，实际数值缺测仍“缺失”。窄屏表格可横向滑动并提示，保持字列可读。
- 三者共享本地原生 DetailOverlay 模态基础，后台不可操作、正文独立滚动、键盘循环、Esc、保存中保留上下文、关闭恢复焦点；已有工程决策弹窗复用该基础。没有新依赖、外部服务、后端/数据库规则改动。

## RED → GREEN → REFACTOR

命令在 frontend 下执行（根目录的 npx --prefix frontend … --root frontend 等价）；退出码均记录于执行结果。

| ID | RED（退出1） | GREEN（退出0） |
| --- | --- | --- |
| UI-Q1 | npx vitest run src/panels/RequirementsPanel.test.tsx：2 failed/5 passed，找不到抽屉 dialog | 连同 EngineeringRecords.test.tsx：11 passed；浏览器需求抽屉1 passed |
| UI-Q2 | npx vitest run src/panels/ConsistencyPanel.test.tsx：3 failed/5 passed，缺少抽屉与原行焦点恢复 | 8 passed；浏览器真实处置1 passed |
| UI-Q3 | npx vitest run src/panels/SamplesPanel.test.tsx：3 failed/5 passed，缺少宽弹窗/重试 | 8 passed；浏览器上传→实测→比对→确认→换样件1 passed |
| 展示补强 | 相同样件命令：1 failed/8 passed，目视项仍被显示为缺失数值 | 最终前端全量93 passed |

原始 red-*.txt、green-*.txt 及 browser-requirements/conflicts/samples.txt 可复查。Q1 辅助 fetch 参数数量断言不正确，修正为检查 GET/无 method；不把该辅助断言失败称为行为 RED。Q2 首次浏览器夹具无开放冲突，改为在独立库先实际修订发动机需求再检测，未降低断言。Q3 首次浏览器 locator 命中数值与目视两条“通过”，限定内孔直径行；browser-samples-first.txt 保留失败。另修正 RTL cell 断言的多余 exact 选项（TypeScript报错）。

REFACTOR：手机宽表/提示、目视空值、证据样式和共享模态复核后，前端全量、build/lint、四项 details/version-dialog 浏览器再跑通过；重复检查不累计为新测试。仅 jsdom 替身 showModal/close 的 open 属性；真实 top-layer、键盘与布局由 Edge 检查。

## 最终验证

- `npm run test:coverage`：22文件，**93 passed**；frontend-full.txt。TS语句83.60%（1550/1854），分支67.16%（1125/1675），函数84.49%，行87.90%；既有门禁通过，无新增覆盖排除。main.tsx仅启动装配、src/test/**仅支持、*.test.ts/tsx仅测试本身继续排除。
- `npm run build`、`npm run lint`：均退出0，lint无警告；build.txt、lint.txt。
- `npx playwright test --config playwright.cockpit.config.ts`：**12 passed**；cockpit-full.txt。三项新详情、原工程弹窗、原件归档/版本审核、备份恢复、断连/保存错误、三桌面同屏、手机及模块业务标题。
- `npx playwright test --config playwright.review.config.ts`：**1 passed**；walkthrough.txt，贯穿九模块展示。原流程仅增加关闭新弹窗动作，保留原断言。
- `npx playwright test --config playwright.cockpit.config.ts details.spec.ts version-dialog.spec.ts`：4 passed（上述12项中的子集）；browser-refactor.txt。
- 合计 **13个不同浏览器检查**；所有数据库写入仅在独立临时库/端口，未复用日常服务。后端没有修改，本轮未重新执行pytest或采集Python覆盖率；旧256/核心90.50%不是本轮结果。

## 截图与日常数据

requirement-drawer-desktop/mobile.png、conflict-drawer-desktop/mobile.png、sample-comparison-desktop/mobile.png 已目视复查。日常只读复现：`node docs/test-evidence/2026-10-21/UI-Q/live-check.cjs`，退出0，live-result.json确认无异常、外网或写请求；live-requirement-drawer.png、live-sample-comparison.png。日常无开放冲突不人为创建，只在独立库验证。

source-hash.json：data/demo.db仍为edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。未重置日常保存状态、修改参考原件、连接生产或部署。关闭保留的草稿仅在当前页面内，刷新/离开模块不承诺持久化未提交表单。

启动仍为根目录Start-Demo.cmd，刷新http://127.0.0.1:5181/可见。当前工作限于上述三处交互，不签署完整P0/AC、任意输入泛化或长期混沌可靠性。
