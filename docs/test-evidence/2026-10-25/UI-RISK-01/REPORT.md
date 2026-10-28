# UI-RISK-01 轻量导航与协同预警摘要

关联：本轮用户授权，AC-15/20/21。用户不接受实心深蓝当前阶段，改回浅蓝底、蓝字与边框强调。协同预警首页保留左图及三项指标，右侧展示一个重点议题、来源标识、一条核心发现和两条数值摘要；计数一行，完整原因与记录移入弹窗。

## 实现与边界

- 后端只读聚合附带实际进度、沟通记录、规则条件、样本/参与方信息和来源。核心发现从当前指标运行快照中已触发的计划落后记录取最大值；不新增风险阈值、不修改风险分类、不从消息文本猜测进度。
- 指标失效时headline为null，时延等值仍按原逻辑为空，旧50个百分点不成为当前结论。详情中当前登记的进度与当前可用指标分开呈现，提示补充或重算。
- 前端从后端等级选一个重点议题展示，其他议题保留于“预警详情”。完整标题、所有原因、计划/实际/交付版本、时间及依据、原始沟通记录均可查。标题仅去掉已知展示前缀及合成后缀，原名保留在详情；合成标识来自显式名称或来源，未将rule自动当作合成来源。
- “指标说明”展示窗口、配对样本、参与方、缺席分母和后端实际触发条件；未知不填0，已知无人缺席显示“无”。“查看风险”仍进入完整工作台。
- 弹窗沿用既有Esc/焦点返回、宽幅及内部表格横向滚动，首页右侧不再有内部滚动条。

## RED → GREEN → REFACTOR

前端RED：`npm test -- src/panels/OverviewPanel.test.tsx -t 'keeps the risk overview compact'`，原界面没有核心摘要/弹窗，1项失败，退出1（red-ui.txt）。

后端首轮测试错误地期望进度接口返回200，实际合同为201；该次失败仅为夹具错误，不作为缺失行为证据。修正后，暂不接入新增汇总字段，`python -m pytest backend/tests/test_overview_api.py -k risk_summary --no-cov --basetemp docs/test-evidence/2026-10-25/UI-RISK-01/pytest-red-corrected` 因`KeyError: headline`失败、退出1，见red-api-corrected.txt；随后接入只读聚合。

GREEN：`python -m pytest backend/tests/test_overview_api.py backend/tests/test_coordination_api.py backend/tests/test_progress_domain.py --no-cov --basetemp docs/test-evidence/2026-10-25/UI-RISK-01/pytest-green` 12项通过，退出0。包含真实快照50个百分点/52小时、原始记录、配对分母、只读审计不变，以及上游进度更新后headline与时延失效断言。

前端目标34项通过；`npm run test:coverage` 全量186项/29文件通过，退出0。语句83.90%、分支72.89%、函数81.80%、行90.27%，沿用既有UI门槛，无新增覆盖排除。无前端领域规则，本轮未重跑后端全量及领域覆盖，不把前轮337项或核心覆盖率当作本轮重测。

浏览器：`npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts overview-activity.spec.ts overview-risk.spec.ts` 4项通过；`npx playwright test --config playwright.overview.config.ts initial-showcase.spec.ts overview-stages.spec.ts` 2项通过，均退出0。桌面四尺寸同屏、浅蓝背景及文字对比度、无内部滚动、所有议题保留、完整记录/口径、Esc与焦点返回、手机详情无整页横向溢出、初始完整场景及清空重导入均覆盖。原多议题断言迁移到详情中核查3个议题，没有删除其等级/原因验证；原场景60个百分点进度差仍在详情断言，首页改验证50个百分点计划落后。

重构：拆分OverviewRisk，复用DetailOverlay，局部CSS，Black格式化。`npm run lint`、`npm run build`、`python -m black --check backend/app/overview_services.py backend/tests/test_overview_api.py`退出0。唯一pytest警告是既有Starlette/httpx弃用提示。

## 实际服务

备份至`data/backups/before-ui-risk-20261025.json`，完整回读校验SHA；核对本项目启动器及其API/Vite子进程身份后停止并重新启动同一工作副本，加载新增只读字段。8027/5181运行，业务数据库SHA前后完全相同，见runtime.json。

实际5181：1920与1366首页右侧scroll/client均155/155、142/142；弹窗含3条进度和10条沟通记录，390手机详情无整页横向溢出。写请求0、页面异常0，业务SHA前后一致，见live-browser.json。卡片、浅蓝流程和详情截图已目视检查。未改源协议、审核、风险接受或材料包状态。
