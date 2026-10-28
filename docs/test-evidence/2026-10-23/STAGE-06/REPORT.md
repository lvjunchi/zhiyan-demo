# STAGE-06 验证流程与两引擎展示

会议19—22，O9—O12、两引擎，AC-10—15/18/20/21。后端只读workflow-summary提供当前用例审核/有效性/执行、样件5步和参数/版本变化；前端使用真实统计和横条，旧执行保留并标历史。样件流程区分登记、图纸、实测、问题处置与审核；一致性页面展示原值/现值、型号替换、新增件、图纸实测和来源，既有冲突抽屉保留；严重度/类型增加条形图。图纸/实测输入空白不再转0。

018迁移保存按参与方+里程碑的稳定UUID和版本历史。进度差/计划落后≥20个百分点中风险、≥40高风险，交付版本不同中风险；缺记录不判为0，跨里程碑不比较。原沟通规则保持独立；指标快照包含进度，更新后旧结果stale，风险接受不能沿用。材料包含coordination_progress.csv与快照；恢复校验历史对应、身份、时间和参与方，清空沿外键保留既有保护。

RED：后端阶段2用例缺行为失败（首轮路径书写修正后重跑RED），领域3用例缺模块失败，前端缺组件失败；GREEN阶段/领域5通过，协同相关10通过。篡改进度备份RED（错误被接受200）→GREEN6专项。实测/图纸输入RED缺模块→GREEN2。首轮一致性版本断言因误用201提前失败；纠正200后，以旧投影复现1!=2（version-red-real.txt），修复硬编码版本，最终阶段4通过。

完整`python -m pytest --basetemp docs/test-evidence/2026-10-23/STAGE-06/pytest-full -q`312通过（237.12秒），最后版本修复/新增断言后`python -m pytest backend/tests/test_stage06.py backend/tests/test_consistency_api.py backend/tests/test_consistency_domain.py backend/tests/test_material_package_api.py backend/tests/test_progress_domain.py --no-cov --basetemp .../pytest-final-focused -q`28通过；不同后端用例313，不冒称313全量一次。核心语句97.06%/分支91.15%，综合92.05%。前端`npm run test:coverage`178通过，语句84.29%、分支72.89%、函数83.17%、行90.29%；最终契约/展示专项38、lint/build/Black通过。覆盖排除未扩大。

浏览器：cockpit初轮27通过/1本地连接ETIMEDOUT，失败在saved-feedback写请求连接前；原测试无放宽重跑与新流程检查合计3通过。overview4通过，共32个不同检查通过。新增真实试验统计/样件流程/差异表、AB90%/30%与V2/V1预警、修订后指标失效、390窄屏。截图browser/。临时库验证，日常数据未重置。未接入车间进度、自动CAD或真实检测设备；进度、实测和外观输入仍需人工/明确合成样例。
