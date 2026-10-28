# UI-X：需求审核工作流

日期：2026-10-22。关联O1、AC-04/07/09/18/20/21的受控交互范围。用户授权将需求清单改为待审核、已确认、已驳回、全部需求四个视图，处理后移出待办，保留数据及审核历史。

## 实际实现

- 默认待审核，包含后台draft与pending_review状态。四个视图数量来自读取到的需求状态，不改变数据库对象身份或通过规则；审核状态与有效性继续分列。
- 确认成功后刷新列表，条目从待审核移到已确认，显示明确成功提示。已处理项不再提供同版本的重复确认/驳回按钮。
- 驳回使用右侧抽屉，原因必填且不能全空白；通过原审核API保存comment、expected_revision、操作身份与决定。取消不提交，同对象本页原因保留，换对象/项目隔离；保存失败保留输入，保存中锁定关闭及重复操作。
- 已确认、已驳回以及新版待审核项可查看只读审核记录。使用已有GET confirmations接口，校验返回结构与对象ID；显示对应版本、意见、操作人及时间，历史版本明确区分，失败可只读重试。
- 已处理项提供修订入口，定位既有修订表单。仅在后台确实生成新版本且返回草稿/待审核时切回待审核；相同内容的无实质修订保留原状态，不伪造重新提交。
- 审核或修订写入成功、后续GET失败时，明确提示已保存并锁定重复写入，只重试列表读取；写入失败则不移动条目。来源/版本、搜索、有效性筛选保留。
- 从材料或变更定位某条需求时以全部视图显示，避免已确认/已驳回记录被默认待办过滤。按项目与定位目标隔离工作区。

本任务未修改后端审核/修订规则、数据库迁移、人工权限或材料门禁。并行FIX-R任务有其他后端/前端修改，其实现与后端验收见独立报告；下列完整前端检查对应执行时共享工作区快照，不将其全部归为UI-X新增能力。未删除或重置日常需求，未替用户审核。

## RED → GREEN → REFACTOR

从frontend执行 `npx vitest run src/panels/RequirementsPanel.test.tsx`：

| 阶段 | 退出码与结果 | 证据 |
| --- | --- | --- |
| RED | 退出1，9失败/5通过；缺少视图/数量、驳回抽屉、审核历史、保存后刷新失败反馈及定位适配 | requirements-red.txt |
| 初次实现 | 14个断言用例通过，但有1个未处理错误，整体退出1，不能计通过；jsdom无scrollIntoView | requirements-green-initial.txt |
| GREEN | 退出0，14通过，无未处理错误；使用输入框focus完成定位，浏览器核验焦点 | requirements-green.txt |

最初构建退出2，新测试ByRoleOptions不支持exact参数；保留build-initial.txt，移除冗余参数，字符串名称仍按默认精确匹配。初次lint有渲染期读ref及effect同步setState两条警告；保留lint-initial.txt，改为事件中捕获焦点回退节点、工作区key隔离定位状态，最终lint无警告。未删除失败断言、增加重试或放宽业务标准。

专项 `npx playwright test --config playwright.cockpit.config.ts requirement-review.spec.ts` 退出0，1通过（review-browser.txt）。真实独立库创建两条合成需求，注入一次503后重试确认，验证驳回必填/取消/保存、无变化仍驳回、实质修订V2重新待审、再次确认、刷新持久化、历史V1原因和V2审核并存；原记录总数不减。finally用版本hash合同恢复隔离库。

## 最终验证

| 命令（frontend） | 结果 | 日志 |
| --- | --- | --- |
| `npm run test:coverage` | 退出0，125通过/22文件 | frontend-full.txt |
| `npm run lint` | 退出0，零警告 | lint.txt |
| `npm run build` | 退出0，TypeScript及Vite成功 | build.txt |
| `$env:ZHIYAN_UIX_SUITE='cockpit'; npx playwright test --config playwright.ui-x.config.ts` | 退出0，18通过 | cockpit.txt |
| `$env:ZHIYAN_UIX_SUITE='review'; npx playwright test --config playwright.ui-x.config.ts` | 退出0，1通过 | walkthrough.txt |
| `$env:ZHIYAN_UIX_SUITE='workspace'; npx playwright test --config playwright.ui-x.config.ts workspace.spec.ts` | 退出0，5通过 | workspace.txt |

浏览器命令同时设置 `$env:ZHIYAN_EVIDENCE_DIR='../docs/test-evidence/2026-10-22/UI-X'`。共24个不同检查，不叠加专项、重跑或日常只读检查；R2仅workspace.spec.ts，未跑整个R2套件。新配置复用原检查集，端口8061/5211、8062/5212、8063/5213及输出目录各自隔离；原脚本仍可独立使用。

TS覆盖：语句86.36%（1830/2119）、分支71.71%（1440/2008）、函数86.92%（605/696）、行90.32%（1521/1684）。排除维持src/main.tsx（启动装配）、src/test/**（测试支持）、测试文件本身，无新增排除。本轮UI-X未运行pytest或重新采集Python覆盖，不把前端覆盖当成Python核心领域覆盖。

### 首次完整浏览器复查中的失败

首次标准cockpit为17通过/1失败，错误是test-results/cockpit下trace/network文件ENOENT，日志cockpit-initial.txt保留。共享工作区存在并行测试，改用本轮独立端口与产物目录复核，18通过；未移除首页断言，未关闭trace。未据此宣称已穷尽定位初始文件缺失的所有原因。

首次review因等待“查看相似项目”超时，walkthrough-initial.txt保留。并行FIX-R已将匹配改为显式计算，走查改为先点“重新计算相似项目”，仍验证相同匹配结果并关闭弹窗；最终1通过。原需求详情、可读性、保存失败等检查显式切到全部视图后验证原记录，没有删掉原断言。后续修改继续以各自报告和统一复核为准。

## 视觉、日常数据与文档

已目视检查rejected-queue-desktop.png和review-history-mobile.png，四视图/计数、处理后动作及历史版本展示可读；浏览器同时验证手机无页面/抽屉横向溢出、取消/关闭返回焦点。其余截图见本目录。

根目录 `node docs/test-evidence/2026-10-22/UI-X/live-check.cjs` 退出0：日常5181默认待审核、全部记录、实际审核历史、关闭焦点正常，无写请求/页面异常（live-check.json）。没有用日常数据演练确认、驳回、修订或恢复。原data/demo.db SHA-256仍为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`；此哈希仅证明原库未变，日常页面无写结论另见脚本记录。

使用指南、老师说明、README、验收、任务、开发日志及决策同步。启动仍为根目录Start-Demo.cmd；已运行的5181刷新即可。本次是需求审核交互与所列回归的检查点，不签全部P0/AC、真实认证或生产混沌。其他agent仍有进行中的工作，待其完成后再统一复核。
