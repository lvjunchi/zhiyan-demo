# STAGE-04 需求表格与审核交互

范围：会议15/16/17，O1及AC-04/07/08/18/20/21。增加分类/排序/定位、勾选范围、后端只读批量预览与整批事务提交、逐条UUID审核、弹窗修订、底部可点击状态图。源文档/阻塞/字段/审核/版本在提交时重检；hash变化409，任一不合格全部不提交；保存后读失败明确提示仅重读。

RED：`python -m pytest backend/tests/test_requirement_batch.py --no-cov --basetemp docs/test-evidence/2026-10-23/STAGE-04/pytest-red -q` 退出1，6失败（缺接口）；`npx vitest run src/panels/Stage04.test.tsx` 退出1，4失败（缺交互）。GREEN：后端6、前端4专项通过。重构原单条确认复用事务内helper，不改变原审核规则。

完整：`python -m pytest --basetemp docs/test-evidence/2026-10-23/STAGE-04/pytest-full -q` 303通过（207.50秒），核心领域语句96.93%、分支90.75%，综合93.11%。`npm run test:coverage` 172通过，语句85.69%、分支75.66%、函数86.68%、行91.05%；`npm run lint` 无警告；`npm run build`通过。Black通过。前端无独立领域层，核心范围backend/app/domain/**，既有覆盖排除未扩大。

浏览器：overview4通过；cockpit初次24通过/1失败，失败为弹窗输入13px低于可读性14px门槛；实际修复为15px后readability2复验通过，共29个不同检查通过，不累计重复。截图browser/。初轮旧测试的inline表单步骤已更新为打开弹窗，断言保留；搜索加入原文后为档位测试夹具补正确原文；状态图新增同名文本后使用明确审核按钮断言。构建初轮unknown收窄错误已修复。所有初轮失败日志保留。

仅临时测试库，未清空日常数据。日常仍旧后端，需正常退出后重启加载新服务。批量确认需要人工核对勾选，不自动解决阻塞；不包含权限/模型能力。后续按顺序开始第5组。
