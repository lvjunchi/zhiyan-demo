# R1 · 按序完善与受控验收（2026-10-19）

任务：GAP-01 → GAP-02 → VER-01 → UX-01/02 → ENG-01 首轮；关联 O1–O4/O6–O13、AC-02/07–11/16–21。用户授权按已列优先级实现，不仅更新文档。未联网、未收费、未部署、未改参考原件或原演示库。

## 实际变更

- GAP-01：013 迁移为来源原件建立不可更新/删除的字节归档；新导入可同时保存文件名/类型/大小/SHA-256，后台重新校验格式与字节，标明正文是否经人工调整；原文与原件分开。下载返回附件与 nosniff；不同文档版本互不覆盖，重复版本拒绝。材料显式选附件时纳入真实原件及正文，备份含字节。旧正文记录明确缺原件。本轮直接字节往返测试覆盖 TXT/PDF，既有 DOCX 提取测试通过；不称复杂 DOCX 泛化评估。
- GAP-02：手工录入的同义参数也通过统一字段映射保留复用决策版本引用；恢复时审核状态必须与本版本实际审核留痕一致，不能只改状态。
- GAP-02：014 迁移为变型点/复用决策增加独立 revision、review_status、具体版本依赖、不可更新/删除的历史快照与审核记录。自动版本 draft，确认校验 expected_revision、当前有效性和上游确认；旧审核不迁移到新版。迁移只保留当时当前行并标注更早历史缺失；首次重新分析即使参数相同，也须建立带当前依据的新版本。非适用对象保留历史标记，避免旧退役决策永久阻塞新包。
- 设计/FMEA 对实际使用的变型记录 ID+revision；需求修订、工程失效、审计在事务内。材料 O13-1.1 实际检查适用的工程决策，draft/stale/rejected 不可就绪；旧 O13-1.0 包保留原状态与 ZIP，标为旧门禁并阻止按新合同审批。
- UX-01：需求编号/参数/目标搜索、审核与有效性筛选，保留总量，不改变后端五条分母；来源位置/摘录/正文/原件下载、任意两份已有 revision 的字段对比。审核刷新不再覆盖未保存修订草稿。
- UX-02：材料冻结快照的阻塞项有对象/版本、模块跳转与可见记录高亮；未在当前列表展示的对象明确提示，不谎称定位成功。返回材料后生成新包复检，旧快照不自动改变。
- ENG-01：公共标签与错误/时间工具分离为 uiSupport.ts，组件文件只导出组件；共享字阶和新证据区间距，延续菜单/同屏约束。24 条 lint warning 降至 10，未禁用规则。Black 24.4.2 格式化并核对本轮 18 个 Python 文件，开发工具锁在 requirements-dev.txt；无新运行时依赖，不等同完整 Python 静态分析。

## RED / 诊断 / GREEN 的实际证据

| 任务 | 实际 RED / 问题 | 最终验证 |
| --- | --- | --- |
| GAP-01 | backend test_source_archive.py 退出 1，8 failed：原件缺失/非法原件被忽略；前端新导入原件断言退出 1 | 字节下载/重启/新旧版本/非法输入回滚/包内附件与冻结/备份恢复；ParsingPanel 新原件导入；最终全量通过 |
| GAP-02 初版 | 最初 test_engineering_versions.py helper 命名 setup，被 pytest 当 xUnit 钩子；3 errors 不是有效行为 RED。实现后才改名，不能补造最初版本实现 RED | 最早独立版本实现存在 TDD 证据缺口，AC-21 不宣称全通过 |
| GAP-02 后续 | red-revision-integrity：无匹配历史的 revision 99 被恢复；red-gates-and-integrity：工程驳回未阻塞；red-domain-gate：4 failed/6 passed；red-malformed-snapshot：JSON 非对象引起服务器异常；red-manual-reference 与 red-review-integrity 分别复现遗漏引用和无留痕确认被接受 | 工程版本专项（含手工引用、审核留痕一致性）、领域门禁参数化、整库回滚与完整性拒绝；最终全量通过 |
| GAP-02 界面 | 缺 EngineeringRecords 组件，Vitest 退出 1 | 当前版本审核、历史保留、失败意见保留；浏览器真实 API 复核 |
| UX-01 | 搜索/筛选入口缺失，Vitest 退出 1 | 需求列表与来源/版本测试、浏览器筛选和原始缺失说明 |
| UX-02 | 缺 MaterialBlockers；旧门禁仍显示可提交，Vitest 退出 1 | 实际对象 ID/revision 跳转、无依据时无假链接、旧门禁不显示就绪或审批入口 |
| ENG-01 | 独立审核刷新后修订草稿被覆盖（最终有效夹具使用 JSON 深拷贝），退出 1 | 草稿保留、全前端回归、构建与 lint |
| VER-01 旧包 | red-legacy-gate：旧门禁快照仍可批准，退出 1 | 当前合同守卫/明确历史标签，不修改旧包字节 |

诊断留存：source reviewed_text_changed 最初返回 SQLite 1 而非 JSON true，修正序列化；前端 mock 缺 ApiError 导出，改为保留原模块；筛选项文本与状态标签重复，区分筛选显示并精确定位；新增来源 GET 后更新“只加载当前模块”的请求序列断言，没有移除检查。浏览器首次发现未变化旧记录不触发新快照，补 needs_capture 后真正生成当前依据版本。RTL exact 选项不受类型支持、确认 payload 少 comment 的构建错误已修正。所有诊断未通过 skip/删断言/吞错误换绿。

## 最终命令与结果

命令在根目录执行 Python、在 frontend 执行 npm/npx。专项数均包含在全量，不叠加。

| 命令 | 实际结果 / 文件 |
| --- | --- |
| python -m pytest backend/tests -q | 237 passed，退出 0；backend-final.txt；1 条既有 testclient 弃用警告 |
| npx vitest run --coverage | 64 passed / 19 文件，退出 0；frontend-final.txt |
| npm run lint | 退出 0；10 条剩余 effect warning；../ENG-01/lint-final.txt |
| npm run build | 退出 0；build-final.txt |
| python -m black --check（python-format.txt 所列 18 文件） | 退出 0；../ENG-01/python-format-check.txt，未关闭业务检查 |
| npx --offline playwright test --config playwright.cockpit.config.ts | 7 passed；browser-final.txt；总览/字号/备份恢复/故障反馈/新原件/来源对比/工程审核/材料高亮 |
| npx --offline playwright test --config playwright.review.config.ts | 1 passed；modules-browser.txt；九模块 |
| npx --offline playwright test --config playwright.change.config.ts | 1 passed；change-browser.txt；独立临时库 |
| npx --offline playwright test --config playwright.single-project.config.ts | 3 passed；flow-browser.txt；独立临时库 |

Edge 合计 12 条；未修改断言去接受业务错误。报告数据不是历史各轮相加。Black 后完整 Python 回归通过；最后前端类型/标签调整后组件、构建与相关浏览器配置通过。

## 覆盖率与排除

- Python 全业务语句 95.25%、分支 84.49%、综合 92.89%，backend-coverage.json。无业务路径人为排除。
- 核心 domain/**：语句 96.81%、分支 90.32%；core-coverage.json 逐路径列明。API/适配器/持久化/服务编排仍在全业务报告，不混当纯领域分支。
- TS 语句 83.05%、分支 68.25%、函数 85.11%、行 87.07%；排除 main.tsx 入口、src/test/** 与测试文件，保留原覆盖门禁。前端无独立业务判定层，UI 分支不是领域分支。

## 验证边界与保留数据

本轮包括单场景 80→60→80→100、TC-007 旧 2600 加载 invalid/2800+2.4 fail/2800+2.5 pass、旧运行保留、旧库迁移不重号、本地并发修改/导出源派生不混版本、新工程门禁与原件哈希。已有确定性故障注入随全量重跑。未执行长期高负载、分布式网络故障、系统级磁盘故障、进程强杀、真实台架或模型；复杂文档/单位泛化与任意依赖图仍需专项，不称全 AC 或生产级混沌认证。

维护备份仅支持当前匹配的 schema，不承诺跨版本直接恢复；旧结构会明确拒绝。历史原文件和更早工程版本不能补造；旧材料为历史快照，必须重新生成新门禁。当前工程审核是本地演示身份，不是认证/RBAC。

data/demo.db SHA-256 保持 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。全部写测试在独立库/临时预览；原参考资料未修改。为加载最终后端代码，先备份预览，再重启并恢复同一预览状态，原 UUID/数据保留，仅追加恢复审计；未停止 8000/5173 日常服务。

启动：python scripts/run_preview_backend.py --port 8027；frontend 设 ZHIYAN_API_TARGET=http://127.0.0.1:8027，npm run dev -- --host 127.0.0.1 --port 5181 --strictPort。预览 http://127.0.0.1:5181/。常驻原库数据不重置，临时预览退出不回写原库。
