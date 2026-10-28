# UI-PACKAGE-01 总览评审材料卡片

任务关联：用户截图、O13、AC-16/20/21。仅前端展示，不改变材料包生成、审批、门禁或数据库。

## 变更

独立 OverviewPackage 组件，替换原卡片左上角聚集的小段文字。状态图标、材料编号和冻结状态形成首组；中间显示真实快照的阻断与提示数量；下方提供下一步提示和整行“查看评审材料”按钮。草稿、可提交、人工批准仍直接展示后端状态，不根据数量自动推导通过。

旧版材料标注“旧版材料 · 待更新”和“上次快照 · 待更新”，保留上次快照计数，不称为当前检查结果；未生成时显示—，不补0。矮屏简化辅助说明，完整含义保留在快照区域悬停说明及材料页，状态不省略。

## RED / GREEN / REFACTOR

- RED：`npm test -- src/panels/OverviewPanel.test.tsx -t 'useful package snapshot summary'`，2项因缺“评审材料摘要”区域失败，退出1，见red.txt。`npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts -g 'complete project dashboard'` 因缺摘要区域失败，退出1，见red-browser.txt。
- GREEN：组件文件最终33项通过，退出0。新增断言草稿/旧版快照的阻断与提示、冻结状态、查看入口只导航不写业务；增强未生成时不能显示0的断言。原26项阻断断言改为对实际分组的完整文本核对，保留业务强度。
- 目视发现初轮小屏检查块内部挤压，增加`.package-checks`的内部裁切检查并得到RED；见red-inner-layout.txt。修正间距、普通屏最小高度及矮屏单排统计，保留所有原同屏/可读性/按钮间距断言。
- 最终浏览器 `npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts overview-trace.spec.ts` 3项通过，退出0；覆盖2560/1920/1440/1366桌面、390手机、按钮整行及靠近底边、检查块无内部裁切、原追溯详情/焦点返回。见browser-final.txt。
- 独立组件和局部样式为重构结果；`npm run lint`、`npm run build`均退出0。未修改后端领域规则，未重复全量后端及覆盖率，无新增覆盖排除，不把历史覆盖报告当作本轮重跑。

## 实际页面与数据

实际5181页面1920/1440/1366截图已目视检查。卡片clientHeight分别205/145/123px，内部检查块scroll/client分别50/50、42/42、26/26，均无裁切，桌面同屏。只读浏览器写请求0、页面错误0，前后业务SHA相同，见live.json和card-*.png。没有生成新包、执行审批、清空或替换业务数据，无需重启后端。
