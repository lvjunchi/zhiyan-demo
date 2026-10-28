# UI-IMPORT-GROUP-01 导入概况、文档与分布合并

2026-10-25；本轮用户指定“概况在上、文档列表居中、下方状态分布图与文件处理记录”，关联会议12/13、AC-20。

## 结果

DocumentImportStatus默认完整视图采用一张外层卡片，顺序为概况→文档列表→分布图→待核对/失败记录。ParsingPanel只渲染一次，不再将两块隔着上传表单展示。保留刷新、原件下载、结果弹窗与关闭返回焦点、继续解析、继续/取消核对；沿用图表样式、配色和桌面左右布局，小屏依旧上下排图。处理记录仍在需要时显示并可折叠，不隐藏已有待核对操作。

无后端、数据模型、统计口径或审核规则改动，无依赖变更，无服务重启。已恢复的初始展示数据未改。

## RED / GREEN 与验证

- RED：在已有Stage03结果弹窗回归中，将查看入口限定在同一“文档导入统计”区域。`npm test -- src/panels/Stage03.test.tsx`实现前1失败/5通过、退出1，原因是原文档操作按钮在另一张卡片，见red.txt；没有移除原结果弹窗及返回焦点断言。
- GREEN：`npm test -- src/panels/Stage03.test.tsx src/panels/ImportDistribution.test.tsx src/panels/ImportResume.test.tsx src/panels/ParsingPanel.test.tsx`：4文件20通过、退出0。
- `npx playwright test --config playwright.overview.config.ts import-resume.spec.ts stage03.spec.ts overview-stages.spec.ts`：5不同用例通过、退出0；独立测试库覆盖草稿跨页/刷新/重选原件、取消/清空、实际Word导入与审核分离、失败记录和未知空态。
- `npm run lint`、`npm run build`退出0，103模块，JS522.99kB，Vite默认体积提醒保留。
- 当前5181页面只读检查：概况/文档/分布属于同一区域，实际y顺序正确；桌面2列图、小屏1列图，390px无页面横向溢出，0业务写请求、0页面错误。桌面及小屏截图已目检，见live-layout.json、import-management.png、import-management-mobile.png。
- 首次只读核查脚本无条件点击已展开的导航，导致折叠后等待超时；修正为仅在未展开时点击，最终检查通过，见live-layout-final.txt。这是核查脚本问题，没有更改产品导航逻辑或放宽页面断言。
- 日常数据库前后SHA一致，见data-preserved.json。未执行全量后端、全量前端覆盖或其余浏览器套件，不把历史全量数量作为本次结果。

首次命令误以frontend为工作目录创建空证据目录，导致重定向目标不存在，npm并未执行，不能计为RED。正确目录建立后才得到上述真实RED。空目录清理命令被工具策略拒绝，未继续尝试删除；不影响代码、数据或正确位置的证据。所有有效证据均在本报告所在目录。
