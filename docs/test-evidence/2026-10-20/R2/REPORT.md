# R2 操作主线、变更影响与成果预览（2026-10-20）

## 实际完成

| 任务 | 关联需求/O/验收 | 验收行为与结果 |
| --- | --- | --- |
| FLOW-02 | 全主线，AC-07/20 | 九阶段导航展示后端记录数、待办检查及失效数量；当前工作提示、写入后刷新、手动刷新、错误重试；阶段“已记录”不等于审核/门禁通过 |
| IMPACT-02 | AC-08/09，需求与工程版本 | 相邻需求版本及字段对比；仅沿已保存引用展示当前需求/变型/零件/设计/用例对象；引用版本与当前版本分别展示；已确认且 stale 同显；对象跳转高亮及返回 |
| VIEW-02 | AC-20，O7–O13 | 模块蓝灰色阶、工具栏、表格、状态、聚焦及响应式统一；设计评审、DFMEA、试验方案与材料快照只读预览；实际内容、输入/审核版本、文件清单；Esc 关闭与焦点返回 |
| VERIFY-02 | AC-18/21 | 全量回归、受控变化浏览器闭环、断连重试、临时数据库未提交事务进程中断回滚、持久化预览重启与状态校验 |

后端新增只读 `/api/projects/{id}/workspace`，不改变审核/符合性/材料门禁规则。界面不推断未记录依赖，不修改基型 JX-12A，不把旧试验结果改挂新版。首屏总览结构保留。

## RED → GREEN 与重构

- 后端 `python -m pytest backend/tests/test_workspace_api.py -q`：退出码 1，新增 workspace 路由 404；同时局部运行触发全量 80% 门槛，后续局部使用 `--no-cov`、完整运行单独计覆盖。`backend-red.txt`。
- 前端首次运行因组件模块不存在，属于导入失败，不计行为 RED（ui-red.txt）。建立空组件后，同命令指定 WorkspaceJourney/ArtifactPreview 两个测试文件，3 个断言因缺少工作提示、重试和预览按钮失败，退出码 1（ui-behavior-red.txt）。实现后 3 passed（ui-green.txt）。
- 设计预览集成：预览按钮缺失，退出码 1（preview-integration-red.txt）；后续验证打开预览不增加请求。原面板初始化会 POST 检索相似项目，因此不以“页面绝无 POST”作为错误断言。
- 来源字段差异：WorkspaceJourney 测试因未展示来源摘录失败，退出码 1（field-diff-red.txt）；新增字段对比后随完整前端回归通过。
- 持久化预览：空实现抛 NotImplementedError，退出码 1（persistent-preview-red.txt）；实现只创建一次且不覆盖已有副本，GREEN（persistent-preview-green.txt），新增损坏副本保留检查随最终全量通过。
- 重构：Black 格式化后重跑全量；预览焦点 ref 在 effect 内捕获，清除新增的 ref 警告。浏览器原断言“开放”因新增提示出现歧义，改为精确状态文字匹配，保留原业务断言。其余首次浏览器失败为测试定位标签错误，修正为实际可访问名称，非业务 RED。

## 最终验证

| 命令（标记 frontend 的在该目录执行） | 退出码 | 实际结果 / 证据 |
| --- | --- | --- |
| python -m pytest backend/tests -q --cov-report=json:docs/test-evidence/2026-10-20/R2/backend-coverage.json | 0 | 242 passed，1 条既有 TestClient 弃用警告；backend-final.txt |
| npm run test:coverage（frontend） | 0 | 22 文件、70 passed；frontend-coverage.txt |
| npm run build（frontend） | 0 | build-final.txt |
| npm run lint（frontend） | 0 | 10 条既有 effect 警告，无新增警告；lint-final.txt |
| npx playwright test --config playwright.cockpit.config.ts（frontend） | 0 | 8 passed；cockpit-final.txt |
| npx playwright test --config playwright.review.config.ts（frontend） | 0 | 1 passed；modules-final.txt |
| npx playwright test --config playwright.change.config.ts（frontend） | 0 | 1 passed；change-final.txt |
| npx playwright test --config playwright.single-project.config.ts（frontend） | 0 | 3 passed；single-project-final.txt |
| npx playwright test --config playwright.r2.config.ts（frontend） | 0 | 3 passed；browser-final.txt |

浏览器合计 16 个不同检查，不把重复运行累加。新变更与故障场景使用独立数据库/端口；已有维护检查在预览副本备份并恢复。新增预览在 1440×900、1366×768、390×844 检查边界、页面横向溢出、Esc 和焦点；既有菜单/总览尺寸回归继续通过。截图只是排版证据，不代替业务断言。

覆盖：Python app 语句 95.31%、分支 84.84%、综合 92.98%；核心 `backend/app/domain/**` 单独求和：语句 96.81%、分支 90.32%（core-coverage.json，真实断言 ≥90%）。TS 语句 82.57%、分支 65.88%、函数 82.98%、行 87.16%；UI 分支不是领域分支。Python 核心分母排除 app 中非 domain 层；它们仍在 app 全量分母。scripts/** 为启动基础设施，另有回归，不在 app 覆盖范围。前端排除 src/main.tsx 入口、src/test/** 测试设置、**/*.test.ts(x)，样式与浏览器测试不计业务语句；无新增排除以提高数字。无运行时依赖新增。

## 预览恢复事件与持久化修正

更新前 GET /system/backup 返回 503，但 PowerShell 后续停止命令仍执行，这是执行错误。核查时原临时预览文件不可用，原因未确认，无法证明最后保存快照之后的所有操作都被保留。已从上一轮 `2026-10-19/VER-01/preview-state-final.json` 恢复，校验各业务表数量（恢复新增审计除外）；事实见 preview-recovery.json。未对不可恢复的期间补造数据，也不称其全部无损。

随后成功另存当前快照，再迁入 `data/local-preview/workspace.db`。新增 `--workspace` 只在目标不存在时由 source 复制一次，已有副本与损坏副本均不覆盖；持久化目录排除在版本管理外。实际重启后，快照 SHA-256 与全部表数量完全相同（persistent-restart.json）。之后开发启动使用此目录；自动化仍使用临时库。

原 `data/demo.db` SHA-256 保持 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`，原参考文档未改。没有操作用户原 8000/5173 服务，没有部署或外传。

## 限制与后续

未新增真实模型、OCR、工程 CAD/视觉识别或生产权限。变更视图限当前持久化引用与相邻版本，不是任意历史依赖图审计；无记录时明确不能据此断言没有工程影响。材料预览来自所选冻结快照，修复后仍须生成新包。并发、复杂文档/单位泛化、长期负载、任意时点进程终止/系统磁盘故障仍需扩展测试；新增子进程 os._exit(73) 仅证明临时 SQLite 未提交事务回滚，不称完整混沌验证。历史无效 RED 不补造；全 AC 仍不能签署。

启动：项目根目录 `python scripts/run_preview_backend.py --workspace data/local-preview/workspace.db --port 8027`；frontend 下设置 `ZHIYAN_API_TARGET=http://127.0.0.1:8027`，运行 `npm run dev -- --host 127.0.0.1 --port 5181 --strictPort`。不带 --workspace 仍为临时测试副本。
