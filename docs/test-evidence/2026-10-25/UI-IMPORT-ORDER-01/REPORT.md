# UI-IMPORT-ORDER-01 导入操作在前

2026-10-25，关联O1、AC-20。按用户纠正的意图，将ParsingPanel中的整个DocumentImportStatus从上传表单之前移到之后；内部仍为概况→文档列表→分布图和处理记录，后接导入问题与澄清。仅移动组件位置，没有改变状态、审核、统计或草稿逻辑。

纯展示顺序调整，没有新增业务行为，不新增重复测试或制造RED。复用现有组件回归：`npm test -- src/panels/Stage03.test.tsx src/panels/ImportDistribution.test.tsx src/panels/ImportResume.test.tsx src/panels/ParsingPanel.test.tsx`，4文件20项通过，退出0。`npm run lint`及`npm run build`退出0，现有522.99kB构建体积提醒保留。日志见本目录components.txt、lint.txt、build.txt。

`node docs/test-evidence/2026-10-25/UI-IMPORT-ORDER-01/live-layout.cjs`退出0。在实际5181页面验证整个上传表单底边不高于管理卡片顶边、内部上下顺序正确、桌面图表两列/390px一列且页面无横向溢出。所有非只读API请求被拦截，实际0写请求、0页面错误。截图及live-layout.json保存在本目录。

未执行全量后端、全量覆盖或隔离浏览器业务套件；未重启、恢复或清空日常数据。主操作指南已同步顺序。
