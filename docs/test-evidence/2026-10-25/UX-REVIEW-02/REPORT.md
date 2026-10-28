# UX-REVIEW-02 试用反馈修复（2026-10-25）

后续状态更新：本报告记录当轮结束时的运行限制；该限制已在[PRE-REHEARSAL-02](../PRE-REHEARSAL-02/REPORT.md)通过原启动器现有stop正常退出流程解决，运行后端已载入本轮修复，用户数据库校验值保留。下文保留当轮过程事实。

关联：用户本轮11点，会议15—19，O1/O2/O3/O4/O9/O10，AC-04/05/07/09/18/20/21。

## 范围与实际变更

- 修订需求仍按新版本待审核处理，可以再次驳回；打开修订弹窗清除其他对象的旧确认提示。已确认旧版的审核不覆盖。
- 常规导入继续自动编号，映射移入高级选项；08文件只用于复现说明中的显示编号，非额外上传依赖，UUID/引用不变。保留草稿恢复及自定义映射兼容性。
- 零件示意图按类别区分壳体、离合器壳、轴、单齿轮、齿轮组、法兰、执行机构、取力器；不是各型号的制造几何或实物照片。
- 选型确认意见可留空、驳回需填写原因；增加操作间距，保存并成功刷新后自动关闭，确认卡片绿色勾选与边线。
- 后端同一上游检查同时服务确认校验与`confirmation_blockers`提示，列具体编号/参数/版本。未确认变型仍阻止通过，可驳回；未降低版本、适配及审核门槛。
- 选型界面与工程档案是同一批工程记录，明确V变型/P零件关系。基型提示解释型号与“选用”自动填入方式；设计两个输入保留可手填，不默认冒充选定型号。
- 试验方案、用例分别增加带原因的驳回弹窗，已审核版本不显示重复确认入口。条件缺失的当前草案可以驳回，仍不能确认；旧执行不改挂。
- 设置内补充初始展示恢复说明，使用已有整库备份预览/确认流程。本轮不替用户恢复初始场景。

## TDD 与过程事实

RED在实现前执行：

1. `python -m pytest backend/tests/test_part_selection.py::test_choice_exposes_upstream_blockers_and_rejection_remains_available backend/tests/test_testing_edges.py::test_incomplete_case_can_be_rejected_but_not_confirmed --no-cov -q --basetemp docs/test-evidence/2026-10-25/UX-REVIEW-02/pytest-red`：pytest退出1，2失败；缺少blockers字段、缺标准用例驳回返回422。日志backend-red.txt；输出包装层读取日志后的退出0不等于pytest通过。
2. `npm test -- src/panels/PartChoicesPanel.test.tsx`：Vitest退出1，2失败/1通过；无意见不能确认、没有具体阻塞及驳回入口，见frontend-red.txt。
3. `npm test -- src/panels/TestingPanel.test.tsx`：Vitest退出1，1失败/5通过；不存在“驳回用例”按钮，见testing-ui-red.txt。

实现后专项：25后端通过（part_selection/testing_edges/engineering_versions）；相关5文件36前端通过。另扩充原有需求测试，核对V2可驳回和修订弹窗不混入其他确认提示。

真实发现并修正：首次build因测试mock返回缺少真实类型字段失败，补全mock后通过；首次浏览器精确颜色断言发现全局CSS覆盖确认徽标，修正选择器优先级，未删除断言；下一次专项通过。代码补丁一次同文件删除/新增被工具拒绝，改用更新；文档补丁一次原文匹配失败后重新读取并按实际文本更新，未更改参考原件。

## 验证

- `python -m pytest backend/tests -o addopts='' --cov=backend/app --cov-branch --cov-report=term --cov-report=json:docs/test-evidence/2026-10-25/UX-REVIEW-02/backend-coverage.json --cov-fail-under=80 --basetemp docs/test-evidence/2026-10-25/UX-REVIEW-02/pytest-full`：340通过，退出0，总覆盖93.37%，1条Starlette/httpx弃用提醒。`python scripts/check_core_coverage.py .../backend-coverage.json`退出0，领域语句97.1873%/分支91.6096%；路径与排除沿用既有配置，没有为本任务扩大排除。
- `npm run test:coverage -- --maxWorkers=4`：31文件198通过，退出0；语句84.93%、分支73.28%、函数82.35%、行91.16%，门槛通过。日志frontend-final.txt。映射草稿测试补充真实展开高级选项，不移除原映射保留断言。
- `npx playwright test --config playwright.overview.config.ts`：最终9个不同用例通过，退出0，见browser-full-final.txt。此前首次完整跑因旧草稿恢复测试在第二次恢复后没有展开高级选项而超时，清理未完成导致后续空态检查也失败（2失败/7通过），见browser-full.txt；补上展开操作后原断言完整保留，9项全绿。专项及重复复跑不叠加计数。浏览器stderr包含故意上传损坏PDF的诊断和终端NO_COLOR提示，不视为假成功或产品正常文档报错。
- `npm run lint`退出0，`npm run build`退出0（103模块）；约514.06kB主JS触发Vite默认500kB体积提醒，未提高阈值隐藏。首次build失败为新增测试mock返回类型不完整，已修正为真实类型字段。
- 全量覆盖后以锁定black格式整理4个Python文件，`python -m black --check`5文件通过；`python -m pytest backend/tests/test_part_selection.py backend/tests/test_testing_edges.py backend/tests/test_engineering_versions.py --no-cov -q --basetemp .../pytest-refactor`：25通过、退出0；仅格式整理后不重复计算全量覆盖。
- 已查看独立库截图：确认区按钮与文本域间距至少12px，绿色标记真实计算样式符合预期，桌面/390px窄屏无页面及弹窗横向溢出；原始截图不代表真实制造结果。
- 全部业务测试使用独立库，浏览器专项保存/恢复的也是自身隔离夹具。

## 日常运行与交付限制

本次读取日常库：工程记录0项。开始核对与保存备份的SHA-256均为`b24aca0c699cd333570e2843701d15637af6f22adbe60ce79b6b8b3c83eb454f`。已通过现有save_shutdown_backup保存完整JSON至data/launcher-backups，写入fsync后回读并核对原始SQLite字节SHA，路径元数据见restart-backup.json。

重启操作在执行前被工具自动审批策略拒绝（blocked by policy），涉及Stop-Process结束已识别的当前本地启动器及其前后端进程。没有通过其他工具绕过拒绝；原服务仍保留，后端代码尚待正常停止后重新启动加载。用户操作：原启动窗口输入stop，停止成功后双击根目录Start-Demo.cmd。仅刷新不能使旧后端载入本轮用例驳回修复。当前用户库未清空、未恢复、未审批；预置初始展示备份只验证/说明，不激活。

最终只读检查：8027/5181健康正常，原后端进程51680仍在；SHA与开始核对、重启前备份一致。205个本地文档链接无缺失，综合演示11项文件大小与哈希匹配；final-verification.json留存实际结果。未执行用户库恢复或后台重启。

## 限制

- 检查日常工作库时，用户此前截图中的工程记录已不在当前库（工程记录0项），不声称对那两个历史UUID做了现场修复。独立夹具复现并验证取力器变型点依赖主箱壳体/新增接口的阻塞。
- 确认后若保存成功但读取失败，保留明确提示并禁止重复提交，成功刷新后再关闭。业务状态仍以后端为准。
- 原生SVG是类别级合成示意，同类别不同型号仍靠登记参数区分；未引入制造级几何数据或真实发动机库。
- 备份恢复是整库切换，不是与当前协议合并；启动不会自动覆盖已有工作副本。未执行用户库的清空、恢复、需求/零件/用例审核。
- `python -m ruff`不可用（未安装该模块）；仓库锁定的Python格式工具实际为black，使用black检查与格式化，不声称ruff已通过。
