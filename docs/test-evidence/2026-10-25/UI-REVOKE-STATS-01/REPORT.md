# UI-REVOKE-STATS-01 撤回选型确认与需求统计

2026-10-25；用户明确授权两项修改。关联O1/O4、AC-07/09/16/18/20。仅本地Demo，独立测试库；没有清空、恢复或审批用户业务。

## 实现

- PartChoicesPanel为当前有效、已明确选定且已确认的零件显示撤回原因和“撤回确认并驳回”。原因必填；失败保留输入，保存成功并刷新后关闭弹窗、显示红色已驳回。沿用工程审核API，后端对confirmed→rejected额外要求非空原因，重复决定/旧revision拒绝。
- 原engineering_record_confirmations与版本快照不改；新增rejected决定，另记part.confirmation_withdrawn审计，关联原确认ID与新驳回ID、原因、身份、角色、对象版本和时间。审核状态变更不虚增内容revision。
- 与撤回在同一事务内：按现有项目/基型边界，将设计评审和DFMEA保守整体置为stale；DFMEA最新条目失效，真实引用这些条目的用例进入待复核，未引用的用例不变。一致性报告需复检；旧试验及冻结材料不改。已有待复核DFMEA也不会漏掉传播。材料包重新生成时由原门槛阻塞未确认/失效成果。
- 设计/DFMEA在内容快照相同但文档已stale时允许重新生成新草案版本，避免卡在旧失效版本；不得自动恢复旧审核或旧试验。普通需求变更的原选择性传播保持，不因整个DFMEA文档stale扩大固定覆盖失效范围。
- RequirementReviewChart左侧环形图与总数、已确认占比，右侧待审核/已确认/已驳回卡片。draft与pending_review合计，点击筛选/全部入口保留，并标记当前筛选；统计始终基于全部需求，stale按有效性单独计数。无需求不显示100%，失败不展示陈旧百分比。桌面与390px响应式适配，无新增远程资源或依赖。

## RED与过程纠正

- 实现前backend-red.txt / backend-red-verified.txt中空白撤回原因被201接受、事务故障注入未被执行，均是真实缺失行为；frontend-red.txt中已确认记录没有撤回按钮（1失败/3通过）。chart-red.txt缺少环形图及空态（2失败）。命令均退出1。
- 新主线测试首次把试验API误写为数值/201/顶层run形状，按现有人工判定契约改为manual_result、200和run嵌套；这些夹具错误不计为产品RED。最终主线断言校验原确认/版本完整、撤回关联、失效传播、旧执行保留、重复提交、备份有效。
- 首次扩大FMEA有效性检查至所有stale文档，导致既有主线与选择性传播失败；撤回传播改为明确失效所涉FMEA条目，撤销该全局判定改动，P0与变更传播复跑通过。首轮全量在修复后主动中断，backend-full.txt不是通过证据。
- 旧材料包门槛测试曾无原因撤回已确认件，按新必填合同补充原因，原草稿/阻塞断言保留。
- 最终另发现“文档已stale但条目尚current”的传播边界，stale-red.txt为1个真实失败；查询同项目/基型全部相关文档后修复。完整344项运行已在此前开始，新增边界测试未在其中；最终代码另跑下述20项，不把重跑次数累加为更多不同测试。
- 首次前端全量并行同时运行后端/浏览器，一项原有ParsingPanel交互超出5秒；保持超时与断言，改用单worker复跑201项全部通过。

## 验证

- `python -m pytest backend/tests --basetemp docs/test-evidence/2026-10-25/UI-REVOKE-STATS-01/full-final-temp --cov-report=term-missing --cov-report=json:docs/test-evidence/2026-10-25/UI-REVOKE-STATS-01/backend-coverage.json`：344通过、退出0，见backend-full-final.txt。新增已stale边界修正另由最终专项验证。
- 最终代码：`python -m pytest backend/tests/test_part_withdrawal.py backend/tests/test_engineering_versions.py backend/tests/test_acceptance_p0.py backend/tests/test_change_propagation.py backend/tests/test_fmea_dependency_regression.py --no-cov --basetemp docs/test-evidence/2026-10-25/UI-REVOKE-STATS-01/targeted-final-temp`：20通过、退出0，含5撤回用例、主线、材料门槛、引用与故障回滚。见targeted-final.txt。
- `npm --prefix frontend run test:coverage -- --maxWorkers=1`：32文件201通过、退出0。前端语句85.14%、分支73.61%、函数82.75%、行91.15%。见frontend-full-final.txt。
- `npx playwright test --config playwright.overview.config.ts`：9通过、退出0。扩展review-usability真实点击撤回、校验确认/驳回双记录与撤回审计，检查统计筛选及390px无横向溢出。隔离测试库，见browser.txt与桌面/手机截图。
- `npm run lint`、`npm run build`退出0，现有默认包体积提醒保留（JS524.85kB），见lint.txt/build.txt。
- 后端整体覆盖93.42%；`python scripts/check_core_coverage.py .../backend-coverage.json`退出0，核心领域语句97.1873%、分支91.6096%，见core-coverage.json。未新增排除；前端沿用main.tsx启动入口、src/test与测试文件排除，领域90%分支门槛在后端独立核算。

## 实际运行与数据

核实原启动器10140及其子进程归属，先调用现有save_shutdown_backup保存/fsync/校验完整备份，再经该启动器已有控制台stop协议正常停服；原端口释放后隐藏启动同源/工作副本、同端口的新启动器48772（API52608/UI39436）。没有强制结束进程，也没有恢复/重置数据。工具脚本和日志在本目录refresh-runtime.py、runtime-before.json、runtime-stop.txt、runtime-start.txt、runtime-after.json。

重启前后、实际只读页面检查前后SHA均为a519de271e6561cf22761ff8543075ff3f96bf2933ecc9711039dfac3562a8cf。实际5181检查状态筛选、13条统计和已确认零件撤回入口；所有非只读API请求被拦截，实际0写请求、0页面错误，桌面/390px截图已目检。没有在日常数据上实际驳回，撤回业务写入由独立API及浏览器测试证明。见live-readonly.json、live-requirement-statistics.png、live-requirement-statistics-mobile.png、live-withdrawal.png。

刷新 http://127.0.0.1:5181/ 即可使用。主操作说明为docs/DEMO_GUIDE.md。
