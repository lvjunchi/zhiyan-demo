# UI-Z3 统一品牌栏、参考卡车与简化阶段导航

任务关联本轮3项及AC-19/20/21的前端展示范围。没有开始其他会议任务或重新签署完整P0验收。

## 实现与决策

- 卡车使用用户本轮179×246附件的原始字节，替换手绘SVG；仅CSS融合边缘，来源和校验值记录于assets/SOURCES.md。无新生成素材、外部资源请求或依赖变化。
- 顶部统一显示品牌和完整平台名，备份/恢复仍在工具区；模块标题不再重复平台全称。桌面同行，手机自适应换行。
- 删除总览“当前进度”横条、额外当前标签及阶段编号。五阶段独立卡片增加间隔，只突出当前步骤；保留唯一aria-current及可点击导航。原业务卡片继续呈现待澄清、阻断、草稿和待更新。
- 阶段沿用已有成果定位，不表示执行中、已验收或前序阻断已关闭。后端仍是审核、有效性、符合性和门槛唯一权威；没有改动任何领域规则。

## RED / GREEN / REFACTOR

`npx vitest run src/App.test.tsx src/panels/OverviewPanel.test.tsx`：RED退出1，4失败/25通过，失败针对统一品牌栏、删除额外进度区域及空项目/变型/旧材料阶段行为。GREEN和REFACTOR同命令均退出0、29通过。见red.txt、green.txt、refactor.txt。保留点击导航、草稿/待更新和26项阻断断言，没有删除业务检查换绿。

`npm run test:coverage`退出0，22文件141测试通过，见frontend-coverage.txt。TS语句1939/2254=86.02%，分支1640/2238=73.27%，函数87.48%，行90.97%。既有排除src/main.tsx（入口挂载）、src/test/**（测试设施）和测试本身不变；没有新增排除。本轮未重测后端覆盖，不将整体前端分支覆盖冒称为核心领域90%。

`npm run lint`退出0、零警告；`npm run build`退出0，最终CSS调整后重新构建成功。见lint-final.txt、build-final.txt。

## 浏览器与视觉检查

使用独立临时后端库，端口ZHIYAN_E2E_API_PORT=8074、ZHIYAN_E2E_UI_PORT=5224，按轮次设置ZHIYAN_EVIDENCE_DIR隔离输出。

初次专项检查4通过/3失败：侧栏超高、1440材料卡2像素裁切。调整导航间距和卡片布局后，全量`npx playwright test --config playwright.cockpit.config.ts`有21通过/1失败：1366追溯表仅差2像素。保留browser-initial.txt、browser-final.txt及实际归档trace；没有放宽断言。将低高度屏幕验证区域间距8px改为6px后，仅重跑失败项：

`npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts -g 'shows the complete project dashboard'`退出0，1通过（browser-spacing-recheck.txt）。最终22个不同检查通过，统计来自21项全量成功及1项修复重验，不声称最后一次完整调用22项全绿。

验证范围包括1920/1440/1366总览一屏、表格/参数完整，1280侧栏、390手机无整页横向溢出，图片实际加载原始179像素宽度，品牌全称唯一、模块不重复、当前阶段唯一且不同颜色、数字对比度、键盘/下一步导航，以及现有详情、审核、故障反馈、备份恢复和版本闭环。已目视检查browser-spacing-recheck/dashboard-1366.png及日常总览图；截图用于布局复核，不替代业务断言。

## 数据保护与限制

`node docs/test-evidence/2026-10-22/UI-Z3/live-check.cjs`退出0；11个模块只读，writes/errors/external均为空，模块无报错。13条需求和1份来源保留，备份前后hash均为707a983dc73077c88324d3fd67574fe276da29aadfc0510b2afa2173745dcaef。未导入、确认、清空、恢复或重置用户内容。源data/demo.db校验值仍edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0，参考资料未修改。

本轮只涉及前端展示，无后端改动；pytest和完整P0验收未重新执行。README、演示指南和老师说明已更新，历史UI-Z2记录保留。启动仍为根目录Start-Demo.cmd；现有5181开发服务刷新即可。
