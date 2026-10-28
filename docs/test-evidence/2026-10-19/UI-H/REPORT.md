# UI-H · 侧栏重排与可读字号（2026-10-19）

任务关联：O1–O13 展示、AC-20/21；依赖 UI-G。用户指出侧栏字号变小、内部滚动条不美观，要求重新设计及全界面字体适配。

## 变更与验收

- 新增共享 readability.css，统一总览与业务页侧栏宽度和字号，消除切换时字体/宽度跳变。桌面菜单 14px、大屏 15px，分组 12px、品牌 26px；项目简介在较矮屏收起，缩减分组留白；720px 高度进一步缩行距，不缩文字。
- 表格正文/稳定编号 13px、大屏正文 14px，输入框 14px，主要状态/辅助信息 12px，业务分区标题 17px。总览主标题/分区/正文也同步增大，核心表格 11px，细节工作区可继续查看完整信息。
- 总览重新分配各行高度和上下留白，保持 1920×1080、1440×900、1366×768 主要内容同屏；产品参数、5 条追溯、三智能体按钮和底部材料完整可见。
- 导航在上述三种桌面及 1280×720 均 scrollHeight <= clientHeight+1；全部 11 项不截断、在屏内；舒适/紧凑切换不引入菜单溢出。390×844 可横向导航切换，正文可读，页面无横向溢出。
- 业务规则、后端、参考资料均未改。超短视口/高倍缩放仍保留可访问滚动兜底；1280×720 总览可正常纵向阅读，不承诺其全部内容一屏。

## RED → GREEN → REFACTOR 与命令

1. RED：frontend 执行 `npx --offline playwright test --config playwright.cockpit.config.ts readability.spec.ts`，退出 1，2 failed。菜单实测 12px < 14px，手机表格 11px < 13px；red-readability.txt。
2. 实现后回归发现旧总览高度公式导致大屏底部多 3px、1440 表格/卡片局部挤压；新增逐智能体、材料包内部高度与产品参数完整性断言。按失败调整留白/网格，未降低字号断言或移除遮挡检查。新测试最初误用可见 label“新数值”，实际 aria-label 为“修订后的数值”，已修正定位并保留诊断 browser-green.txt。
3. 1280×720 增补检查发现菜单多 35px，紧凑密度的旧选择器覆盖了缩行距规则；提高对应导航规则优先级后通过，文字保持 14px。
4. GREEN/最终：`npx --offline playwright test --config playwright.cockpit.config.ts`，退出 0，6 passed；browser-final.txt。涵盖总览/设置/真实备份恢复/故障反馈/新字号与侧栏/移动端。
5. `npx --offline playwright test --config playwright.review.config.ts`，退出 0，1 passed，九模块走查；modules-review.txt。后续只调整低视口卡片 padding，最终 cockpit 含该布局验证。
6. `npx vitest run --coverage`，退出 0，55 passed/17 文件；frontend-tests.txt。`npm run lint` 退出 0，24 条已有类别警告；lint.txt。`npm run build` 最终退出 0；build.txt。字体调整后不再增加实现镜像单测，浏览器直接断言真实字号/几何范围。

TS 覆盖率：语句 84.31%、分支 71.91%、函数 87.61%、行 88.03%；排除 main.tsx 装配入口、src/test/** 和测试文件。本轮无领域判定变化，不把 UI 分支当作核心领域分支。不重跑未变动的后端，212 后端通过仅为 UI-G 历史基线，不冒称本轮结果。

## 证据与限制

最终截图 dashboard-1920/1440/1366.png、项目总览/需求清单-各宽度.png、mobile-settings.png、demo-*.png。最初一次沿用旧测试路径重渲染了 UI-G 的设置/模块图片，随后统一更正测试截图目录为 UI-H，历史文本报告未修改；本轮权威证据以此目录为准。

所有浏览器写操作位于临时预览库；原 data/demo.db SHA-256 仍为 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。未重置用户数据、未接外网或改参考文档。完整验收阻塞仍以 docs/ACCEPTANCE_REVIEW.md 为准，本轮没有关闭协议原件归档/独立版本模型缺口。

预览 http://127.0.0.1:5181/，已运行服务通过 Vite 更新样式；启动仍按 README 的临时副本方式。截图与字号验收按默认 100% 浏览器缩放，其他缩放允许滚动，不隐藏菜单功能。
