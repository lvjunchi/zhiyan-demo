# REVIEW-01 七组需求复核与清理检查

日期：2026-10-25。关联会议23项、O1—O4/O6—O13、AC-01—AC-21受控场景。

本次依据开发计划、AGENTS、代码及重新运行的测试复核；没有修改业务代码、参考原件或日常项目数据。七组核心流程具有本地Demo的受控实现和验证证据，完整主线通过；不能扩展为任意协议、真实制造适配或全部申报指标达标。

## 七组结论

| 组 | 结果 | 本次核查与边界 |
| --- | --- | --- |
| 1 框架品牌 | 已实现，验证通过 | 全称/品牌、透明卡车图、分组导航、醒目下一步；导航、设置、字号与移动布局检查通过。 |
| 2 项目总览 | 已实现，双阶段通过 | 空白介绍、真实Word导入后看板、实际状态/步骤强调/滚动动态/风险原因；四种宽度截图，1440空白图人工目视核查。 |
| 3 清空导入 | 已实现，隔离库通过 | 明确确认后备份清空及重导入、正文核对、真实失败记录、文档状态及分布、问题闭环。DOC与扫描PDF/OCR仍不支持。 |
| 4 需求审核 | 已实现，交互通过 | 筛选/排序/定位、批量范围预览及逐条审计、取消不写入、弹窗修订新版本、状态图筛选；非法/阻塞/旧版本不能批量通过。长字段列宽仍可优化。 |
| 5 型谱零件 | 已实现合成候选演示 | 24型号、图示/来源/依据、选择/独立确认、状态统计、版本/失效/材料追溯。自动核对扭矩/档数包络；接口及制造适用性仍需人工核对，图示非各候选实物照片。 |
| 6 验证风险 | 已实现受控流程 | 当前试验与历史分开、样件五步及复检、参数/版本/型号/实测对照、冲突图表、AB进度/交付版本/沟通风险。技术参数冲突在一致性模块，未统一汇入协同议题；无真实现场采集。 |
| 7 协议样例 | 已交付，重新排练通过 | Word/PDF各19条、九类及2条待澄清，独立零件/试验/样件/协同样例；11交付文件SHA及长度全通过。JSON用于填值/隔离排练，不是通用一键导入格式。 |

## 重新执行结果

所有测试使用独立库。未向日常项目发出清空、确认、恢复或导入请求。

- `python scripts/rehearse_demo.py --output-dir docs/test-evidence/2026-10-25/REVIEW-01/rehearsal`：退出0；Word/PDF各19条；80→60→80→100；旧结果保留；合成人工审批冻结；修改后旧ZIP不变；备份清空后UUID不复用。见rehearsal.txt和rehearsal/rehearsal-report.json。
- `python -m pytest --basetemp docs/test-evidence/2026-10-25/REVIEW-01/pytest-full -q`：退出0，331通过，319.78秒，1个第三方弃用警告。COVERAGE_FILE为本目录.coverage；`coverage json`和`python scripts/check_core_coverage.py docs/test-evidence/2026-10-25/REVIEW-01/backend-coverage.json`均退出0：domain语句97.1873%、分支91.6096%，综合93.29%。排除范围未扩大。
- frontend中`npm run test:coverage`：退出0，29文件180通过；语句84.08%、分支72.64%、函数82.50%、行90.21%。前端无独立领域层，按既有UI门槛验收。
- frontend中`npm run lint`与`npm run build`：均退出0。
- `python scripts/check_demo.py --only python-format --evidence-dir docs/test-evidence/2026-10-25/REVIEW-01/format`：退出0，仅检查器所列20路径，不声称所有历史文件均已格式化。
- frontend中分别`npx playwright test --config playwright.cockpit.config.ts`、overview、change、fixes：均退出0，29+5+1+4=39项通过；独立服务自行结束。
- 综合交付文件按清单重算SHA-256和长度：11项全通过，见bundle-integrity.json。

本轮为已有实现复核，无新行为或代码重构，新增RED/GREEN不适用；历史实现的RED/GREEN证据保留于各阶段报告，没有削弱断言或跳过失败。

cockpit首条命令设置截图目录的PowerShell父路径表达式失败，测试随后正常执行29项通过，截图在默认frontend/test-results/cockpit/screenshots；其他套件使用本目录显式browser-*路径。损坏PDF的header/EOF日志是失败处理测试的预期输入。后端Starlette TestClient/httpx弃用、Node颜色环境提示均未导致失败，不在演示前临时升级锁定依赖。

## 阻塞与待优化

当前受控主线未发现新软件阻塞。日常8027端口连接拒绝，说明后端未运行，不代表业务数据损坏；使用前双击Start-Demo.cmd等待就绪。未停止或清空日常实例。

非阻塞项：需求长字段在部分桌面宽度中换行较多，可继续分配列宽/横向滚动；可增加候选接口/材料约束及区分型号的图片；可将一致性技术冲突关联协同议题。完整页截图中的固定顶栏位置不能直接当成实际滚动故障，未据此修改布局。

统一检查脚本默认尚未包含overview套件，本次已显式执行；默认pytest临时目录也未统一到证据目录，本次显式指定独立basetemp。复杂跨行文档泛化、更多依赖组合、长期运行/任意时刻中断恢复仍未完成完整专项（NEXT-01/02/04）；历史CSS收敛及PDF原位标注待办保留。不宣称生产级混沌测试全部通过。

## 清理实际结果

用户本轮明确授权删除多余文件。选定2026-10-23/STAGE-03—07的pytest-*重复临时副本：44目录、1842文件、逻辑1271.83 MiB，见cleanup-inventory.json。逻辑大小不等于NTFS实际可释放空间。

保留data全部业务库/活动指针/恢复目录/备份、参考原件、简版Word和综合交付、最终排练ZIP/备份、报告/RED-GREEN日志/覆盖率/截图、离线依赖、Git和IDE资料。STAGE-03/text-test.pdf被浏览器测试引用，不能当废弃文件删除。

带Resolve-Path边界和链接检查的原生PowerShell Remove-Item -LiteralPath -Recurse命令被自动审批在启动前以blocked by policy拒绝整条命令。实际删除0文件、该1271.83 MiB未释放；没有换Python/Node等方式绕过。清单在拒绝后以只读扫描单独生成。新测试证据保留，清理不影响功能测试结论。
