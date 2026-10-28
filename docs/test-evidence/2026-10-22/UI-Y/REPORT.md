# UI-Y：统一交互、业务状态与说明复核

日期2026-10-22。关联O1–O13适用模块、AC-04/07/09/18/19/20/21的受控范围。用户要求检查类似需求审核反馈的问题，统一核对后再按操作说明试用。先读取开发计划P0/AC与AGENTS，再核对UI-X、FIX-R完成记录、当前源码、日常只读页面和独立测试库。

## 发现与修复

| 问题 | 实现及验收行为 |
| --- | --- |
| 工程决策、设计/FMEA、试验、样件、一致性、协同多处POST/PATCH成功后GET失败，被笼统显示为失败 | 抽取useSavedRefresh与独立提示组件，明确“已保存，但页面刷新失败”；暂停重复写入，只重试原GET。成功读取后更新真实状态及动作。取消/关闭不是重新提交，读失败不伪造未保存或自动审核 |
| 已审核工程版本仍显示驳回等重复审核动作 | 当前版本完成审核后显示只读说明，留存版本/依据/审核记录；内容调整通过重新生成的新版本再审核。真正不适用记录只读，默认收起但可展开 |
| DFMEA改了输入但未保存时，可确认后台旧评分；也可点击文档确认 | 未保存修改明确提示，先保存再确认评分/文档。RPN仍由后端已确认S/O/D计算，不将输入框草稿当成保存值 |
| 保存一行DFMEA评分会覆盖其他行未保存的输入 | 按条目ID与revision保留其他未变版本的草稿，只重置本次已保存行；后台版本不同则重新读取，不把旧草稿绑定新版本 |
| 当前工程记录中三个基型各有V-01等同名编号，原列表未区分 | 只读接口补真实base_display_code，列表/详情展示基型，增加基型筛选；稳定ID、版本和审核分开。字段只加在展示模型，不加入版本快照，不更改历史或写审计，后台测试验证读前后数据库备份hash一致 |
| 操作说明仍写首次直接查看相似项目、旧DFMEA/材料版本及过期进度 | 对齐显式计算入口、评分操作顺序、基型选择、只读审核及恢复读取。更新实际保存状态，说明新后台代码需要正常stop/启动；不自动替用户处理业务待办 |

未把持续查阅的设计、试验和检查报告从页面删除。需求审核属于待办队列；工程成果还承担引用、比对和追溯，确认后保留结果及状态，收起重复动作。历史材料、审核和不适用工程对象均保留。

## 逐模块审查

| 模块 | 核对重点与结论 |
| --- | --- |
| 项目总览 | 模块入口与实时状态可达，展示覆盖与执行分开；不把当前60%或草稿材料显示为已就绪 |
| 协议解析与澄清 | 真实文本/规则边界、问题关闭/重开证据和反馈保留；不将填充样例当成新项目重置 |
| 需求清单 | UI-X四视图、0待办可查看13条全部需求，来源/版本/审核记录、修订与失败反馈保留 |
| 型谱选型与变型 | 计算结果与选用动作分开，工程版本按基型区分；已完成审核只读、历史展开可查 |
| 设计成果 | 显式相似项目计算，评审摘要/预览；DFMEA保存、评分确认、文档确认顺序，其他行草稿保留 |
| 试验验证与追溯 | 方案/用例/执行独立，stale与审核并列；确认、重新基线、记录执行后的读取恢复不重复写入 |
| 样件检验 | 保存基准单表、文件/视觉模式/确认保留；登记、上传、比对、确认的保存与GET失败分开 |
| 一致性检测 | 报告审核、完整冲突证据/关闭档案保留；运行/审核/处置后的读取恢复只GET |
| 协同风险 | 新沟通记录需重算、旧接受不冒充当前；创建/计算/接受风险的GET恢复及既有导入反馈保留 |
| 评审材料 | 当前准备与快照查看分工、真实门禁、历史下载；旧规则草稿需重新生成，不能自动审批 |
| 系统设置 | 实际运行版本、备份/恢复入口与状态保留，未在日常点击恢复或重置 |
| 导航/说明 | 完整侧栏与当前工作一致，关键入口与说明对齐；需求0待办、工程多基型和当前待复核有明确说明 |

## TDD与单项证据

| 阶段 | 命令与结果 |
| --- | --- |
| 六模块反馈及未保存评分RED | frontend执行 `npx vitest run src/panels/DesignPanel.test.tsx src/panels/TestingPanel.test.tsx src/panels/ConsistencyPanel.test.tsx src/panels/SamplesPanel.test.tsx src/panels/CoordinationPanel.test.tsx src/components/EngineeringRecords.test.tsx`，退出1，7失败/41通过，缺少明确已保存提示、只读重试/锁定及评分确认保护；feedback-red.txt |
| GREEN | 同命令退出0，48通过；feedback-green.txt。后续新增用例包含在最终全量135中，不叠加计数 |
| 多行草稿RED/GREEN | `npx vitest run src/panels/DesignPanel.test.tsx`，退出1，1失败/7通过，第二行9被覆盖成7；修复后退出0，8通过；fmea-draft-red/green.txt |
| 工程历史RED/GREEN | `npx vitest run src/components/EngineeringRecords.test.tsx`，退出1，1失败/5通过（历史与当前同名动作混列）；修复后退出0，6通过；engineering-history-red/green.txt |
| 基型展示后端RED/GREEN | 根目录 `python -m pytest backend/tests/test_engineering_versions.py -q --no-cov -k read_models`，有效RED退出1，缺少base_display_code。最初测试误用201作为分析返回码，先修正为既有200再取得缺失行为RED，原setup日志保留。最终整个test_engineering_versions.py退出0，9通过；engineering-base-red-setup/red/green.txt |
| 基型筛选前端RED/GREEN | 工程组件测试退出1，1失败/6通过，缺少基型筛选；修复后退出0，7通过；engineering-base-ui-red/green.txt |
| 浏览器专项 | `ZHIYAN_UIX_SUITE=cockpit`、设置本轮ZHIYAN_EVIDENCE_DIR，`npx playwright test --config playwright.ui-x.config.ts saved-feedback.spec.ts`，退出0，1通过；feedback-browser.txt。真实提交审核后注入GET503，恢复仅GET、确认次数1；多行评分、两基型筛选及审核后只读、手机/焦点、隔离库finally恢复均核验 |

初次lint有组件文件同时导出hook的Fast Refresh警告，保留lint-initial.txt；将hook移至src/useSavedRefresh.ts，提示组件单独导出，最终零警告，未禁用规则。新增代码无业务覆盖排除或外部依赖。

## 统一验收结果

根目录 `python scripts/check_demo.py --evidence-dir docs/test-evidence/2026-10-22/UI-Y/final-check-2` **退出0，所有计划步骤依次通过**。

| 检查 | 本轮实际结果 | 证据 |
| --- | --- | --- |
| 后端全量 | 287 passed，退出0，1条既有Starlette/httpx弃用提示 | final-check-2/backend.txt |
| Python app语句 | 5479/5745 = 95.37% | final-check-2/coverage-backend.json |
| 核心领域独立门禁 | 语句1580/1630 = 96.93%；分支510/562 = 90.75%，通过 | final-check-2/core-coverage.txt |
| Python格式 | 检查器既有20路径通过；本次工程版本模块/测试额外black --check两路径通过 | final-check-2/python-format.txt、python-format-engineering.txt |
| 前端全量 | 22文件，135 passed，退出0 | final-check-2/frontend.txt |
| TS覆盖 | 语句1907/2221 = 85.86%，分支1591/2182 = 72.91%，函数87.22%，行90.85% | 同上 |
| lint/build | 退出0，lint零警告，TypeScript/Vite构建成功 | final-check-2/lint.txt、build.txt |
| 浏览器修复专项 | 4 passed，退出0 | final-check-2/browser-fixes.txt |
| 浏览器工作台 | 19 passed，退出0 | final-check-2/browser-cockpit.txt |
| 浏览器变更闭环 | 1 passed，退出0，2600→2800、派生要求、旧结果/失效及材料阻断核验 | final-check-2/browser-change.txt |
| 九模块成果走查 | 1 passed，退出0 | browser-review.txt |
| R2工作区 | 5 passed，退出0，仅workspace.spec.ts | browser-workspace.txt |

浏览器共30个不同检查，不叠加专项、重跑、日常只读或历史数量；未运行整个R2浏览器套件。额外两套从frontend以playwright.ui-x.config.ts运行，ZHIYAN_UIX_SUITE分别review、workspace，后者限定workspace.spec.ts；ZHIYAN_EVIDENCE_DIR指向本目录browser。检查器各套使用可用独立端口、临时SQLite；额外套件端口/输出目录独立。

TS排除维持src/main.tsx（启动装配）、src/test/**（测试支持）、测试本身；Python核心仍为既有domain/**口径，不将UI分支门槛充当核心分支90%或宣称全仓Python格式已验收。

首次统一执行final-check的后端286、核心与格式通过；前端133通过/1失败后按规则停止，没有继续。该阶段仍在增补工程历史测试，前端阶段先读到新断言、实现尚未更新，原日志完整保留。随后完成工程历史/基型修复并冻结代码，重新从完整后端开始执行final-check-2，全部通过；未跳过失败测试或弱化断言。

已查看engineering-base-filter.png、saved-review-readback-failure.png等真实截图。截图仅证明展示可读性；业务结论取上述断言与API结果，故障画面中的旧草案显示为尚未刷新状态，已保存提示、锁定与GET恢复同时存在。

## 日常只读状态及交付说明

根目录 `node docs/test-evidence/2026-10-22/UI-Y/live-check.cjs` 退出0，11模块均可打开，模块错误提示/页面异常/外网请求为0。脚本禁止一切非GET/HEAD/OPTIONS的API请求，实际尝试写请求为0；未用日常数据演练审核、修订、生成或恢复。live-check.json及live-*截图留档。

日常实际保存状态见live-state.json：13条需求已确认；工程记录17项，按只读原库候选ID映射JX-12A9项、JX-12B3项、JX-12C5项，均为当前适用；它们不是本次删除或合并的历史。DFMEA V14待复核，方案V2依据变化，有效覆盖3/5（60%）；MP-P01-003为旧规则草稿，需重新生成。待办和旧材料不是API保存失败，不自动确认或消除。

日常服务器已为SQLite015，但没有自动重启加载本次新增的基型展示字段；旧响应兼容，前端显示“未记录基型”而不猜测。新增字段及筛选在隔离新后端验证通过。用户开始试用前应在原启动窗口输入stop完成备份并停止，再双击Start-Demo.cmd；仅刷新前端不能加载后台更新。未擅自结束日常实例或覆盖工作副本。

原data/demo.db SHA-256仍为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`；此为原库校验，日常无写结论另见脚本请求记录。操作说明、README、文档目录、任务、验收、开发日志与决策已同步。

结论：在所列受控主线和当前排练说明范围，未发现尚未修复的软件阻塞，可正常重启后开始完整试用；实际业务待复核仍需按依赖顺序处理。未签全部P0/AC，不证明任意复杂文档/依赖图、长期压力、真实工程性能、真实认证或生产级混沌。旧测试与恢复事实继续保留。
