# INITIAL-SHOWCASE 完整初始展示与清空重演

2026-10-25；关联用户本轮确认的完整展示范围、会议第2/3/7/8/9/10及清空重演、O1—O4/O6—O13、AC-01/02/04/07/14/15/16/17/18/20受控范围。

用户明确选择：初版Word加独立合成的选型、设计、试验、样件及协同样例。协同数据不能由协议自动产生；后续从空白导入新协议不能继承这套夹具结果。

## 实现和真实数据

新增scripts/prepare_initial_showcase.py，只创建不存在的独立输出目录，通过真实API抽取并归档外层01_重型变速器技术协议_V1.docx，得到13条需求。原Word SHA256为5bd022e55a1bcc6206c965558c3799598dbb979ddbac4aa8b4ae2d68af1bc51b，未修改。独立合成CN-01/CN-02澄清最高档/耐久并保留修订与关闭记录，使用真实范围预览批量审核；审核身份为“初始展示准备（合成）”，不冒充真实工程签核。

预置受控型谱计算、JX-12A变型/复用、独立主箱壳体/齿轮候选选择及工程确认、设计评审、按明确合成评分表的DFMEA、方案/用例/执行、SVG图纸样件与人工比对、一致性报告及草稿材料。发动机仍2600 N·m（V1），不运行BG-01，不修改JX-12A能力；固定验证范围5/5覆盖、5/5合成执行通过，不扩展为全部产品工程认证。

协同为独立合成议题：3对回复48/52/56小时，均值52小时，4次重开、缺席1/3；三方进度90/30/55%、V2/V1/V1，均保留时间和证据并由后端计算预警。高风险不自动接受，因此材料包draft，1项阻断；不自动human_approved。文件与数据来源在manifest及记录中标明。

生成data/initial-showcase/initial.db、initial-backup.json、manifest.json。启动器仅在没有工作副本时使用完整预置源；缺少manifest的半成品不选用，缺失预置时兼容demo.db。已有工作副本/恢复指针优先，清空或新导入后重启不自动补回样例。没有新增后端接口或数据库迁移，仍018。

首页协同响应图空态补充“响应图需要配对沟通记录，协议导入不包含这些记录。”及现有查看风险入口，说明缺少的是业务输入，不伪造零值。

## 测试：RED → GREEN 与回归

- 初次pytest RED：缺准备脚本，3项失败，red.txt。实现后真实检出批量审核字段名不对（green.txt）并修正；测试清空预览原写GET，实际应POST，该失败是测试调用错误而非功能RED，修正为正确方法并校验状态（green2.txt）。
- 启动器缺default_source为真实RED（green3.txt）；随后增加半成品场景，partial-red.txt真实失败，修正只有manifest就绪才选预置源。
- 保护范围复核：在GET项目列表后、获取备份前注入新建P02，scope-red.txt证明仅检查旧列表会遗漏；现在依据实际备份再次验证仅有P01，拒绝整体恢复，保留P02。备份落盘fsync后回读并完整校验，再以expected_state_hash激活，状态变化则不切换。
- 最终`python -m pytest backend/tests/test_initial_showcase.py backend/tests/test_demo_launcher.py backend/tests/test_demo_launcher_runtime.py --basetemp docs/test-evidence/2026-10-25/INITIAL-SHOWCASE/pytest-complete -q --no-cov`退出0，12项通过，17.56秒。包括原件13条/独立成果/52小时、拒绝覆盖输出、备份完整/其他项目保护、清空重启为空、重新导入综合Word19条draft且UUID不复用/无旧协同。
- UI针对“protocol alone”新增说明与跳转的测试先失败（ui-red.txt），后全量`npm run test:coverage`退出0，181项通过；语句84.01%、分支72.61%、函数82.29%、行90.16%，既有门槛通过。命令筛选时其他项未执行不等于代码skip；最终全量没有跳过。
- `npx playwright test --config playwright.overview.config.ts`退出0，6项通过（57.8秒）：新增全初始场景→设置真实备份清空→空白首页→综合Word19条draft/零协同→刷新不补样例；其他5项文档/失败/批量审核/Word-PDF回归保留。新增测试最后恢复独立服务器的原空白快照，不影响后续测试和日常数据。
- `npm run lint`、`npm run build`退出0；Black格式化后三个修改Python文件检查/专项复跑通过。没有领域规则修改或额外重构；本轮未重跑全量后端331及domain覆盖，不借用历史覆盖作为新增结果。

## 按授权载入日常工作区

2026-10-25T04:47:06 UTC已显式载入完整初始场景。原工作区备份：data/backups/before-initial-showcase-cd688757b92e435cb22308f3fba66e5b.json；落盘、回读校验后通过既有restore-preview/restore接口切换副本，原数据库保留，未删除。当前仅P01，防止覆盖其他项目的检查已执行。不能沿用旧报告“日常只读/未更改”的结论来描述本次授权切换。

live-activation.json记录当前13条已确认、1议题/10记录、高风险、覆盖100%、通过5/5、草稿材料1阻断。实际5181页面重新打开的只读浏览器检查通过：原件关联13条、响应图48/52/56小时可见、浏览器写请求0；live-ui.txt及live-initial.png，截图已目视核查。data/demo.db仍EDC56DBC3DB3AD6F227CA9BB3B3C974CFBB43954D32DA89BF2643E995C48B5D0。

`python scripts/start_demo.py --check --backend-port 8123 --frontend-port 5263`退出0，只读预检通过（另用空闲端口，未停止日常服务）。当前页面刷新即可读取新项目身份；以后更新旧后端仍按stop/启动流程。

## 使用与复现

先在首页展示已有合成成果。亲自演示：设置→重新开始项目→预览、输入P01、备份并清空→重新载入→导入综合版Word或PDF，得到19条待审核需求；按操作说明逐步生成设计、试验、样件与协同。不直接向初始场景叠加新协议替代清空。

恢复初始展示可在设置选择data/initial-showcase/initial-backup.json（整库恢复，先备份并核对范围）。开发者可`python scripts/prepare_initial_showcase.py --output-dir <不存在的新目录>`复现；加`--activate-url http://127.0.0.1:8027`才会显式备份后载入，只允许本机、单P01。已有输出拒绝覆盖。

README、演示指南、老师说明、外层文件入口及验收/任务/日志同步。原参考资料、Word/PDF交付正文、旧demo.db和此前验收证据保留。本轮没有递归删除缓存或绕过此前审批限制。
