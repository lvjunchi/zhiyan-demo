# UX-DEMO-14 演示操作反馈验证

日期：2026-10-26。范围：用户本轮14项反馈，O1/O3/O4/O7/O8/O9/O10/O12、协同指标、AC-01–AC-21中相关导入/审核/版本/界面行为。当前业务数据不重置，参考原件不改。开发计划书和AGENTS基线已读取。

## 实际变更

| 条款 | 结果 |
| --- | --- |
| 1 | 文件选择按钮深蓝白字，边框加深；样件选择入口同步。 |
| 2 | 左环图包括已归档文件与未归档待核对任务，四类状态明确，避免已关联文件重复计数；右图仍是历史处理次数。概况“已解析文档”明确口径，列表头显示未归档数量；待核对可在下方记录继续。 |
| 3 | 新增流程演示版Word/PDF：明确超速档、合成耐久规程DEMO-DUR-001及1000h判据。真实解析各19条草稿/0澄清，原综合协议仍19条/2澄清。规则支持明示合成规程标记，不屏蔽真实问题。 |
| 4/5 | 需求驳回原因选填，空意见仍保留决定及版本；操作固定列位，审核记录最后。 |
| 6/7 | 统一工程表放在零件型号选择之前，保持原表、无分类页签，V点先审核再选零件；已确认/已驳回用绿色/红色标签，有效性独立。 |
| 8 | 只读design-context接口查本项目最新持久化变型分析，设计评审/DFMEA自动沿用基型；手工编辑不被异步加载覆盖。无分析不猜默认值，清空无旧分析。 |
| 9/10 | “填入合成评分”按04样例的明确FMEA编号补全空白草稿，已有保存值不覆盖；不自动保存或确认。S/O/D限定1–10整数，待填写/待保存/待确认/已确认RPN分开，越界禁止保存，单行保存保留其他行草稿。RPN标签不拆行。 |
| 11 | 方案/用例共享驳回原因改选填；旧审核、修订新版本和有效性门槛不变。 |
| 12/13 | 无样件时默认展开登记；列表显式“上传文件”，详情第二步选择并上传原件。五步进度在空白时也显示，已有样件按真实上传/参数/比对/处置/审核状态计算。上传不自动识别图纸尺寸。 |
| 14 | 创建表预填合成议题/参与方/窗口，消息按钮填入发起和关联回复，进度按钮分别填入A/B计划实际及版本、时间和周报。风险接受理由可修改预填文本；全部仍需明确创建/保存/接受，不自动提交。 |

本轮按用户最新第6条将原统一表上移；此前UI-ENGINEERING-ROLLBACK-01“表在下方”属于历史决定，不重新引入分类页签。

## RED、修正和GREEN

命令工作目录除注明外为项目根目录，前端命令在frontend运行。失败日志保留，不通过删除有效断言换绿。

- `python -m pytest backend/tests/test_design_context.py --basetemp .../red-context-temp`：退出1，新增接口返回404；见red-context.txt。新增接口后退出0，见green-context.txt。
- `npx vitest run src/panels/ImportDistribution.test.tsx`：退出1，缺四状态图；见red-import.txt。
- `npx vitest run src/panels/RequirementsPanel.test.tsx src/panels/TestingPanel.test.tsx src/panels/DesignPanel.test.tsx`：退出1，3失败/28通过，选填提交被禁用及缺基型接口；见red-review-design.txt。
- `npx vitest run src/panels/CoordinationPanel.test.tsx src/panels/SamplesPanel.test.tsx`：退出1，2失败/21通过，缺预填和直接上传入口；见red-coord-sample.txt。
- 相关7组件文件最终59通过，见components-green.txt；旧测试追加到预填文本的问题通过先清空输入修正，保留原提交载荷断言。
- 协议测试首次误用extract_text返回键`text`，后一次误期望英文规范值；均为夹具/断言错误，见red-protocol.txt、green-protocol*.txt，**不作为有效产品RED**。合成规程识别扩展未留下合格的实现前RED，此处如实记录该过程缺口。最终真实Word/PDF及原综合对照3项通过，连同基型接口共4项通过，见green-protocol-final.txt。
- 首次全前端207通过/1失败为旧“成功导入”标签断言；更新为本轮“已解析文档”后最终208通过，未改统计数断言。见frontend-full.txt、frontend-final.txt。
- 浏览器前两轮失败来自新验收脚本误用可访问名称/宽泛上传提示选择器，首轮超时使临时库清理失效并影响后续空库测试；旧图名断言也已同步。保留browser-overview.txt、browser-overview-final.txt。修正脚本且从新独立库重跑，10项全通过；未放宽业务断言或改日常库。

## 最终验证

| 命令 | 实际结果 |
| --- | --- |
| `python -m pytest backend/tests --basetemp docs/test-evidence/2026-10-26/UX-DEMO-14/full-temp --cov-report=term-missing --cov-report=json:docs/test-evidence/2026-10-26/UX-DEMO-14/backend-coverage.json` | 退出0，350通过，259.49s；backend-full.txt。 |
| `python scripts/check_core_coverage.py docs/test-evidence/2026-10-26/UX-DEMO-14/backend-coverage.json` | 退出0；整体93.45%，核心backend/app/domain语句97.1873%、分支91.9521%；core-coverage.json。 |
| `npm run test:coverage -- --maxWorkers=1` | 退出0，32文件208通过；前端语句85.17%、分支73.97%、函数82.83%、行91.21%；frontend-final.txt。 |
| `npx playwright test --config playwright.overview.config.ts` | 退出0，10通过；browser-overview-verified.txt。包括新协议真实上传、未归档统计、空原因驳回、沿用基型、评分保存确认、真实文件上传、两消息及两进度样例提交并重算出2h响应与进度/版本预警。 |
| `npx playwright test --config playwright.cockpit.config.ts part-selection saved-feedback version-dialog workflow-progress workflow-drawers z-workflow` | 退出0，8通过；browser-cockpit.txt。含版本、失败后重读、其他草稿保留、样件与协同真实状态。 |
| `npx playwright test --config playwright.overview.config.ts demo-usability` | 最终RPN标签样式调整后退出0，1项复验通过；browser-final-style.txt，不与前述18项重复累计。 |
| `npm run lint` / `npm run build` | 最终均退出0，lint-verified.txt/build-verified.txt。 |
| `node docs/test-evidence/2026-10-26/UX-DEMO-14/live-readonly.cjs` | 修正只读脚本先切全部需求后退出0，live-readonly-final.txt/json；实际5181桌面和390px检查、无页面错误、无业务写入、页面无横向溢出。 |

前端没有独立业务判定领域，判定仍由后端唯一负责；不把前端73.97%分支称作90%。未新增覆盖率排除；前端沿用main.tsx入口、src/test及测试文件排除，后端核心按既有domain范围独立统计。末次样式只增加RPN不换行，不改变受测业务。

非阻断工具提示：FastAPI/Starlette现有httpx弃用提示1条；Vite主包约530kB提示拆包。未隐藏提示，构建和测试实际退出0。损坏PDF用例预期输出invalid header，不是未解释产品失败。

## 文档和运行

- 新资料：`演示导入文件/流程演示/01_流程演示协议_V1.docx`及PDF、使用说明、SHA-256清单；生成脚本scripts/create_flow_protocol.py拒绝覆盖现有目标。原参考及综合协议未改。
- 使用documents/pdf技能。bundled Python可用；通用render_docx因无LibreOffice未成功，日志doc-render*.txt保留。用本机Word只读导出PDF、Poppler渲染替代验证，最终两页reviewed-page-1/2.png已目视检查，版式无截断。两种协议提取的实际语义已测试，不因通用渲染器失败声称未执行。
- README、主操作指南、老师说明、任务表、文档索引、验收摘要、开发日志和决策同步；旧变更排练仍使用原综合协议，两条澄清不被隐藏。
- 原启动器34016经过已验证stop协议正常备份退出；新启动器6040，端口8027/5181，无强杀端口进程。日志runtime-stop/stdio、runtime-before/after.json。
- 实际业务备份SHA在重启前后及只读检查前后均为`8f45a53510a6208fa10353e60f5eb3a1a0855415242b1ef488d8372522c69f0c`。没有清空/恢复/重新导入/审核日常项目。中间临时测试库正常恢复与当前业务库无关。

## 使用边界

流程版需用户选择导入，不会改写已经导入的旧模糊条款。演示评分和协同记录有合成来源，不能当成协议自动提取的实测数据；一键填入不跳过保存/审核。样件参数仍需结构化登记，旧DOC/扫描OCR、生产认证、全申报指标达标不在本轮新增范围。没有公网、收费API或外部发送。
