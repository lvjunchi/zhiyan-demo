# UI-ENGINEERING-FLOW-01 变型审核与版本记录

2026-10-25，用户授权优化工程记录区。关联O3/O4、AC-05/07/09/18/20。保留后端真实审核、ID、版本和依赖判定，本轮只改前端流程、展示及刷新联动。

## 实现与界面顺序

- BasesPanel顺序为运行变型分析→变型审核与版本记录→零件型号选择。记录区默认“变型点审核”，第二页签为“零件选型记录”，使用相同持久化工程对象，不复制业务记录。页签支持方向键/Home/End，项目切换隔离，保留基型筛选与不适用记录折叠。
- 名称在前，类型和稳定编号作辅助信息；修订号显示“第N版”，与V编号区分。审核与有效性分别展示，draft显示待审核，按待复核、待审核、驳回、已确认优先排序，待复核与待审核数字仍为独立维度。
- 按钮简化为“审核详情”/“版本记录”，可访问名称带稳定编号以区分对象。旧版本、引用和审核留痕仍可查，关闭恢复原按钮焦点，失败与已保存后读取失败的保护保留。
- 变型点审核保存成功才通知下方零件刷新；自身详情不因联动刷新而消失。零件记录页签只读，所有零件型号选择、确认、撤回留在卡片，避免再做一次审核。后端审核规则及材料门槛没有改。
- 零件卡片增加原持久化对象的data-object-id，保证材料包待办跳转能在默认变型页签下定位到卡片；没有用排序或下标生成身份。选型提示和主操作指南同步新位置与自动刷新。

## RED / GREEN / REFACTOR

- `npm test -- src/components/EngineeringRecords.test.tsx`实现前退出1：原7通过、新2失败，缺少分类页签/新审核入口。见red.txt。新增测试验证分类与只读边界、待处理排序、实际expected_revision及保存成功/失败后的联动。保留原焦点、历史、失败输入、基型隔离和保存后读取重试断言，更新按钮与标题选择器。
- 实现后`npm test -- src/components/EngineeringRecords.test.tsx src/panels/BasesPanel.test.tsx src/panels/PartChoicesPanel.test.tsx`：3文件20通过、退出0，见components.txt。
- `npm run test:coverage -- --maxWorkers=1`：32文件203通过、退出0；前端语句85.06%、分支73.76%、函数82.69%、行91.01%，门禁通过。见frontend-full.txt。沿用既有main.tsx、src/test、测试文件排除，无新增排除；核心领域未改，不把历史后端核心覆盖当本轮重跑结果。
- 后续展示重构清除新引入的effect同步setState lint提醒；补充零件卡片定位属性并统一只读提示。最终重复上述20组件检查通过，见refactor-components.txt。`npm run lint`无新增提醒，`npm run build`退出0，见lint-final.txt/build-final.txt；JS527.51kB默认体积提醒保留。
- 首次GREEN命令误在根目录使用frontend相对日志路径，重定向失败，npm未执行；不计作RED/GREEN或通过次数。正确工作目录执行结果如上。

## 独立浏览器检查

命令均在frontend目录，设置ZHIYAN_EVIDENCE_DIR指向本目录。

- `npx playwright test --config playwright.overview.config.ts review-usability.spec.ts`：1通过、退出0。验证变型审核区整块在零件选型前、变型确认后无需手动刷新即可继续确认零件、零件版本记录只读、关闭焦点恢复，以及原驳回/撤回和试验审核闭环。见browser.txt。
- `npx playwright test --config playwright.cockpit.config.ts part-selection.spec.ts version-dialog.spec.ts saved-feedback.spec.ts z-workflow.spec.ts`：4通过、退出0。更新受影响旧选择器及早前已改成自动关窗的断言，保留型号/审核历史、原件、失败恢复、版本弹窗原生焦点/手机尺寸与材料包关联定位。见cockpit.txt。两组共5个不同测试，不累加重复运行。
- 两配置各自使用独立临时SQLite（cockpit只读复制data/demo.db后在临时库操作），不使用日常持久工作副本。没有更改种子或参考原件。未跑其余浏览器全套或后端全量。

## 实际运行

`node docs/test-evidence/2026-10-25/UI-ENGINEERING-FLOW-01/live-readonly.cjs`退出0；最终见live-readonly-final.txt/live-readonly.json。实际5181页面验证变型在选型前、键盘切换页签、零件记录无重复确认入口、关闭恢复焦点、390px无页面横向溢出。宽表在其容器内可横向滚动。桌面变型区、零件记录、历史弹窗及手机截图已目检，见live-variant-review.png、live-part-records.png、live-part-history.png、live-part-records-mobile.png。

所有非只读业务请求被拦截，实际0写请求、0页面错误。前后SHA均77f81645f98ede6a212506c68e7b3b3080b17f67db77b751da984a189e7d095a。保留用户当前操作状态，未清空、恢复、重启或在日常库审批。此次没有后端改动，刷新 http://127.0.0.1:5181/ 即可查看。主指南为docs/DEMO_GUIDE.md。
