# UX-BATCH-RUN-DIALOG 工程批量确认与执行弹窗

2026-10-27；本轮2项，O3/O4/O10、AC-07/08/09/11/18/20。

## 修改与决策

批量确认额外用part_number以DEMO-开头过滤原始复用/变型件，逐条审核没有该限制，造成用户只确认前两项变型点。现统一两者口径：前端预览包含当前适用、current、draft/pending_review的变型点及零件决策，排除已审、驳回、stale和历史；后端去掉额外前缀门槛，继续在单事务中先审核变型再审核零件，并调用与单条相同的_confirm_in_transaction。依赖、版本、迁移来源、项目、候选适配和审计校验均保留。

这确认的是当前工程复用/变型决策，不会自动选候选、改型号或将候选卡片标为已选。显式选候选后仍按新版本独立审核。测试证明全批原始PN确认后，原型号保持、selected_candidate_id仍为null、selection_state仍unselected。原“未选候选必拒绝”测试与本次统一逐条口径冲突，改为“缺少上游变型确认时拒绝”，保持事务回滚断言。

记录执行从默认内联表单改为显式弹窗，包含编号/名称/版本、原预填、提交/取消。点击不写执行；取消/关闭/Esc不提交，同版输入在本页保留，项目和版本隔离。保存失败留窗，保存成功后关窗并刷新列表；读取失败明示已保存，只重读而不再写执行。预填加载仍按精确需求ID/revision/current/confirmed读取，2.6独立合成来源和手工覆盖保护不变；后端2.4失败规则不变。

## TDD 与证据

后端命令在仓库根目录，前端在frontend；原始输出均保留。本轮未跳过/降低断言。

| 阶段 | 命令/输出 | 实际结果 |
| --- | --- | --- |
| RED后端 | `python -m pytest backend/tests/test_engineering_batch.py -q -k all_original`，RED-BACKEND.txt | exit1；新增行为断言预期201、实际422（原前缀限制）。同时由于仅跑单项而触发全局80%覆盖门槛；GREEN专项使用--no-cov，全量另实际验覆盖 |
| RED前端 | `npm test -- --maxWorkers=2 src/components/EngineeringRecords.test.tsx src/panels/TestingPanel.test.tsx`，RED-FRONTEND.txt | exit1；2失败17通过，批量漏原始零件、执行缺弹窗；实现前运行 |
| GREEN后端 | `python -m pytest backend/tests/test_engineering_batch.py backend/tests/test_engineering_versions.py backend/tests/test_part_selection.py --no-cov -q` | exit0；21通过，含全批原始件、逐项留痕、不自动选候选、事务回滚及既有版本/选型规则 |
| GREEN前端 | 同RED前端命令，GREEN-FRONTEND.txt | exit1；18通过1失败，旧人工执行用例确认后直接访问默认内联表单，按新交互增加显式打开，不删除原提交/判定断言 |
| GREEN前端复验 | 同命令，GREEN-FRONTEND-RECHECK.txt | exit0；20通过。另补保存失败留窗及保存后读取失败关闭/不重写测试 |
| 后端全量 | `python -m pytest -q --cov-report=json:docs/test-evidence/2026-10-27/UX-BATCH-RUN-DIALOG/backend-coverage.json`，BACKEND-FULL.txt | exit0；357通过，整体覆盖93.48%；1条既有Starlette/httpx弃用提示 |
| 核心领域 | `python scripts/check_core_coverage.py docs/test-evidence/2026-10-27/UX-BATCH-RUN-DIALOG/backend-coverage.json` | exit0；backend/app/domain/**语句97.1873%、分支91.9521%，核心门禁通过 |
| 前端全量覆盖 | `npm run test:coverage -- --maxWorkers=2`，FRONTEND-COVERAGE.txt | exit0；36文件230通过，语句85.07%、分支74.97%、函数82.57%、行91.21%，门禁通过 |
| 浏览器执行/版本 | `npx playwright test --config playwright.cockpit.config.ts execution-feedback.spec.ts version-dialog.spec.ts` | exit0；3通过。验证真正模态、焦点、取消不写/重开保留2.4、390px边界、成功关窗和真实fail保存，及既有版本弹窗/沟通流程 |
| 浏览器主流程 | `npx playwright test --config playwright.overview.config.ts demo-usability.spec.ts` | exit0；1通过。批量预览10项全部本次确认、后端10项confirmed、候选仍全部未选；执行预填改为显式打开弹窗，其他导入/评分/样件/协同仍通过 |
| 格式与复验 | `python -m black --check backend/app/engineering_batches.py backend/tests/test_engineering_batch.py` | 初次exit1仅测试文件需换行；black格式化后专项21再次通过，BLACK-FINAL.txt exit0。无业务重构改动 |
| 静态/构建 | `npm run lint`、`npm run build` | exit0；lint无警告，构建保留既有>500kB提示，主块549.63kB |

不同浏览器用例共4项，不与历史轮次相加，写入均使用配置自建隔离测试库。前端覆盖排除仍为src/main.tsx启动入口、src/test/**夹具及src/**/*.test.{ts,tsx}；后端核心范围由脚本明确为backend/app/domain/**，无新增排除。当前UI前端分支门禁65%，核心领域分支门禁90%，各自实测而非合并数量。

## 实际服务更新与只读验证

旧启动器PID56176经已有refresh-runtime.py验证归属、保存可校验备份后向其原控制台输入stop，正常备份退出，不强杀端口。runtime-stop.txt记录业务SHA：

`cbee9031bd69f3e029b496f936a9bd6b24bf058cba1330a085b90a122152ad9c`

尝试Start-Process启动的复杂PowerShell命令被自动审批拦截，未执行；改为允许的直接受控exec命令`python scripts/start_demo.py --backend-port 8027 --frontend-port 5181 --no-browser`成功启动（会话9023、PID22644），不是绕过服务归属校验或强杀。新服务8027/5181就绪，runtime-after.json业务SHA相同。

`node docs/test-evidence/2026-10-27/UX-BATCH-RUN-DIALOG/live-readonly.cjs` exit0；实际5181新浏览器会话只读打开完整批量预览和执行弹窗，检查1440/390px、预填与关闭。该会话当前记录已全部审核，eligible=0、pending=0匹配；完整10项批量写入由隔离浏览器和后端测试验证，不在用户项目补做审核。0业务写请求/0页面错误，前后备份SHA仍相同。未清空、恢复、重导或提交任何实际用户执行。

已视觉检查桌面/手机执行弹窗截图。操作指南、任务、开发日志、决策、文档索引及验收摘要同步。前后端均已加载新代码，刷新页面即可继续；关闭弹窗不会跨页面/刷新持久保存草稿，仅本页保留，正式执行仍须明确提交。
