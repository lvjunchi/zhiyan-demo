# VERIFY-03 完整主线与最终交付核对

2026-10-21。完成顺序：START-01/UI-M → UI-N/MAINT-01 → 本轮验收与文档。各阶段历史报告保留，不把此前数量累加为当前通过数。

## 最终实际结果

| 命令 / 范围 | 退出码与结果 | 证据 |
| --- | --- | --- |
| python -m pytest backend/tests -q | 0；**256 passed**，1 条已知 testclient 依赖弃用 warning | [backend-full.txt](backend-full.txt) |
| python -m pytest backend/tests/test_delivery_integrity.py backend/tests/test_acceptance_p0.py --no-cov -vv | 0；5 passed，包含在全量范围内，不另加数量 | [mainline.txt](mainline.txt) |
| python -m coverage json -o docs/test-evidence/2026-10-21/VERIFY-03/python-coverage.json | 0；本次全量覆盖导出 | [python-coverage.json](python-coverage.json) |
| python scripts/check_core_coverage.py docs/test-evidence/2026-10-21/VERIFY-03/python-coverage.json | 0；核心领域独立门禁通过 | [core-gate.json](core-gate.json) |
| npm run test:coverage（frontend） | 0；**83 passed** | [前端原始记录](../MAINT-01/coverage-complete.txt) |
| npm run lint / npm run build（frontend） | 均 0；前端检查 0 警告 | [lint](../MAINT-01/lint-complete.txt)、[build](../UI-N/build-complete.txt) |

Python app：语句 **95.34%**，分支 84.96%，覆盖综合 93.04%；核心 domain/** 分支 **90.50%**（505/558）、语句 96.87%。TS 语句 **83.06%**、UI 分支 66.47%。Python/TS 分开计算，app 未新增业务路径排除；启动/检查工具由专项测试验证，不冒充纯领域覆盖。

## 浏览器：20 个不同检查

| frontend 命令 | 结果 | 证据 |
| --- | --- | --- |
| npx playwright test --config playwright.cockpit.config.ts | 8 passed | [总览/模块/备份/故障](../UI-N/cockpit.txt) |
| npx playwright test --config playwright.r2.config.ts | 7 passed | [版本/证据/预览/错误重试](../UI-N/workspace.txt) |
| npx playwright test --config playwright.review.config.ts | 1 passed | [模块复演](review.txt) |
| npx playwright test --config playwright.single-project.config.ts | 3 passed | [独立新项目/API 冲突/材料阻断](single.txt) |
| npx playwright test --config playwright.change.config.ts | 1 passed | [2600→2800 旧成果阻断](change.txt) |

全部配置使用独立临时库/专用端口，不复用日常工作副本。早期单条布局试跑与重复检查不再加到 20 中。最后的样件原生文件输入隔离改动由新增真实 RED 和完整前端回归验证；未为这一 DOM 改动重复全套浏览器场景。

## 主线结论与真实边界

API/SQLite 受控验收覆盖协议/需求、型谱/工程决策确认、设计/DFMEA、方案/用例、试验/样件、冲突、材料 ready 与人工批准，再执行 2600→2800 的失效/复核恢复；独立五条验证集 80→60→80→100、TC-007 当前加载/2.4 失败/2.5 通过、旧结果保留有自动断言。并发导出/修订冻结一套版本、旧门禁不能批准也通过。

浏览器验证真实业务模块操作、原件下载、工程版本、材料阻塞跳转、需求变更、备份恢复、保存失败和请求断连可重试；**不是从头在浏览器手填所有数据后再次完成全部人工审核的录像**。当前已测场景无未解释关键失败，不把测试总数当任意依赖图或文档泛化证明。

## 日常数据与运行

以新启动器实际启动日常 8027/5181，已有恢复指针及工作副本继续使用；未重置或恢复用户项目。启动前后业务 SQL 快照 SHA-256 一致，原 demo.db SHA-256 不变：

- [启动前](data-before-start.json)、[启动后](data-after-start.json)；semantic_unchanged=true。
- [日常页面只读核对](../UI-N/live-check.json)；无外网请求、页面异常或溢出。
- 现场仍保留设计/DFMEA 待复核、旧材料需更新的状态，不将其自动改成可提交。

本轮未完成复杂文档质量基准、任意依赖传播组合、长期压力、操作系统级磁盘故障/任意时点强杀恢复。早期 GAP-02 与 UI-M App 初始测试错误的 RED 缺口继续披露，不能追认；不签全部 AC-01–AC-21。安装与启动见根 README，日常双击 Start-Demo.cmd；当前 http://127.0.0.1:5181/。
