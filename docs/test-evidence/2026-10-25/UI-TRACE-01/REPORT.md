# UI-TRACE-01 总览一致性追溯展示

关联：用户参考图、O7/O9—O11、AC-09/11/13/20/21。仅调整总览只读汇总与详情，不改变判定、审核、版本或清空流程。

## 变更

- 后端将设计评审项的直接需求依赖、实际用例/执行记录附到原追溯矩阵；保留所引用的旧 revision，不按名称或示例图猜测关系。设计项明确为评审检查点，非 CAD 成果。
- 表格展示需求版本、关联设计评审项、试验项、执行结论与查看入口。宽屏显示具体要求值，紧凑屏保留完整悬停说明与详情。
- 环图使用原后端有效用例覆盖数/固定分母；未套用参考图的“85%+检出率”，也未把用例覆盖或执行通过改称全链一致。
- 宽幅详情展示当前基准、评审版本及引用需求版本、工况、加载条件、准则和执行记录；可进入对应工作台。沿用原弹窗 Esc、焦点返回和滚动行为。
- 保留失败、待审核/复核、未覆盖、未执行的独立展示。没有直接关联时显示未关联；未生成方案时不编造追溯行。
- 桌面四尺寸同屏、手机表格内部横向滚动；修复初轮表格裁切及隐藏辅助文字脱离滚动容器导致的页面溢出。

## RED → GREEN → REFACTOR

RED：`python -m pytest backend/tests/test_overview_api.py -k trace_links --no-cov --basetemp docs/test-evidence/2026-10-25/UI-TRACE-01/pytest-red`，新增行为断言因 `KeyError: design_items` 失败；`npm test -- src/panels/OverviewPanel.test.tsx -t 'shows requirement-design-test links'` 因缺少“需求项”等新表头失败。见 backend-red.txt/frontend-red.txt。初轮命令尾部读取日志导致 shell 返回0，未独立保存测试进程退出码，不把 shell 的0称为测试通过。

GREEN：后端 overview 专项5项、前端全量182项通过；新增关联真实性/跨项目隔离/只读/2600→2800 后旧依据和执行保留断言；组件断言失败与待审核并存、详情准则与旧引用可见。浏览器3项通过（四桌面尺寸+手机、弹窗、Esc/焦点、备份 SHA 不变）。初轮布局失败留在 browser*.txt 中，最终结果见 browser-green-final.txt。

重构：独立 OverviewTrace 组件与样式，Python Black 格式化。最终全量 `python -m pytest --basetemp docs/test-evidence/2026-10-25/UI-TRACE-01/pytest-full --cov-report=json:docs/test-evidence/2026-10-25/UI-TRACE-01/backend-coverage.json` 337项通过，退出0；总覆盖93.34%，核心领域语句97.1873%、分支91.6096%，核心门槛检查退出0。COVERAGE_FILE独立保存在本目录。

`npm run test:coverage` 182项/29文件通过，语句84.02%、分支72.55%、函数82.16%、行90.22%；前端未新增领域规则，沿用既有UI覆盖门槛，不能把UI分支72.55%称为领域90%。覆盖范围与既有排除不变。

`npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts overview-trace.spec.ts` 最终3项通过；`npx playwright test --config playwright.overview.config.ts` 6项通过，覆盖初始完整场景→备份清空→Word重导入、空白状态、PDF失败、批量审核/修订及Word/PDF一致解析。相关命令退出0；无skip/删断言。`npm run lint`、`npm run build`、`python -m black --check backend/app/overview_services.py backend/tests/test_overview_api.py` 退出0。

唯一pytest警告为既有Starlette/httpx弃用提示；浏览器损坏PDF用例预期输出header/EOF诊断，未转为成功。初轮裁切（1440、1920、1366）及手机隐藏辅助文字定位导致的横向溢出均已保留日志，并通过原断言修正，没有降低布局验收。

## 实际服务复核

为加载后端新增只读关联，先GET完整备份、验证数据库内容SHA并另存 `data/backups/before-ui-trace-20261025.json`；核对原启动器及其本项目两子进程身份后停止并重新启动同一工作副本。现仍运行8027/5181、迁移018。前后业务数据库SHA均为 `4be0ddf23cc6fb4d55c9862280caeecca29808c79b6cc7de3daf20d718d0bc39`，未替换项目、未清空、未修改业务记录。

实际API返回5条真实链路；1920/1366/390只读浏览器检查通过（写请求0、页面异常0），实际卡片、紧凑屏与弹窗截图已目视检查。见runtime.json、live-browser.json、live-trace*.png。原初版13条需求与独立合成成果继续保留。重启后刷新总览即可查看。

## 数据与边界

所有运行测试使用隔离副本。未重导入、确认、清空或替换用户项目。该总览仍以固定验证集展示5条要求，完整冲突报告由“查看检测”进入；环图不是全项目缺陷检出率。规则/人工/合成执行模式仍来自保存记录。
