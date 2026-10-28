# UI-F · 紧凑同屏总览

关联 O1–O13 展示，AC-19/20/21；依赖 UX-E。用户要求默认紧凑，将总览尽量放在一个页面，阅读参考 HTML 并借鉴，同时给出后续完善建议。

## 实际完成

- 默认密度改为 compact。显示偏好使用 zhiyan.display.v2；旧 v1 的舒适密度迁移为紧凑，保留减少动效偏好；新版本用户主动保存的选择继续持久化。
- 总览取消成果标签切换和辅助内容折叠。流程、产品、四项真实指标、五条追溯、三智能体、风险依据、知识来源、材料快照及最近动态同屏显示。
- 参考文档/index.html 已完整解析 DOM、阅读脚本，并用本机 Edge 打开截屏；所有 HTTP 请求阻断。借鉴其横向流程、三智能体并排、检测与风险同屏、最近操作。参考原件未编辑；reference-1440.png 为原件渲染证据。
- 图表只用实际已配对响应时长，数量从当前项目 API 读取；未复制示例历史曲线、固定进度/RPN 或“结果存在就通过”等原型判断。
- 修正材料页的附件文案：来源文档实际只导出 TXT 正文，原始样件字节已归档；明确当前没有协议 PDF/DOCX 二进制归档。
- 后续完善建议见 docs/IMPROVEMENT_REVIEW.md，列出依赖传播、原件归档、完整验收和复杂文档解析四项。

## RED / GREEN 与重构

- RED：`cd frontend; npx vitest run src/preferences.test.ts src/panels/OverviewPanel.test.tsx`，退出 1，7 failed/2 passed；默认密度/偏好迁移、三智能体同时出现、真实证据可见等缺失，见 red-behavior.txt。首个从根目录执行的测试因未读取前端配置失败，red.txt 不作行为 RED 证据。
- 初次 GREEN 后两项测试定位错误（article 写成 region、文本同时出现在流程和材料卡），修正为正确语义定位；RTL getByRole 的 exact 选项不合法，构建已发现并移除。业务断言保留。
- 浏览器初次只验证卡片标题在屏内，截图发现表格尾行和按钮被挤压。新增 scrollHeight/clientHeight 检查后真实失败，red-content-fit.txt；调整格子最小高度、局部表格密度优先级、按钮布局和小屏留白，保留失败尝试，最终 browser-final.txt 通过。
- 最终组件测试、lint、构建及 Edge 验证见同目录最终输出；无跳过、删除业务断言、吞错或把截图当作正确性结论。

## 验证范围

- `npx vitest run --coverage`：51 passed，14 文件；语句 87.29%、分支 72.32%、函数 90.07%、行 90.00%。排除 main.tsx 入口装配、src/test/** 和测试文件；前端没有独立领域判定，未把 UI 分支称为核心领域 ≥90%。
- `npm run lint`：最终命令退出 0，既有 Fast Refresh/effect 类警告保留；不宣称零警告。
- `npm run build`：最终通过，资源本地，无新增依赖。
- `npx --offline playwright test --config playwright.cockpit.config.ts`：2 passed；1920×1080、1440×900、1366×768 页面无横向或纵向滚动；五条追溯全部在卡片内，主要区域无内部遮挡；390px 纵向排列，无横向溢出。验证真实入口、偏好持久化、无页面错误、无外网请求、项目列表无变更。
- `npx --offline playwright test --config playwright.single-project.config.ts`：3 passed，独立临时库。
- `npx --offline playwright test --config playwright.review.config.ts`：1 passed，临时备份库，九业务模块走查。
- 后端业务代码未修改，本轮未重复后端覆盖率；UX-E 的 197 项后端通过结果与领域分支 90.04% 是上轮证据，不计作本轮新执行。

## 数据与限制

原演示库 SHA-256 保持 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0；无重置/删除用户项目。预览和浏览器写入只用副本/临时库。默认紧凑改变浏览器显示偏好，不改变业务审核或材料门禁。

一屏适配验证的是默认紧凑、浏览器 100% 缩放、所列桌面尺寸；更小视口、放大字号和手机允许正常纵向滚动，确保内容可读可操作。不承诺任意缩放都强行一屏。当前所有 AC 尚未全量重审；建议优先补齐变型/复用依赖传播及协议二进制原件归档。

访问 http://127.0.0.1:5181/。启动沿用 README 的 8027 后端副本和 5181 前端预览，不改用户日常服务。
