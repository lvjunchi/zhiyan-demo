# UI-Z1 平台品牌与分组导航

## 范围与最终行为

本轮仅执行会议第4/5/6/14项，关联AC-19/20/21受控界面范围；其他会议任务未启动。

- 顶部完整名称“复杂高端装备智能定制与自主验证平台”，保留侧栏智研引擎品牌；标题与面包屑两层，保留备份/恢复入口。首页沿用原一屏布局。
- 新增本地SVG重型卡车示意，作为左下角工业风格图形，不作为工程证据；不依赖联网资源。
- 四个侧栏分组使用可展开按钮、aria-expanded/controls、原生键盘Enter/Space；默认需求解析组展开，其他收起，每次展开一个。隐藏项保留稳定tab/panel ID。手动收起不切换当前页面、不发业务写请求；总览/下一步/材料定位等页面跳转统一展开目标组。评审材料和系统设置独立入口保持。
- 子模块顶部以当前工作与指标/说明、下一步操作两个区域展示，强化字号/色彩和按钮，仍用已有真实workspace API；不新增通过规则、不自动审核。手机上下排列，桌面并列；缺数据和失败重试保留。
- 新增shell.css、TruckMark，App导航状态与WorkspaceJourney结构局部修改；浏览器测试通过共享openWorkspaceTab真实点击分组再进模块，不使用force或隐藏元素点击绕过界面。

## TDD与检查

1. RED：`npx vitest run src/App.test.tsx src/components/WorkspaceJourney.test.tsx`，退出1，3失败/20通过；缺平台全称/分组按钮/下一步region，原始red.txt保留。
2. GREEN同命令退出0，23通过，green-initial.txt；完成共享样式及排版调整后REFACTOR同命令，refactor.txt。语义断言保留键盘、分组不切业务页、总览动作展开目标、指标和下一步跳转。
3. `npm run test:coverage`退出0，22文件138通过，frontend-coverage.txt。TS语句85.93%（1918/2232）、分支72.97%（1604/2198）、函数87.34%、行90.89%；main.tsx、src/test/**、测试本身既有排除不变。无后端逻辑改动，Python测试/覆盖率本轮未重跑，不借用旧结果作本轮全量验收。
4. 初次build退出2：新增RTL断言误用了仅Playwright支持的exact选项；去掉该类型错误，保留字符串精确匹配，build-final.txt退出0。最终根目录 `python scripts/check_demo.py --only lint build browser-fixes browser-change --evidence-dir docs/test-evidence/2026-10-22/UI-Z1/final-check`退出0，lint零警告、构建成功、fixes4与change1通过；只选定四项，不宣称跑过全检查。
5. 初次专项platform-shell3通过。随后完整cockpit22检查：21通过/1手机超时，browser-final.txt保留。读取trace确认main.tsx请求net::ERR_NO_BUFFER_SPACE，未加载应用；停止并行浏览器任务后，保持同一产品实现与断言，单独重跑narrow screens退出0，1通过，mobile-recheck.txt。没有添加自动重试或放宽超时。原始trace在测试框架复用输出目录后未归档，诊断摘录另记failure-diagnosis.txt。
6. R2 workspace.spec.ts5通过（仅该文件，非全R2）；review完整浏览器走查1通过。合计33个不同浏览器检查：cockpit22 + fixes4 + change1 + workspace5 + review1，不叠加首次专项和重跑。命令、退出码见对应txt和final-check/原始日志。测试后端均用临时工作库，无日常恢复/重置。
7. 1920/1440/1366/1280桌面及390手机截图已目视检查，标题不挤压工具栏、桌面侧栏无需滚动、主页1920/1440/1366一屏；工作上下文仍满足原桌面紧凑检查。截图在browser-final/、mobile-recheck/、workspace/等目录。

## 日常工作区与文档

`node docs/test-evidence/2026-10-22/UI-Z1/live-check.cjs`退出0，11页只读，无页面异常/模块报错/外网/业务写请求。期间用户已自行重新导入；检查时需求13、来源文档1，不是空库。日常库走查前后hash均为707a983dc73077c88324d3fd67574fe276da29aadfc0510b2afa2173745dcaef；没有清空、代导入、代审核或回退其进度。source demo.db仍为edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。

README、DEMO_GUIDE、老师说明、任务表/日志/决策同步；将此前“当前为空”的静态文字改为历史清空记录，当前进度以系统为准。启动仍为Start-Demo.cmd，本次仅前端，当前5181刷新可见。尚未开发系统设置清空按钮、总览内容扩展、导入进度和其他会议功能。


维护注：UI-Z2最初只读走查误复用了本目录live-check.cjs输出位置，live-check.json和live-*.png更新为UI-Z2界面检查时状态；该次结果已复制至UI-Z2，后续使用独立目录。原UI-Z1浏览器截图在browser-final/、mobile-recheck/等目录仍保留，UI-Z1原测试结论不变。
