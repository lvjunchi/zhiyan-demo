# UX-COORD-COST 协同成本输入预填

2026-10-26，用户截图要求工时/演示费率也预填。关联协同、AC-15/20。开发计划P0与AGENTS已复核。

DEMO_COORDINATION集中配置独立合成成本样例3小时、120元/小时，字段显示单位及来源，可编辑或明确清空；仍仅点击重算才发送原API，空项保持null不当0，旧计算快照不自动更新。与协议、消息及进度原始记录分开，不伪称推算工时。无后端/数据库/迁移改动，Vite加载更新，服务不需重启。

RED：`npx --prefix frontend vitest run --root frontend frontend/src/panels/CoordinationPanel.test.tsx`退出1，新默认值断言收到null，1失败/9通过（red.txt）。实现预填后旧手输测试先清空字段，原数值提交断言保留。GREEN：frontend下`npx vitest run src/panels/CoordinationPanel.test.tsx`退出0，10通过（green-final.txt）；新增行为验证默认3/120、不自动计算、修改5/清空费率后提交5/null。

`npm run lint`退出0（lint.txt）；首次build因新测试mock返回CoordinationMetricRun不兼容Record类型退出2（build.txt），改为API声明的普通对象测试替身，未用any或弱化断言。最终`npm run build`退出0（build-final.txt），既有Vite主包体积提醒保留。无独立重构或覆盖排除，本次未重复全量后端/覆盖率，前轮356/211不是本次测试数。

`node docs/test-evidence/2026-10-26/UX-COORD-COST/live-readonly.cjs`退出0：实际5181有值，可修改/清空，禁止所有非GET业务请求，0写入/0页面错误，前后业务SHA相同，见live-readonly.json；截图cost-prefill.png。未点击真实项目重算、清空、恢复、重启或修改业务数据。指南、任务表、日志、决策同步。
