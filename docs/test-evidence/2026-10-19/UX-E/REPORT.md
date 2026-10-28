# UX-E 本轮验收记录

任务：单项目工业工作台改版、系统设置、移出常驻角色标签，并补关键业务缺口。关联 O1、O7–O8、O10–O13，AC-02/04/07/09/19/20/21。本报告仅覆盖本轮专项，不等于所有 AC 全面重验收。

实际完成：

- 总览：本地机械结构示意、当前动力/挡位要求、四项实际项目指标；保留三阶段成果讲解、两引擎和材料包主线。申报目标仍在辅助证据中单列为待实测。
- 全局视觉：统一导航、顶栏、表格、表单、按钮、留白和状态；1920/1440/1366/390px 浏览器检查无页面横向溢出。
- 系统设置：浏览器保存舒适/紧凑密度与减少动效；保存失败反馈；真实健康接口探测，错误不显示为已连接；审核身份、合成数据、规则/模拟边界集中说明。无新增认证能力。
- 文档：UTF-8 TXT、文本 PDF、DOCX 的本地文本提取预览；导入前人工核对。保留 TXT 行/PDF 页/DOCX 段落位置；拒绝未知格式、超 8 MiB、坏编码、坏文件和纯扫描内容。不保存原始二进制文件。
- 固定派生合同：B-003 变更在同一事务更新独立 C-002 revision 与值，保留关联和旧审核；异常整体回滚。JX-12A 未修改。
- 设计复核：迁移 012 增加设计评审/DFMEA current/stale；需求变更后自动失效、旧确认保留；一致性报告呈现文档版本冲突，材料包受复核门禁约束。

## RED、GREEN 与重构验证

| 检查 | 实际命令 | 结果/证据 |
| --- | --- | --- |
| 派生和设计失效 RED | `python -m pytest backend/tests/test_change_propagation.py -q --no-cov` | 退出 1，两项失败；red-change.txt |
| 同项 GREEN | 同上 | 退出 0，两项通过；green-change.txt |
| 失效文档进入一致性报告 RED | 同上，新增 version 对象断言 | 退出 1；red-stale-report.txt；最终全量通过 |
| 文件入口 RED | `python -m pytest backend/tests/test_document_text.py -q --no-cov` | 清理参数化测试 ID 后退出 1，8 项因缺接口失败；red-document-clean.txt |
| 文件入口 GREEN | 同上 | 退出 0，8 项通过；green-document.txt |
| 设置 RED | `npx vitest run src/panels/SettingsPanel.test.tsx` | 控制台退出 1，缺 SettingsPanel；随后保存/重载/失败反馈两项通过 |
| 指标 RED | `npx vitest run src/panels/OverviewPanel.test.tsx` | 退出 1，缺项目实时指标区域；red-metrics.txt；最终全量通过 |
| 文件预览 RED | `npx vitest run src/panels/ParsingPanel.test.tsx` | 退出 1，缺文件输入；red-file-preview.txt；最终全量通过 |
| 后端全量 | `python -m pytest backend/tests -q` | 退出 0，197 passed；backend-tests.txt |
| 前端全量/重构 | `npx vitest run --coverage` | 退出 0，50 passed；frontend-tests-final.txt |
| 前端 lint | `npm run lint` | 退出 0，无错误；24 条 Fast Refresh/effect 类警告保留，见 lint.txt |
| 构建 | `npm run build` | 退出 0；build-final.txt |
| 浏览器首页/设置 | `npx --offline playwright test --config playwright.cockpit.config.ts` | 退出 0，2 passed；browser-tests-final.txt |
| 三条流程回归 | `npx --offline playwright test --config playwright.single-project.config.ts` | 退出 0，3 passed；flow-tests-final.txt |
| 九业务模块走查 | `npx --offline playwright test --config playwright.review.config.ts` | 退出 0，1 passed；walkthrough.txt；标题改名后的结果见 walkthrough-final.txt |
| 浏览器变更闭环 | `npx --offline playwright test --config playwright.change.config.ts` | 退出 0，1 passed；change-browser-final.txt |

浏览器变更专项实际点击修订 2600→2800，验证 C-002 自动更新且为草案、设计/DFMEA 待复核、100%→80% 覆盖、新材料包 draft 和旧执行记录逐项保留。完整恢复至 ready/human_approved 的路径由后端 test_acceptance_p0 验证；本轮并未声称浏览器操作了完整恢复和批准。

回归诊断：初次全量后端有 5 项旧测试依赖“源参数变更后派生数值不变”的旧行为。测试现先断言同步成功，再显式输入错误的独立派生值以继续检验真实参数矛盾、风险接受、关闭/重开；材料包恢复测试新增设计独立复核，未降低原门禁断言。浏览器初次并行共用产物目录导致 trace 文件竞争，另有模糊标签定位；现各配置隔离目录且精确定位，原业务断言保留。文件参数化测试初次默认 ID 展开大字节串造成路径错误，现使用短 ID，重跑产生干净 RED；未保留该无效大日志。曾在 frontend 目录执行 coverage JSON 得到 No data to report，已在根目录从同一次测试覆盖数据正确生成报告。

## 覆盖率与排除

- Python 全业务语句 95.06%，分支 84.07%，语句+分支综合 92.69%；backend-coverage.json。
- Python 核心领域（backend/app/domain/**）语句 96.66%，分支 90.04%；core-coverage.json 逐路径列明。API、schema、持久化、适配器和服务编排另在全量报告，未当作领域分支混算；无业务代码人为排除。
- TypeScript 语句 87.39%，分支 73.05%，函数 90.02%，行 89.94%。排除 src/main.tsx（入口装配）、src/test/** 和测试文件；不存在前端重复业务判定层，不把 UI 分支称作核心领域 ≥90%。
- Python 语法检查 `python -m compileall -q backend/app` 通过；本轮未引入或宣称完成独立 Python 静态 lint 流程。后端保留一条既有 FastAPI/Starlette testclient 弃用警告。

## 数据保护和限制

原始参考文档只读。data/demo.db SHA-256 前后均为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`；P02 历史记录未删除。全部浏览器写操作使用临时备份或独立测试库，未重置用户数据库，未停止用户 8000/5173 服务。迁移 012 在测试/预览副本中验证；日常后端需正常重启后才能加载新代码并执行未应用迁移。

未宣称全部 AC 已验收：复杂版面解析准确性、任意依赖类型的全图传播及全量验收矩阵仍需继续审计；此轮重点为固定源/派生合同与设计文档复核。文件原件二进制未归档，无 OCR；无生产权限、真实模型/台架/外部系统连接。完整 O5/O5′、供应商指派/批次归集仍不纳入 P0。申报指标未经实测不称达标。

## 查看

预览 `http://127.0.0.1:5181/`。项目根目录运行 `python scripts/run_preview_backend.py --port 8027`；另一个 PowerShell 在 frontend 中设置 `$env:ZHIYAN_API_TARGET='http://127.0.0.1:8027'` 后执行 `npm run dev -- --host 127.0.0.1 --port 5181 --strictPort`。预览操作保存在临时副本，停止后不回写演示原库。
