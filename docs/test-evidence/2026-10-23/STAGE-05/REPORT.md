# STAGE-05 型谱与零件候选

会议18、O2/O3/O4，AC-05/07/08/09/18/20/21。017迁移预置24个只读合成候选（8类×3型号），扭矩/档数匹配包络，不冒称制造规格；本地SVG工程示意与现有产品参考图有明确说明。候选选择写入原工程零件part_number/source/reason并建立版本、依据和audit，原编号/UUID不变；独立审核同步工程版本和材料包门槛。重新分析保留选择，需求变更失效并重新捕获引用，零件变更使设计/一致性待复核。

RED：`python -m pytest backend/tests/test_part_selection.py --no-cov --basetemp docs/test-evidence/2026-10-23/STAGE-05/pytest-red -q`退出1，3失败（缺接口）；`npx vitest run src/panels/PartChoicesPanel.test.tsx`退出1（缺组件）。GREEN专项后端17通过/前端2通过；首轮备份预览测试写错路径404已改为真实restore-preview。构建发现旧总览调用示意组件缺少name，保留兼容默认名后通过。

完整回归初轮305通过/1失败：迁移预置候选与清空副本重复插入冲突。修复project_clear为对预置记录逐字段核对，一致才保留、冲突报错；增加清空后候选数量不变断言，专项19通过。最终`python -m pytest --basetemp docs/test-evidence/2026-10-23/STAGE-05/pytest-full-final -q` 306通过（196.65秒），综合93.12%；核心覆盖见core-coverage-final.txt（仍96.93%语句/90.75%分支）。`npm run test:coverage`174通过，TS语句85.12%、分支74.28%、函数85.36%、行90.63%；lint/build/Black通过，覆盖排除未扩大。后续仅工程版本摘要增加型号字段，完整浏览器覆盖该字段。

浏览器cockpit26通过（新增选型→保存→独立确认→刷新保留→版本历史/审核留痕→390窄屏），overview4通过（空白/Word/PDF/清空重导入/批量需求），共30个不同检查。图片见browser/。所有测试仅临时库，日常项目未清空，需正常退出后重启加载017。现有P0主线可继续沿用基型零件；显式候选选择是工程决策的版本内容，不凭界面按钮声称真实制造适配。未实现自动CAD判定或现场连接。
