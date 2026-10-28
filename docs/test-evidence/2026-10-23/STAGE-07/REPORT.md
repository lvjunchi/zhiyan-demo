# STAGE-07 综合协议与最终排练

会议23及第4—7组收尾；O1—O4、O6—O13与两引擎的受控AC-01—AC-21场景。第4→5→6组各自通过后开始本组，当前四组完成，广泛泛化/生产能力不在该结论内。

## 交付与实现

综合资料位于演示导入文件/综合演示：Word和同内容文本PDF、澄清变更、零件、试验/评分、样件实测、协同、SVG尺寸原件、编号映射、校验清单与使用说明。原13条简版和参考原件保留。新协议19条草稿、A—I九类、2条待澄清（最高档、耐久）；配套JSON为独立人工填值与排练样例，未宣称界面可统一导入所有JSON。规则补充油品/换油、标准法规、验收和噪声字段、同义表达及中文紧邻AMT词边界；保留重复/矛盾与来源，不是模型生成。

完整API排练脚本scripts/rehearse_demo.py只新建独立库，已存在目录拒绝覆盖。真实Word提取/归档/解析→范围审核→CN-01→型谱/零件独立审核→评审/SOD/DFMEA→方案/用例/执行→2600→2800→CN-02及耐久用例补据→样件失败/复检→AB进度风险/显式接受→一致性→材料就绪与合成人工审批冻结→改进度后旧ZIP字节不变→完整备份清空→PDF重新导入19条，旧/新需求UUID不交叉。coverage_sequence=[80,60,80,100]，旧结果保留，基型2600不改。排练输出final-rehearsal/，含report、ZIP、清空前备份；不属于日常业务材料。

排练发现并修复：选择零件时把无关待澄清耐久也作为前置，改为候选匹配字段+实际工程影响字段；样件结果增加记录复检入口并提交expected_revision；用例增加修订弹窗补条件、加载、判据与依据，保存后另行审核/执行；静扭冻结门槛只读。已停用的DR-07/DR-08条目历史stale曾被当成当前冲突，现依据当前文档有效性报告失效，退役条目留历史、不阻断新文档。

## RED GREEN 与真实检查

- parser-red.txt：新增字段9失败（缺行为）→27相关通过；adjacency-red.txt中文紧邻及英文误匹配失败→修正词边界。Word/PDF初轮正文间距与AMT漏抽导致不等；修复识别并按去空白的文本/单位比较（保留字段和值差异断言）后bundle-green2共15通过。
- bundle-red.txt：缺交付文件2失败；rehearsal-red.txt：缺脚本失败。排练green1—5中真实发现原件sha缺字段、耐久用例需显式补判据、样件修订需版本及退役评审误冲突；原日志保留，没有绕过门禁或接受仍检出的产品偏差。
- scope-red.txt：无关耐久阻断零件确认→scope-green4通过。retired-red.txt：退役条目仍报冲突→与排练合计4通过。
- sample-revision-red初轮测试按钮/表单路径错误，不作有效功能RED；修正步骤后red3因缺“记录复检”入口失败，green2通过并断言提交expected_revision。case-dialog-red缺组件失败→用例/既有试验专项通过。筛选执行的其余用例只是该命令未执行，不在代码中skip；最终全部前端180执行通过。

最终后端命令：`python -m pytest --basetemp docs/test-evidence/2026-10-23/STAGE-07/pytest-full -q`，退出0，331通过，208.01秒。`coverage json`及`python scripts/check_core_coverage.py .../backend-coverage.json`退出0，核心语句97.1873%、分支91.6096%，综合93.29%。前端`npm run test:coverage`180通过（29文件），语句84.08%、分支72.64%、函数82.50%、行90.21%；`npm run lint`零警告、`npm run build`通过。`python -m black --check`本轮24个Python文件通过。核心只计backend/app/domain/**，前端无独立领域层；既有排除项未扩大。

浏览器：`npx playwright test --config playwright.cockpit.config.ts`29通过；overview5通过；change1通过；fixes4通过，共39不同检查。新增真实综合Word/PDF导入同19条九类、试验判据弹窗、样件复检新版本，含桌面/390布局、旧结果留存、独立审核、保存故障、备份与当前门禁。截图browser/。原change测试常驻表单步骤已同步为打开全部需求与修订弹窗，断言未放宽。

## 文档质量与环境

使用documents和pdf技能。依赖加载工具当轮未提供，按已安装运行时路径解析到C:/Users/LvXiao/.cache/codex-runtimes/codex-primary-runtime/dependencies，实际以其中python.exe/python-docx作者、node.exe运行两种输出marker（每种一次）。canonical render_docx.py真实尝试因Windows无soffice失败，日志docx-render-attempt.txt保留；改用本机Word COM隐藏只读打开并导出同内容PDF，关闭本次文档，未操作其他文档。Poppler将PDF渲染为2页PNG，逐页目视检查并去除默认Title蓝色边框及斜体字幕，再重新导出/逐页复核；最终无裁切/缺字/重叠，Letter页面、11.5pt正文。Word原生转换保证PDF与DOCX版式一致，不用文本提取代替视觉检查。老师使用现成交付文件无需生成依赖、Word或LibreOffice。

README、DEMO_GUIDE、老师说明、导入说明、任务表、验收、日志与决策已同步。校验清单记录最终文件SHA。文档描述真规则/人工/合成边界，不把申报指标当成已实测。

## 数据与限制

本轮测试、排练、导出均独立库。日常仅GET health/backup：13需求、1来源，当前旧服务016；sha为6cffc45484e43cd78fc8813d1896fe0d1c3ba3ec6b11c8acfc7283a2e6e646c6，与较早707a...不一致，原因未在本轮追溯，不声称日常工作库hash不变；本轮未向日常服务发写请求或清空/审核/停止。源data/demo.db SHA仍edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。要加载018须在原窗口stop备份退出后重新Start-Demo.cmd。

主线无已知阻塞；完整任意依赖组合、复杂跨行文档泛化、长期运行和生产级混沌仍未全面验证。无OCR、旧DOC转换、生产连接、真实认证/权限、自动CAD或设备采集。零件为24个合成匹配包络，图片为示意或明确产品参考；额外温度/NVH未自动算入固定5条已通过。未擅自清空用户数据或批准日常材料。

收尾清理：已检查仅拟删除本轮pytest-*临时目录且校验工作区边界，但递归删除命令被自动审批策略拒绝（blocked by policy），实际未执行。测试临时库全部保留，没有改用其他工具绕过。最终独立排练库、备份、日志、覆盖与图片均保留。交付文件校验清单逐项SHA复核通过。
