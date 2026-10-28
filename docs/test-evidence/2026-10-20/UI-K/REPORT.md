# UI-K 导航收敛、字体与色彩（2026-10-20）

## 结果与设计决定

关联 AC-20/21；沿用 R2 真实版本、审核、失效及门禁合同，没有新增通过规则。

- 移除每个模块重复的九阶段导航和静态输入/工作/输出卡。九个模块不是必须依次完成的九步向导，系统允许返回上游并随时使用贯穿引擎。
- 侧栏统一为协议解析、需求、型谱、设计、试验、样件、一致性、协同、评审材料。材料作为末尾交付入口，不再出现在贯穿引擎之前。
- 模块顶部仅保留当前工作、后端待办/失效/登记数量、刷新和相关下一步。下一步从同一个模块定义取序，仅导航，不代替审核或前置条件判定。材料页回到总览，不强制再次进入一致性。
- 变更影响入口集中在需求清单；下游对象定位、返回、版本与字段对比保留。
- 正文统一 14px、输入 14px、模块标题 18px；保留侧栏 14–15px。系统本地字体、蓝灰背景、深色文本、统一表格/表单/状态层次；抽样五组正文/标签/辅助/状态颜色的对比值为 4.54–12.17，不称完整可访问性认证。
- 首页事实与状态文字适度提高；短窗口压缩多余边距，按钮文字简化且保留完整可访问名称，不通过缩小字号、放宽断言或隐藏有效内容解决拥挤。
- cockpit 和 review 走查改为独立临时库及专用端口，API 使用对应代理；后续验证不复用日常演示进度。

## RED → GREEN → REFACTOR

1. 新增侧栏顺序断言与“无重复阶段导航 / 相关下一步”断言。
2. `npm test -- src/components/WorkspaceJourney.test.tsx src/App.test.tsx`（frontend）退出码 1，2 个行为测试因旧侧栏顺序及仍有完整阶段导航失败（red.txt）。
3. 实现导航与上下文重排；首轮 GREEN 有一个精确文字匹配歧义（待复核标签与表格状态同名），改为在 TC-007 行内断言，保留“已确认且失效同显”的业务要求。全部前端回归随后通过。
4. 静态路径卡原回归按用户新要求更新为简洁上下文及下一步，不保留已撤销设计的断言。
5. 字号调整后真实布局检查暴露菜单/追溯/智能体卡片拥挤；用边距、页脚留白和短按钮标签修复，保留字号、同屏和内容无内部遮挡断言。layout-second / isolated 等输出保留诊断，最终通过见 layout-final / cockpit-final。
6. 常驻 Vite 曾缓存旧导航模块，产生 nextModule 导出缺失；仅核验并重启前端服务，后端持续运行。后续浏览器验证使用新启的隔离服务器，避免缓存与数据共享。最早的旧 cockpit 配置可能为页面相似检索记录审计，已修正隔离；没有主动修订、审批或重置日常业务数据。

## 实际命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| npm run test:coverage（frontend） | 0 | 22 文件、71 passed；frontend-final.txt |
| npm run build（frontend） | 0 | build-final.txt |
| npm run lint（frontend） | 0 | 10 条既有 effect 警告，无新增错误；lint-final.txt |
| npx playwright test --config playwright.cockpit.config.ts（frontend） | 0 | 8 passed；cockpit-final.txt |
| npx playwright test --config playwright.r2.config.ts（frontend） | 0 | 4 passed；workspace-final.txt |
| npx playwright test --config playwright.review.config.ts（frontend） | 0 | 1 passed；review-final.txt |
| npx playwright test --config playwright.single-project.config.ts（frontend） | 0 | 3 passed；single-project-final.txt |
| npx playwright test --config playwright.change.config.ts（frontend） | 0 | 1 passed；change-final.txt |
| python -m pytest backend/tests/test_acceptance_p0.py backend/tests/test_delivery_integrity.py --no-cov -q | 0 | 5 passed、1 条既有 TestClient 弃用警告；business-validation.txt |

浏览器合计 **17 个不同检查**，布局迭代和最后颜色复核的重复 4 项不累加。常用桌面 1920×1080、1440×900、1366×768 的主要总览同屏且无内部遮挡；1280×720 菜单完整；390px 窄屏可操作且无页面横向溢出。九个模块只显示一个工作上下文，导航顺序与下一步共用定义，材料能返回总览。变更影响、文件归档、版本、故障重试和四类预览继续通过。

TS 本轮覆盖：语句 82.67%、分支 65.82%、函数 83.30%、行 87.16%。门槛和排除未改：main.tsx 入口、src/test/**、*.test.ts(x) 不计，CSS/浏览器不计业务语句；前端没有独立业务领域层，UI 分支不是领域分支。后端代码未改，本轮只复演 5 个关键验收，不重算 Python 覆盖；242 全量与核心分支 90.32% 是 R2 那次结果，不冒称本轮重跑。

## 完整演示与就绪状态

受控本地流程能从协议/需求、工程决策、设计/FMEA、方案/用例/执行、样件和冲突处置推进至材料快照/审批；2600→2800、固定分母与旧执行保留在关键验收及浏览器变更场景复演。模型/语义/视觉仍为明确 rule/mock/manual，不宣称真实台架或生产能力。

本轮日常预览只读探测（live-state.json）：13 条需求已确认、固定验证覆盖 100%，但设计评审/DFMEA needs_reconfirmation=true，材料包 requires_regeneration=true。这表示功能可演示，当前保存数据尚须复核并生成新包，不能称当前全部已就绪或直接可提交；没有为展示清除这些状态。

任意依赖图、复杂文档/单位泛化、长期可靠性仍未完整验收。仍不签署 AC-01–AC-21 全通过。原 data/demo.db 哈希保持 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。参考原件、已有验收证据和业务库未被重置。

## 启动与资料

日常后端：`python scripts/run_preview_backend.py --workspace data/local-preview/workspace.db --port 8027`。frontend 设置 ZHIYAN_API_TARGET=http://127.0.0.1:8027，运行 `npm run dev -- --host 127.0.0.1 --port 5181 --strictPort`。本轮已重启前端并继续提供本地预览。

当前说明、演示指南、任务表与验收复核同步为 UI-K，历史 R2/清理报告保留原结果。样式截图、原始输出、颜色抽样与日常状态在本目录。
