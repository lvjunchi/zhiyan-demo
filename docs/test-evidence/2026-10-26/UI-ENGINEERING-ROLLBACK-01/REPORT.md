# UI-ENGINEERING-ROLLBACK-01 恢复原有记录布局

2026-10-26，用户明确要求回退上一轮布局：选完零件后应向下查看记录，避免返回上方或切换页签。关联O3/O4、AC-20。

## 范围

恢复BasesPanel先PartChoicesPanel、后EngineeringRecords；记录区标题恢复“工程决策版本与审核”，变型点与零件同表展示，保留原对象/基型/名称/版本/审核/有效性/操作七列和“查看编号版本”按钮。去掉新增分类页签、排序与只读分类限制，删除本轮前新增且仅供该布局使用的engineering-records.css。原基型筛选、历史折叠、旧版本与审核、失败输入、保存后读取重试和焦点恢复保留。

不是恢复业务备份，也没有版本回退数据库。零件撤回并驳回、撤回原因选填、已确认状态、评分、需求统计等此前功能未动；保留审核成功后自动刷新选型的回调和稳定对象定位属性。选型提示及主指南已改回“下方统一表”。没有后端、依赖或参考原件改动。

## 验证

- RED：更新本轮回退验收和原按钮选择器后，`npm test -- src/components/EngineeringRecords.test.tsx`退出1，原双页签界面不满足混合表、旧标题/入口要求，9失败，见red.txt。取消的页签分类测试改为验证同表包含变型点和零件，未删除原历史/错误/审核断言。
- GREEN：frontend目录`npm test -- src/components/EngineeringRecords.test.tsx src/panels/BasesPanel.test.tsx src/panels/PartChoicesPanel.test.tsx`：20通过、退出0，见components.txt。没有另行重构阶段，也未重跑全量覆盖。
- frontend目录`npm run lint`、`npm run build`退出0，见lint.txt/build.txt。JS525.03kB，已有500kB默认体积提醒保留。
- frontend目录`npx playwright test --config playwright.overview.config.ts review-usability.spec.ts`：1通过、退出0，见browser.txt。验证整个零件选型区在记录区前、无需页签、实际选型及历史、确认后自动刷新、空原因撤回与原审核闭环。
- frontend目录`npx playwright test --config playwright.cockpit.config.ts part-selection.spec.ts version-dialog.spec.ts saved-feedback.spec.ts z-workflow.spec.ts`：4通过、退出0，见cockpit.txt。恢复原记录入口选择器，保留原件、型号审核历史、失败恢复、原生版本弹窗焦点与手机尺寸、材料包关联定位。两组5个不同用例，不累加重复运行；均在独立临时库，未使用日常工作副本。
- `node docs/test-evidence/2026-10-26/UI-ENGINEERING-ROLLBACK-01/live-readonly.cjs`退出0：实际5181验证选型在上、混合表在下、版本关闭后返回按钮、选填撤回按钮仍可用，以及390px无页面横向溢出。桌面与手机截图已目检，见engineering-records.png、engineering-records-mobile.png及live-readonly.json。所有非只读API请求被拦截，0实际业务写请求、0页面错误。

当前数据SHA前后均77f81645f98ede6a212506c68e7b3b3080b17f67db77b751da984a189e7d095a。未重启、清空、恢复或在用户库操作审核。未执行后端全量、前端全量覆盖或其余浏览器套件，不引用历史覆盖作为本次结果。主指南docs/DEMO_GUIDE.md已同步。刷新 http://127.0.0.1:5181/ 查看。
