# FIX-R：版本、解析、保存与验收入口修复

日期：2026-10-22。依据本聊天中的审查结论与用户“开始修复这些问题”授权实施。四项业务缺陷及配套操作/验收入口已修复，受控回归通过；参考原件、日常工作库、人工签核及旧材料包均未由本轮改写。最终实测结果见下文。

## 任务与实际变更

| ID | 关联 O / AC | 实际变更 |
| --- | --- | --- |
| FIX-R1 | O8–O13，AC-08/09/16 | 新增 test_dependencies.py；逐项核对 FMEA 条目及其需求/变型依赖。修订/评分确认/重生成在同一事务失效关联用例与一致性报告；读取也识别升级前漏标记的版本错配。显式重新基线创建新用例版本、保留旧执行；方案包含 FMEA 输入版本并独立复核。 |
| FIX-R2 | O1，AC-03/12 | 比较符按参数匹配片段识别，保留同句重复数值；取力器未定条款保存文本与问题，不默认为需要。固定验证范围内的模糊问题升级高严重度，不能绕过门禁。非法千位分隔符明确拒绝。 |
| FIX-R3 | O12，AC-09/18 | 修订已有比对须提供 expected_revision；证据修改增加 revision。015 显式迁移和不可修改的历史表保存每版测量/结论/证据；迁移仅保留实际存在的当前旧行，不补造更早历史。旧页写入拒绝，完全相同请求可幂等返回。修改使一致性报告待复核。 |
| FIX-R4 | 协同/O13，AC-15/16 | 计算输入绑定 SHA-256；按当前记录/窗口/参与方核对适用性。新增记录使旧指标 stale，保留历史计算及风险接受；禁止接受失效计算，重算后须对新结果独立接受。看板排除失效计算，材料门禁明确阻断待重算。 |
| FIX-R5 | O6/O13，AC-18/20 | 进入设计页只读取现有设计和 FMEA，相似项目由按钮显式计算。材料写入成功后立即保留返回结果；后续读取失败单列提示，只读重试并阻止重复提交。集中校验项目、需求、试验方案、协同与材料关键读取响应。 |
| FIX-R6 | AC-19/21 | 新增 Check-Demo.ps1 与 scripts/check_demo.py：后端全量、独立领域覆盖门禁、修复范围 Python 格式、前端覆盖/lint/build、fixes/cockpit/change 浏览器检查，任一步失败原样退出并保存命令和退出码。无需 Bash、安装依赖或联网。 |

材料合同提升至 O13-1.2；旧快照仍可查看下载，但需按新规则重新生成，不能直接以旧门禁审批。历史库升级不会重置对象、审核或业务数据；旧 JSON 备份仍遵守既有“与当前结构匹配才可恢复”的规则。

## TDD 与中途失败

| 范围 | RED 命令（根目录，前端命令在 frontend 下） | 原始结果与断言 | 后续证据 |
| --- | --- | --- | --- |
| R1 | python -m pytest backend/tests/test_fmea_dependency_regression.py -q --no-cov | 退出 1；3 failed：用例仍 current、基线不升版、旧引用仍计覆盖。r1-red.txt 初次终端中文编码有乱码，保留原输出。 | r1-green.txt：22 passed、退出 0，含既有方案与 DFMEA 回归。 |
| R2 | python -m pytest backend/tests/test_parser_regression.py -q --no-cov | 退出 1；13 failed/4 passed：严格比较、局部符号、重复条款、未定语义、非法分隔符。 | r2-green.txt：35 passed。另 r2-gate-red.txt 为未定条款仍 medium 的有效 RED，最终回归覆盖修复。 |
| R3 | python -m pytest backend/tests/test_sample_revision_regression.py -q --no-cov | 退出 1；3 failed：证据不升版、无版本仍成功、无历史存储能力。 | r3-green.txt：18 passed，含备份恢复。 |
| R4 | python -m pytest backend/tests/test_coordination_freshness.py -q --no-cov | 退出 1；2 failed：缺适用状态、旧接受仍有效。 | r4-green.txt 首次19通过/1失败；新增测试误写计算HTTP200，按既有契约修正为201，保留指标/新接受/门禁全部断言。最终后端全量覆盖。 |
| R5 UI | npx vitest run src/panels/DesignPanel.test.tsx src/panels/PackagePanel.test.tsx src/panels/CoordinationPanel.test.tsx | 初次包含两个测试入口名称错误，不算这两项有效 RED；修正后 r5-ui-red-corrected.txt 为4 failed/18 passed，分别缺显式计算、保存保留/重试与待重算。 | 后续保留生成/审批 payload 与独立缓存查看断言；旧自动加载相似结果测试改为先显式计算再核对缓存重开。 |
| R5 API | npx vitest run src/api.test.ts | r5-api-red.txt：1 failed/6 passed，非法成功响应未拒绝；r5-freshness-red.txt：缺适用状态的协同响应仍被接纳。 | 原请求方法/参数断言保留，通用空对象替身改为各接口有效结构；204 transport 分支改由审核写接口验证，列表204则应拒绝。 |
| R6 | python -m pytest backend/tests/test_check_demo.py -q --no-cov | 退出1，3 failed：缺少门禁步骤、失败不传播、未执行也报成功。 | r6-green-final.txt：4 passed，含完整P0恢复验收。 |

backend-full-first.txt：278通过/3失败，保留全部失败。第一版按整份 FMEA 的 stale 使无关用例失效，改为逐条引用及依赖检查；验收恢复脚本增加先复核工程/FMEA/方案再基线用例的实际步骤，保留覆盖、2.4失败、2.5通过、旧结果、最终 ready/人工审批的全部断言。启动器测试随015迁移更新健康版本，并增加旧014拒绝断言。

final-check 首次统一执行：后端285通过，核心门禁及Python格式通过，前端124通过/1失败后停止，未继续后续步骤。期间需求页存在本轮外的更新，旧 App 驳回测试只打开新抽屉、未提交；补充填写原因和显式提交后，32项相关测试通过。未回退需求页实现。原始失败日志均保留，没有 skip、删断言或失败转成功。

## 运行与证据

根目录执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\Check-Demo.ps1`，或 `python scripts/check_demo.py`。`--skip-e2e` 仅供快速检查，不表示完成浏览器验收。自动生成独立日期/时间证据目录；本轮最终执行使用 `python scripts/check_demo.py --evidence-dir docs/test-evidence/2026-10-22/FIX-R/final-check-2`。

浏览器专项使用独立合成库；配置直接运行时默认8046/5196、8049/5199、8047/5197，统一入口则为每套件自动分配两个可用本机端口。拒绝复用正在运行的服务器，保留现有实例。截图/下载改用本轮 ZHIYAN_EVIDENCE_DIR；原套件无指定时进入 test-results/screenshots。运行中新增的UI-X测试也补上环境变量输出路径，保留其原默认目录和测试逻辑。

final-check-2的后端、核心覆盖、Python格式、前端、lint、build、fixes均通过，cockpit因8049端口被另一实例占用而未启动；保留失败原文，未结束他人进程。新增端口分配回归r6-ports-red.txt（1 failed，返回重复0端口）→r6-ports-green.txt（4 passed）；统一入口使用可用端口，三个配置共享端口校验。支持 `--only` 仅重跑指定步骤，控制台与日志明确标识分项，不宣称该次为全量。

browser-check中fixes4、cockpit18通过，change首次因仍寻找UI-V已取消的长alert失败。改为检查“当前材料准备”的非零阻断、审批不可用、真实后端draft和COVERAGE_INCOMPLETE，旧版本/覆盖/历史结果断言全部保留；change-final单项通过。未修改产品门禁来适应旧选择器。

日常启动仍为 Start-Demo.cmd。已有服务须正常输入 stop 完成退出备份，再重新启动以加载后端代码及015迁移；前端刷新不能替代后端重启。未自动确认、审批、生成或重置日常数据。

## 覆盖与边界

Python app 全量语句/分支报告与 domain/** 独立分支门禁分别保存；核心分支≥90%、语句≥80%。TypeScript仍独立统计src，main.tsx（启动装配）、src/test/**（测试支持）、测试文件沿用排除，无新增业务排除。e2e-fixes只从Vitest发现排除，本身不在src业务覆盖分母中。

Python格式门禁列出本轮修复模块/领域文件、新检查器和回归测试；未把旧版未格式化的其他模块虚称为全仓格式验收。整体大服务文件未进行无关拆分；本轮只抽取FMEA依赖与前端响应校验。未做任意依赖图、复杂文档泛化、长期负载或生产认证；原AC边界和历史RED缺口继续保留。

## 最终实测结果

| 检查 | 实际结果 | 原始证据 |
| --- | --- | --- |
| 后端业务全量 | 285 passed，退出0；1条既有Starlette/httpx弃用提示 | final-check-2/backend.txt |
| 新检查器（端口调整后） | 4 passed，退出0；其中3项已包含在上述285中，不相加伪称新一轮286全量 | r6-ports-green.txt |
| Python覆盖 | app语句5475/5741=95.37%；核心领域语句1580/1630=96.93%，分支510/562=90.75%，独立门禁通过 | final-check-2/coverage-backend.json、core-coverage.txt |
| 前端全量与覆盖 | 22文件、125项通过；语句1827/2116=86.34%、分支1440/2008=71.71%、函数86.90%、行90.31% | final-check-2/frontend.txt |
| Python格式、前端lint/build | 最终均退出0，lint零警告；格式范围20路径见命令 | last-check/*.txt |
| 浏览器修复专项 | 4 passed，退出0 | browser-check/browser-fixes.txt |
| 浏览器工作台 | 18 passed，退出0，含本轮外新增需求审核工作流回归；不据此代签其任务完成 | browser-check/browser-cockpit.txt |
| 浏览器2600→2800 | 1 passed，退出0 | change-final/browser-change.txt |

浏览器共23个不同检查，早期重复运行不累计。Playwright输出的NO_COLOR/FORCE_COLOR提示属于运行环境提示，无未解释业务失败。最终检查器端口调整仅涉及测试工具/浏览器配置；后端app覆盖数据来自最后一次285全量，未追认为调整后又执行过全量。所有必需门禁均取得通过证据，分项执行事实与两次统一执行的失败阶段保留。

已实际查看设计页和变更阻断材料页截图；截图仅用于展示可读性，不能代替上述业务断言。源演示库SHA-256仍为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`，与修复前记录相同。日常工作库/恢复指针未由本轮调用，未自动审核日常对象。

结论仅覆盖FIX-R1–R6所列行为及受控主线，不宣称完整P0/AC-01–AC-21、所有文档泛化或任意依赖图均已验收。
