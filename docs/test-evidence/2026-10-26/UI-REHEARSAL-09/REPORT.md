# UI-REHEARSAL-09 操作主次与协同布局

2026-10-26；本轮4项反馈，O1/O10、协同、AC-07/09/11/13/15/20。仅本地前端布局/标记/样式与测试文档，无后端、协议原件、迁移或判定规则变化。

## 实际变更

1. 需求批量弹窗改为左侧深蓝“确认本批次需求”、右侧浅色“取消批量确认”，不改变核对声明、预览门槛或原子提交。旧弹窗CSS按:first-child自动染蓝，导致原先取消突出；本次重排并为这组操作显式设置主次，未全局覆盖其他弹窗。
2. 试验“最近执行”增加图标和结果色标：绿色“已执行·通过”、红色“已执行·未通过”，证据不足/无效为琥珀，未执行为灰色虚线；旧版本或stale下的执行为灰色“历史执行”，保留原结果文本。执行次数、绑定版本、模式及原因继续显示，不改当前覆盖/通过计数和后端结果。
3. “登记参与方进度”使用深蓝按钮、加号和更明显的尺寸，仍位于进度区标题右侧；读取/保存状态的禁用条件保留。
4. 将沟通导入/查看从预警及风险接受区之后移至议题标题/参与方信息下方，集中在“沟通记录”操作条。其后为进度登记和表格、预警、指标/风险处置、工时与重算。入口只有一组，不重复，功能和草稿保持不变；窄屏自然换行。

## TDD 与验证

命令工作目录为 `D:/Pythontest/zhiyan-demo/frontend`。原始输出在本目录，各轮数量不叠加。

| 阶段 | 命令/输出 | 结果 |
| --- | --- | --- |
| RED | `npm test -- --maxWorkers=2 src/panels/Stage04.test.tsx src/panels/CoordinationPanel.test.tsx`，RED.txt | exit1；2失败14通过，分别因确认仍在取消之后、沟通入口尚无位于进度之前的操作组。实现前执行 |
| GREEN | 上述再加TestingPanel.test.tsx和WorkflowOverview.test.tsx，GREEN.txt | exit0；4文件27通过，原确认/取消/版本/执行/进度保存断言保留 |
| 全量覆盖 | `npm run test:coverage -- --maxWorkers=2`，COVERAGE.txt | exit0；36文件229通过，语句85.03%(3159/3715)、分支74.89%(2896/3867)、函数82.65%(977/1182)、行91.23%(2310/2532) |
| 浏览器执行/协同 | `npx playwright test --config playwright.cockpit.config.ts execution-feedback.spec.ts`，PLAYWRIGHT-COCKPIT.txt | exit0；2通过，验证真实通过/失败色标、点击入口不写执行、2.4真实判fail、沟通操作组在进度前、进度按钮实际蓝色、390px无页面溢出及原消息关联 |
| 浏览器批量/完整流程首轮 | `npx playwright test --config playwright.overview.config.ts stage04.spec.ts demo-usability.spec.ts`，PLAYWRIGHT-OVERVIEW.txt | exit1；1通过1失败。完整流程通过；旧stage04单独运行依赖其他测试先准备需求，本轮隔离库为空导致选择数0，不是UI动作失败 |
| 浏览器批量复验 | `npx playwright test --config playwright.overview.config.ts stage04.spec.ts`，PLAYWRIGHT-OVERVIEW-RECHECK.txt | exit0；1通过。旧用例增加隔离库内明确清空/导入两参数协议夹具及finally恢复，不删数量/审核/修订断言。验证确认左、取消右及蓝/浅实际计算色，390px按钮顺序、弹窗无横向溢出，取消不写与逐项审核记录继续通过 |
| 静态/构建 | `npm run lint`、`npm run build`，LINT.txt、BUILD.txt | 均exit0；lint无警告，构建保留既有>500kB提示，主块549.18kB |

本轮不同浏览器用例共4项已通过；复验为重复用例，不叠加。浏览器均配置自建隔离临时库，stage04清空/恢复仅作用于8075测试服务。无单独结构重构阶段，无skip/降低断言/改超时；覆盖排除沿用vite.config.ts的启动入口src/main.tsx、测试夹具src/test/**及测试文件src/**/*.test.{ts,tsx}。前端分支门禁65%，后端领域分支90%由其单独门禁负责；本轮无后端变动，未重新执行其测试或核心覆盖，不能引用历史数量作为本轮结果。

## 实际运行与交付

`node docs/test-evidence/2026-10-26/UI-REHEARSAL-09/live-readonly.cjs` exit0；实际5181新浏览器会话只读查看五项绿色当前通过标记、协同顶部沟通操作条、蓝色进度入口及1440/390px布局，0业务写请求/0页面异常，前后备份SHA均：

`1ff611f8cb71441d3d047c8d359ca03c0ca436d3ea3191e8c6301dce2c7c124f`

见LIVE-READONLY.json/txt和live截图。已视觉查看移动批量按钮、议题操作条及失败标记截图。未对实际项目做清空、恢复、导入、审核、执行提交或重启。刷新前端即可继续，既有数据和流程保留。

操作指南、任务表、开发日志、决策、文档索引及验收摘要同步。范围限于入口位置和结果辨识度，未改变实际审核、有效性、执行、符合性及风险处置规则。
