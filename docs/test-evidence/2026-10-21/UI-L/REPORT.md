# UI-L 一致性统计展示修复

日期：2026-10-21。关联一致性引擎、AC-13/20/21；依赖 UI-K。范围为前端展示，不改后端判定、确认、失效传播或材料门禁。

## 问题与变更

旧统计区遍历 summary 的全部键，并对值直接 String()。by_severity、by_type 为嵌套对象，因而显示 `[object Object]`，内部字段名也进入界面；这是显示错误，不能据此认定引擎未运行。

- 六个主要指标使用明确中文名称；严重度、问题类型各自展开统计，复检摘要单独呈现。
- 保留后端返回的真实数量及零值，不由前端冲突列表重算。缺失、负数、非有限数、字符串及对象数值显示“—”；缺失分布显示未记录。
- 报告/对象审核状态中文化；报告更新时间格式化，输入快照说明为报告生成时数据。未确认与冲突仍可同时呈现。
- 1920px 六列、常规桌面三列、手机两列，分布区自动换行；不再堆满同一横排。

修改：ConsistencyPanel.tsx、ConsistencyStats.tsx、consistencyStats.css、consistencyPresentation.ts 与回归测试；未改参考原件和数据库。

## TDD 与实际验证

| 阶段 | 命令（frontend 目录） | 退出码 / 结果 | 证据 |
| --- | --- | --- | --- |
| RED | npm test -- src/panels/ConsistencyPanel.test.tsx | 1；3 failed / 2 passed；缺少中文统计/分布与非法输入展示行为 | [red.txt](red.txt) |
| GREEN | 同上 | 0；5 passed | [green.txt](green.txt) |
| 最终回归 | npm run test:coverage | 0；22 文件 / 74 passed | [coverage.txt](coverage.txt) |
| 检查 | npm run lint | 0；10 条既有 effect 警告 | [lint.txt](lint.txt) |
| 构建 | npm run build | 0 | [build.txt](build.txt) |
| 浏览器 | npx playwright test --config playwright.r2.config.ts | 0；5 passed，独立临时数据库/8048 与 5198，未复用日常工作副本 | [browser.txt](browser.txt) |

GREEN 后未再改展示实现，无额外行为重构；最终全量回归验证相同实现。新增三项组件行为覆盖嵌套分布、真实零值/缺失、非法值；保留原运行检查/确认/关闭行为断言。浏览器既有四项回归加一项真实报告统计核对，分别比较 API 标量与分布，不用截图替代断言；同时验证 1920/1440/1366/390px 无页面或统计区横向溢出、无 pageerror。

TS：语句 82.80%（1425/1721），分支 66.26%（982/1482），函数 83.53%，行 87.26%。原有排除 src/main.tsx（启动）、src/test/**（测试工具）、src/**/*.test.{ts,tsx}（测试本身）；未新增业务路径排除。前端 UI 分支不作为后端核心领域分支 ≥90% 的证明；本轮未执行 Python 测试或重算 Python 覆盖率。

日常 5181 另以 Edge 只读冒烟：打开一致性检测、检查无原始对象文字、保存[现场截图](live-consistency.png)，无页面异常或横向溢出，见 [live-browser.json](live-browser.json)。只读 API [live-readonly.json](live-readonly.json)记录 health 正常、现场已存报告 total/open 为 0、status=confirmed；只说明该报告记录，不将零冲突等同所有需求/材料已通过。首次辅助只读探测误用 review_status 键导致 KeyError，改为实际 status 键后成功；未产生写请求或重启服务。

截图：[桌面](consistency-1440.png)、[手机](consistency-390.png)。原有业务主线/全 AC 与长期混沌测试未在本轮重新签署，R2/UI-K 历史结论不冒充新执行。

启动方式不变，按根目录 README 使用持久化预览工作副本。现场刷新 http://127.0.0.1:5181/ 即可查看。
