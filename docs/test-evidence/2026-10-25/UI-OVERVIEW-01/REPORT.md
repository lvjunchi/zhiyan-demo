# UI-OVERVIEW-01 智能体卡片留白与按钮布局

2026-10-25；用户截图问题，AC-20/21受控布局。通过澄清确认用户所指是卡片中间留白和操作入口不协调，而非审核/澄清数量。本轮不修改任何统计口径、业务规则或持久数据。

## 原因与修改

总览中间行按1.05fr分配多余窗口高度，三卡拉伸；操作区margin-top:auto贴底，大屏留下过多空档。品牌布局另有相同选择器覆盖，早先总览样式不是最终生效规则。两个入口原宽度1.2:1、按钮/文字链接高度不同。

在最终品牌布局设置中间行分档高度：普通桌面236px、宽屏268px、矮屏195px，保留风险图所需空间；卡内数据区居中，操作区使用固定小间距。两个入口等宽/等高/同基线，统一边框和焦点样式，主次背景不同。矮屏采用28px按钮及更小间隔，保持字号和首页同屏。导入前介绍区由独立规则控制，没有更改业务内容。

## 真实验证

- RED：增强既有homepage浏览器检查，保留原先同屏、无裁切、图表、导航及数据断言，增加可见最后一条数据至操作区间隔≤28px、两个入口等宽/等高/对齐且至少28px；增加2560×1440。初次命令`npx playwright test --config playwright.cockpit.config.ts e2e-cockpit/homepage.spec.ts --grep 'complete project dashboard'`退出1，实际间隔200.640625px，见red.txt。
- 首轮修改因后续品牌样式覆盖仍失败（green.txt）；之后风险区域最小高度、1440追溯表空间及1366卡片高度真实检出问题，见green2—5.txt。未移除这些原有断言；修正最终生效规则与分档尺寸后通过。测量改为最后一项可见数据的边界，避免flex数据容器长大后掩盖实际留白。
- GREEN：`npx playwright test --config playwright.cockpit.config.ts e2e-cockpit/homepage.spec.ts e2e-cockpit/readability.spec.ts`退出0，4项通过（36.2秒），覆盖2560/1920/1440/1366首页、1280跨模块、390手机、风险图/追溯/内容无裁切及操作跳转。见green6.txt；dashboard-1920.png与1366.png已目视核查。
- `npx playwright test --config playwright.overview.config.ts e2e-overview/overview-stages.spec.ts`退出0，1项通过；空白四宽度介绍与Word实际导入后看板切换正常，见overview-states.txt。
- `npx vitest run src/panels/OverviewPanel.test.tsx`退出0，28项通过；`npm run lint`和`npm run build`均退出0。没有新增领域行为或重跑后端331/完整前端180/覆盖，不能借用旧计数宣称本次全量。

所有浏览器服务与Word导入采用独立测试库；日常服务仅GET health读到018，未发业务写请求。无额外重构，未编造REFACTOR重跑。截图和原始失败日志保留。
