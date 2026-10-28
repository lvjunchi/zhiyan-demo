# UX-DEMO-07 批量审核、样件预填与变化表格

日期：2026-10-26。关联本轮7点反馈，O3/O4/O8/O10/O12及一致性展示、相关AC-05/07/09/10/11/12/16/18/20。按开发计划书与AGENTS执行，不改原协议或参考文档，不清空/恢复日常项目。

## 实际完成

1. 工程记录“一键确认 · 先预览”：冻结当前筛选下的明确ID、基型和revision清单，勾选核对后提交。范围为当前待审核变型点及已选择DEMO候选的零件；未选型号、已审核、待复核和历史项不自动确认。服务端逐项检查项目、适用性、预期版本、上游及候选约束，先变型后零件，同一事务提交；任一失败整批回滚。每项沿用原审核与审计，不另造通过规则。查看版本按钮统一238px宽、40px最小高。
2. “填入合成评分”改为深蓝白字主按钮，仍只填空白、不自动保存/确认。
3. 试验驳回用例使用全局红字浅红底样式，不依赖选型模块样式是否先加载。
4. 执行证据按用例编号/版本预填合成记录，可编辑、可明确清空；空白不偷偷恢复默认值，提交仍需填写。预填没有创建执行记录，不自动设置加载或通过。
5. 样件登记前即显示原件选择和“登记并上传文件”。选择文件后该按钮明确触发登记、上传两个步骤；不选文件也可先登记，原列表/详情上传入口保留。上传失败不假称成功，已登记交付和文件输入在详情可重试，提示勿重复登记。
6. “填入样件合成样例”带入05中的供应商、P-03、图纸、日期及两项尺寸；“填入合成合格实测/超差实测”填入120.2/121孔位、45.01轴径、目视说明和证据。仅匹配参数key、单位、期望值、公差的项；用户须显式提交和确认，原件不自动解析尺寸。
7. “参数与版本变化”改成Excel风格只读表格：字母列、行号、网格、固定表头、有限高度滚动、搜索与类型筛选、长证据摘要及独立详情。稳定ID作行身份，序号只作显示；修改仍在来源模块留版本，不直接改历史单元格。

## RED → GREEN 与实际修正

- `python -m pytest backend/tests/test_engineering_batch.py --basetemp .../red-temp`退出1：新批量接口404，共5失败。全局覆盖门禁因只跑专项也报不足，不计为产品RED；实际缺失接口断言见red-backend.txt。
- `npx vitest run src/components/EngineeringRecords.test.tsx src/panels/SamplesPanel.test.tsx`退出1：2新入口行为失败/23既有通过，见red-components.txt。
- 执行证据第一次测试错写了API/夹具函数名，red-testing.txt为测试错误，不能作为有效RED；修正为真实getTraceabilityMatrix、recordTestRun、planFor后，red-testing-valid.txt退出1，1新预填断言失败/7通过。
- `npx vitest run src/components/WorkflowOverview.test.tsx`退出1，缺搜索/依据展开行为，见red-sheet.txt。
- 实现后green-components.txt为42通过/2失败：新样件断言误用了toHaveValue非对称匹配器、旧试验证据测试在预填后追加文本。修正输入值断言及先清空再键入，保留原载荷断言；最终green-components-final.txt为5文件44通过，退出0。
- 首次build发现EngineeringRecord缺part_number类型声明，补为后端已有字段的可选类型；不是放宽为any。最终build-final.txt退出0。
- 个别新浏览器断言先找执行表单却未确认用例，browser-overview.txt中9通过/1失败；修正为先真实确认用例再查预填证据，browser-new-flow.txt单项通过。没有改审核门槛。
- 实际只读脚本首次误假设当前有待审核用例，后一次未等样件加载完成就读details展开状态；保留live-readonly*.txt，改为按当前已保存状态核查、等待加载后展开。最终live-readonly-verified.txt通过。未通过修改日常数据制造待审核状态。

## 最终命令与结果

| 命令 | 结果与证据 |
| --- | --- |
| `python -m pytest backend/tests/test_engineering_batch.py backend/tests/test_engineering_versions.py backend/tests/test_part_withdrawal.py --no-cov --basetemp .../green-temp` | 20通过，退出0；green-backend.txt。 |
| `python -m pytest backend/tests/test_engineering_batch.py --no-cov --basetemp .../combined-temp` | 6通过，退出0；green-combined.txt。新增组合用例验证请求零件在前也按变型先审，版本失败、未选型、跨项目和重复范围均不部分提交；重试不重复审核。 |
| `python -m pytest backend/tests --basetemp docs/test-evidence/2026-10-26/UX-DEMO-07/full-temp --cov-report=term-missing --cov-report=json:docs/test-evidence/2026-10-26/UX-DEMO-07/backend-coverage.json` | 356通过，退出0，349.39s；backend-full.txt。原单条确认提取为事务内共享函数后，全量重跑通过。 |
| `python scripts/check_core_coverage.py .../backend-coverage.json` | 退出0；整体覆盖93.48%，核心domain语句97.1873%、分支91.9521%，core-coverage.json。 |
| `npm run test:coverage -- --maxWorkers=1`（frontend） | 32文件211通过，退出0；前端语句84.54%、分支73.80%、函数82.27%、行90.55%，frontend-full.txt。 |
| `npx playwright test --config playwright.overview.config.ts` | 9通过/1新脚本顺序问题；修正后`... demo-usability`通过，9+1共10个不同用例均已验证；browser-overview.txt/browser-new-flow.txt。 |
| `npx playwright test --config playwright.cockpit.config.ts part-selection saved-feedback version-dialog workflow-progress workflow-drawers z-workflow` | 8通过，退出0；browser-cockpit.txt。与上组共18个不同浏览器用例，不重复计数。 |
| `npm run lint` / `npm run build` | 最终均退出0；lint-verified.txt/build-verified.txt。 |
| `python -m black --check backend/app/engineering_batches.py backend/app/engineering_versions.py backend/app/main.py backend/tests/test_engineering_batch.py` | 退出0，black-check.txt。 |
| `node docs/test-evidence/2026-10-26/UX-DEMO-07/live-readonly.cjs` | 最终退出0，live-final-style.txt/live-readonly.json；实际5181桌面/390px检查，无业务写入、无页面错误、无页面横向溢出。 |

覆盖率没有新增排除。前端仍排除main.tsx入口、src/test及测试文件；前端分支73.8%不称90%，业务领域判定在后端domain独立核算。前端表格和预填不接管通过规则。

浏览器新增流程实际执行：Word上传解析、工程范围预览/提交与按钮尺寸、评分按钮颜色、先确认用例再看合成证据及红字驳回、空白样件页预填05并上传真实07 SVG、合格/超差值切换后提交超差比对、Excel表格搜索与来源、协同样例重算。样件待处理问题仍真实保留。截图demo-change-sheet及实际live-change-sheet/live-sample-prefill已目视核对。

最后视觉QA进一步将登记按钮固定42px高、底边对齐，并限制变化表列宽，长值可悬停或展开查看，避免被长耐久文本撑宽。此后只重跑受影响的新浏览器用例（browser-final-style.txt，1通过，不重复累计）及实际只读脚本、lint/build，均退出0；未改业务判定或重新重复后端全量。最终主包537.47kB。

## 运行、文档与边界

原启动器6040通过既有stop协议验证备份后正常退出；新启动器56176就绪8027/5181，不强杀占用进程。重启前后及实际只读核查前后业务SHA均为`ddbada5a540635de3999ede1584e4e3aff5eb13126f39a8de35908a980915272`，见runtime-before/after、live-readonly.json。当前业务和旧审核保留，没有清空、恢复或在日常库创建样例。

主操作指南、README、老师说明、任务表、文档索引、验收摘要、开发日志及决策同步。批量最多100项，整批失败应重新读取核对；上传和登记为两个真实保存步骤，上传失败保留登记而不重复注册。合成填值不等于实测/确认，变化表为只读电子表格风格，不是内嵌Excel编辑器。

未联网、未调用收费API、未改原协议、未做外部发送。保留现有FastAPI/httpx弃用提示及Vite约537kB拆包提示，退出码均真实为0，没有隐藏失败。
