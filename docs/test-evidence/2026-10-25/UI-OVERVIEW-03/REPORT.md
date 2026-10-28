# UI-OVERVIEW-03 状态、知识底座与流程层次

任务：用户三张截图，关联 AC-20/21。本次仅前端布局、字号和颜色，未修改领域规则、统计来源、数据库或后端服务。

- 需求卡片将待澄清加入同一行第五项统计，删除单独的底部文字行。数字使用与其他审核统计一致的层次，0项绿色、有待办用琥珀色，保留协议澄清入口和真实数量。
- 工程知识区桌面列权重1.1→1.35，实际1920屏宽度约652→720px；图标20→32px，矮屏28px，名称12—13px、数量16—18px。矮屏用图标在左、文字在右排布，手机两列。规则关键词整体换行，避免拆开词语。
- 流程导航整体文字、图标和边框加深，当前阶段使用深蓝底和白字；仍仅由原定位函数设置 aria-current，不把已有产物表现为已审核通过。

## 验证

RED：`npm test -- src/panels/OverviewPanel.test.tsx -t 'keeps clarification counts'` 退出1，原状态组缺少“待澄清2”。`npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts -g 'complete project dashboard'` 退出1，原状态组只有4项。原始日志 red-component.txt/red-browser.txt。

GREEN：组件文件31项通过、退出0。浏览器 `homepage.spec.ts readability.spec.ts overview-trace.spec.ts` 5项通过，退出0；覆盖2560/1920/1440/1366桌面、1280导航/正文和390手机；五项统计同排不裁切、图标≥28px、知识名称≥12px、当前流程文字对比度≥4.5、原同屏/按钮间距/追溯弹窗断言保持。空白→Word导入状态另1项通过，退出0。见 component-green.txt/browser-final.txt/empty-import-states.txt。

初轮出现2560卡片间距17.66px超16px，及900高屏知识图块撑高导致整页滚动。已调整数字行层次与1000高以下紧凑排布，并修正图标容器旧padding压缩SVG的问题；失败日志保留，原断言未放宽。最后规则关键词按整词换行后再次运行原首页同屏检查，结果见 keyword-wrap.txt。

`npm run lint`、`npm run build` 均退出0。无额外领域/版本逻辑修改，因此本轮未重跑后端337项及覆盖率；前轮覆盖报告仍为历史证据，未宣称本轮重测。没有新增覆盖排除。

## 实际页面

5181实际只读检查：1920/1440/1366均同屏、图标32/28/28px，390无整页横向溢出；卡片、知识区与流程截图已目视。前后业务SHA相同，写请求0、页面异常0，见live-final.json与live-*.png。无需重启数据服务，刷新页面即可查看。未清空或修改现有业务数据。
