# UI-P1 总览图注与交互检查

2026-10-21，AC-20。图注改为“重型变速器 · 产品展示”，移除具体型号及来源链接；图片和参数未改。SOURCES.md 保留原始来源、哈希、版权和外观参考边界，指南同步。

纯文案/样式，RED 不适用。frontend 下 npm run build、npm run lint 退出 0；根目录 node docs/test-evidence/2026-10-21/UI-P1/check.cjs 退出 0，页面真实文案/无来源链接/原图可见通过，无横向溢出。见 build.txt、lint.txt、check.cjs、result.json、product.png。未重跑全量测试或覆盖率，无新排除；未修改后端或日常业务数据。刷新 5181 查看，启动仍 Start-Demo.cmd。

源码检查后的建议（尚未实施，按顺序）：

1. RequirementInspector 目前出现在需求列表下方，适合右侧抽屉，查原文/切换版本时保留列表上下文。
2. ConsistencyPanel 的关闭冲突表单目前追加在表格后，适合侧抽屉集中展示证据、处置方式与意见，保存后更新原行。
3. SamplesPanel 的明细和比对结果目前追加在列表下方，适合宽幅弹窗查看参数/实测/差异。

已有设计评审/DFMEA/试验方案/材料快照预览可后续统一到同一套弹窗组件；长流程编辑适合独立工作区。上述建议不作为已完成功能。
