# UI-PACKAGE-03 收紧快照统计框

关联本轮截图、O13、AC-20/21 展示范围。用户指出材料卡片中间框过宽，截图还显示统计框纵向拉伸。改为最大宽度 280px、左对齐、内容自然高度；矮屏继续使用原紧凑层级。取消统计框的 flex 增长，把剩余空间交给按钮上方外间距，按钮仍完整位于卡片底部。状态和数量仍来自原 API，不改变任何审核、材料生成或门禁规则。

## 测试证据

RED：在既有 `package-boundary.spec.ts` 中增加统计框宽度 ≤280.5px、高度 ≤60px 的可见几何断言，并增加 2560×1440。在 frontend 运行 `npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts`，退出1：统计框宽度实际386.328125px，大于280.5px，见 red.txt。

GREEN/回归：`npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts homepage.spec.ts`，3项通过、退出0，见 green.txt。新增约束在20个尺寸×2种密度（40组）检查；继续保留原按钮底部内边距、整卡/检查区无裁切、独立库业务SHA不变断言，没有放松之前的越界回归。首页同屏、其他卡片布局与模块导航检查通过。

`npm run lint`、`npm run build` 均退出0，最终102模块构建成功。改动仅局部CSS，没有新增结构重构，没有重跑后端/组件全量或覆盖率，无新增覆盖排除。

实际5181只读复核：`node docs/test-evidence/2026-10-25/UI-PACKAGE-03/live-check.cjs` 退出0，检查六尺寸并保存 live-*.png，已目视检查。1920×1001统计框由约70px高度缩至49.80px；1920×1080/2560×1440均为280×52px；1366×768为203.23×27px。按钮留边9px/15px，卡片和统计区scroll/client一致。请求写入0、页面异常0，8027业务SHA前后相同，见live-browser.json；未清空、重启或生成材料包。
