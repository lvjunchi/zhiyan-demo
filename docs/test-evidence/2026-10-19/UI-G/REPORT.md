# UI-G · 工业工作区、数据维护与故障验证

任务关联：O1–O13 展示、AC-08/09/18/20/21，依赖 UI-F。用户要求继续美化总览与各模块，判断产品标识/备份恢复是否适合，核对完整需求与故障测试，并查阅开源界面借鉴。

## 实际交付

- 九个业务模块统一工作路径、分区标题、操作栏、卡片、表格和状态；需求运算符显示 ≥/≤，布尔要求显示中文，稳定编号完整显示，试验审核状态中文化，历史项目明确显示实际 mock 模式。
- 侧栏增加“复杂高端装备 · 智能研发 / AI + 工程知识 + 人机协同 / 本地可操作演示系统”，底部固定、菜单独立滚动。顶栏增加实际 SQLite 存储标识、工程师审核提示和真实备份/恢复入口，不声称浏览器存储或真实认证。
- JSON 完整备份含独立 SQLite 数据镜像、版本、审核、已保存文件、计数和 SHA-256；不是 O13 评审材料包，也不能还原未归档的协议原文件。
- 恢复先检查校验值、当前版本 schema 白名单、完整性、外键、数值、跨项目来源引用、样件/正文/材料快照/ZIP 内部哈希和清单；再复核当前状态哈希。写入独立数据库、原文件保留；原子切换启动指针，重启继续使用恢复结果。界面明确复核后才恢复，失败不显示成功。支持当前数据库版本，镜像上限 32 MiB、前端 JSON 文件上限 45 MiB。
- 需求变化后，受控工程影响范围内的变型点和零件决策立即 stale，旧判断保留审计；无关项不变。共用领域影响范围，未另写前端通过规则。完整独立 revision 模型仍未补齐，见验收复核。
- 存储锁返回 503 PERSISTENCE_UNAVAILABLE，恢复写入错误明确报错；本地数据接口与恢复切换使用异步锁串行，避免同步等待占满工作线程。
- 查阅 Ant Design Pro、Tabler、FlowFuse Dashboard 官方项目/演示，仅借鉴工作区、表格、操作区与分组组织，未引入在线资源或下载整套模板。来源见 docs/UI_REFERENCES.md。

## RED → GREEN → REFACTOR

| 行为 | 实际 RED | GREEN / 最终证据 |
| --- | --- | --- |
| 完整备份/恢复 | `python -m pytest backend/tests/test_backup_restore.py -q --no-cov`，退出 1，缺服务模块 | backup-green.txt，4 passed；重启、历史 ID/版本/样件、校验和激活失败测试 |
| 变型/零件即时失效 | `python -m pytest backend/tests/test_variant_invalidation.py -q --no-cov`，退出 1，3 failed | variant-green.txt，3 passed；影响范围与审计失败整体回滚 |
| 故障反馈 | `python -m pytest backend/tests/test_fault_injection.py -q --no-cov`，退出 1，1 failed/2 passed，锁异常未统一反馈 | fault-and-restore-green.txt，10 passed（当时未含并发用例）；最终全量另含两线程修订测试 |
| 归档内容完整性 | `python -m pytest backend/tests/test_backup_restore.py -q --no-cov`，退出 1；来源正文/样件被改且重算外层 SHA 后仍恢复成功 | archive-integrity-green.txt：8 passed；增加逐项哈希/大小校验 |
| 模块路径/备份预览 | `npx vitest run src/components/ModuleWorkspace.test.tsx src/panels/BackupPanel.test.tsx`，退出 1，缺组件 | components-green.txt，3 passed；预览不触发恢复、非法 JSON 不发请求 |
| 工程参数中文表达 | `npx vitest run src/formatters.test.ts`，退出 1，缺 formatter | frontend-final.txt 中通过；覆盖数值/布尔/文本/范围 |

归档校验补充诊断：首次参数化测试未实际生成材料包，材料两项 UPDATE 为 0 行，不能作为材料能力的有效 RED；之后通过 API 生成真实材料包，并断言 UPDATE 行数大于 0 后重跑通过。保留原始失败输出，不将这两项误报为实现前有效 RED。最后增加正文类型防御后，备份专项 8 项、后端全量 212 项及 cockpit 浏览器 4 项均重跑通过。

诊断如实保留：备份初次校验错误地按普通列读取 revision 表，实际为 snapshot_json，3 failed/1 passed；改为读取历史快照后通过。浏览器第一次沿用 UI-F 截图路径导致那些图片被新版重渲染，历史文本测试报告未改；当前权威截图统一写 UI-G。跨测试文件涉及同一个预览库的备份/恢复，最终配置固定 workers=1 防止数据维护与只读快照对比相互干扰。没有删除、跳过业务断言或以失败转成功换绿。

## 最终真实命令与结果

| 命令 | 结果 |
| --- | --- |
| 根目录 `python -m pytest backend/tests -q` | 212 passed，退出 0，backend-final.txt；一条既有 testclient 弃用警告 |
| frontend `npx vitest run --coverage` | 55 passed / 17 文件，退出 0，frontend-final.txt |
| frontend `npm run lint` | 退出 0，24 条既有 Fast Refresh/effect 类警告，lint-final.txt |
| frontend `npm run build` | 退出 0，build-final.txt；未新增依赖或运行时网络资源 |
| `npx --offline playwright test --config playwright.cockpit.config.ts` | 4 passed，browser-final.txt；总览与设置、真实备份恢复、断连与保存 503 |
| `npx --offline playwright test --config playwright.single-project.config.ts` | 3 passed，flow-tests.txt；独立临时库 |
| `npx --offline playwright test --config playwright.change.config.ts` | 1 passed，change-browser.txt；源派生/设计/覆盖/材料阻断，旧执行保留 |
| `npx --offline playwright test --config playwright.review.config.ts` | 1 passed，modules-browser-final.txt；九业务模块，所有当前截图见 demo-*.png |

212 个后端测试包含本轮受控故障与恢复测试，不把其中子集再次叠加为新测试数。浏览器总计 9 条。没有宣称通过未执行的场景。

## 覆盖率、排除与边界

- Python 全业务语句 94.94%，分支 83.93%，语句+分支综合 92.56%；backend-coverage.json。
- Python 核心领域 backend/app/domain/**：语句 96.66%、分支 90.04%；core-coverage.json 包含逐路径清单。API、schema、持久化、适配器与服务编排在全量报告，未混当领域分支；无业务路径人为排除。
- TS 语句 84.31%、分支 71.91%、函数 87.61%、行 88.03%；排除入口 main.tsx、src/test/** 与测试文件。前端无独立业务判定层，UI 分支不等于领域分支。
- 本轮执行的是确定性的本地故障注入；未做长期高负载、分布式故障、真实磁盘故障、进程强杀或真实模型/台架验证。详细场景和未执行项见 docs/ACCEPTANCE_REVIEW.md。
- 所有 AC 尚未全面满足：原始协议二进制归档、变型点/复用决策独立 revision 等仍阻塞完整验收。运行主线通过不能替代全合同结论。Python 未新增独立静态 lint 配置；历史缺失 RED 不追溯伪造。

## 数据与运行

原参考文档未编辑；data/demo.db SHA-256 前后保持 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`。所有故障、写盘失败模拟、恢复和浏览器写操作均在临时库/预览副本；未停止日常 8000/5173 服务，没有断用户网络、填磁盘或重置用户数据。

恢复数据保存在基础数据库同目录的 `.<数据库名>.restores/<随机ID>.db`；`.<数据库名>.active.json` 记录已校验的活动副本。原库和旧恢复副本保留，启动加载活动指针，损坏指针明确失败，不静默覆盖或回退。相关运行文件已加入 .gitignore。

当前查看 http://127.0.0.1:5181/。预览仍由 `python scripts/run_preview_backend.py --port 8027` 和 frontend 的 `ZHIYAN_API_TARGET=http://127.0.0.1:8027` / `npm run dev -- --host 127.0.0.1 --port 5181 --strictPort` 启动；停止后不会把预览恢复副本回写原演示库。
