# UI-M 各页面业务化展示

2026-10-21；关联 AC-13/15/20/21，依赖 START-01/UI-L。只改展示与连接重试，不另设前端通过规则。

## 交付行为

型谱需求版本改为可展开的编号/版本/目标/追溯标识表；候选评分依据折叠，受控字段与枚举中文化、权重按百分比、评分保留一位显示精度。保存数据与计算口径不变。

一致性证据以中文字段递归展示，零值、空值、未知补充证据仍保留，不再打印 JSON。对象类型/审核/处置中文化。试验执行汇总与覆盖分开，模式、解析结果和样件审核状态中文化；协同窗口格式化、缺席率百分比、人民币以元显示。规则/模拟/人工身份仍可区分。初始项目读取失败后显示启动说明与重试入口，不重置项目。

## RED / GREEN / 最终回归

- [red.txt](red.txt)：5 failed / 27 passed，退出 1。其中版本依据、检查证据、执行统计、协同比率四项为真实缺失行为；App 重试测试误用不存在的 getOverview mock，**这项不计有效 RED**，实现后才改正，不能追认完整 test-first。该缺口与历史 AC-21 限制一起保留。
- [red-scoring.txt](red-scoring.txt)：评分依据折叠与受控字段/枚举业务化断言真实失败；随后实现，最终同范围通过。
- [green-2.txt](green-2.txt)：前期五文件 32 passed。第一次完整回归仍要求 360 CNY 的旧显示断言失败，按明确中文币种显示改成“成本：360 元”，金额、规则、审核行为断言保留，未删除业务断言。
- 最终 `npm run test:coverage`：退出 0，**80 passed / 22 文件**；[coverage-final-2.txt](coverage-final-2.txt)。TS 语句 83.07%、分支 66.45%、函数 83.66%、行 87.56%。既有 main.tsx、src/test/**、测试文件排除不变；UI 分支不冒充领域分支。
- 最终 `npm run lint`、`npm run build` 退出 0，10 条既有 effect 警告；[lint-final.txt](lint-final.txt)、[build-final.txt](build-final.txt)。GREEN 后补充评分及文案整理，再次全量回归与构建验证。
- 最终 `npx playwright test --config playwright.r2.config.ts`：退出 0，**7 passed**；[browser-final.txt](browser-final.txt)。真实独立 API/SQLite、端口 8048/5198；保存版本与后端返回逐项核对、检查依据、模式、重试恢复、变更定位、预览与多视口回归。

截图：[版本依据](business-versions.png)、[冲突依据](business-conflicts-1440.png)、[服务不可达](startup-unavailable.png)。新代码未覆盖旧证据目录，原件只读；未改用户项目状态。

完整后端回归与启动复演见 [START-01](../START-01/REPORT.md)。复杂文档泛化、全部依赖类型和长期混沌仍非本轮完成范围；不以本轮测试数推定全部 P0 验收。
