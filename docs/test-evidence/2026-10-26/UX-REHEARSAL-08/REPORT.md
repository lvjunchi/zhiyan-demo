# UX-REHEARSAL-08 本轮复演反馈

日期：2026-10-26；关联本轮1—8（第9项无具体内容）、O9/O10/O12、两引擎、AC-11/13/14/15/18/20。仅前端交互、合成预填和文档，后端判定及用户业务数据不变。

## 完成内容与边界

- 批量工程提交按钮在portal弹窗内使用独立primary-action蓝底白字，勾选核对声明和范围检查仍必需。原本按钮继承弹窗白底；不是批量API失败。
- “记录执行”原来仅在表下切换填写区，无滚动/焦点反馈。现点击立即定位并聚焦执行工况，按钮蓝色/aria-expanded、表单边框和版本提示标明当前对象；明确“提交执行记录”才保存。保存结果提示放到填写区附近。重复点击同一版本保留输入，新版本不沿用旧草稿。
- 静扭点击入口后从项目需求API按load_basis_requirement_id及用例引用revision读取已确认/current的N·m数值。初版2600、新版2800均来自实际关联；不写死2600，不使用过期需求预填。缺失、未确认、跨项目、版本不符、单位未知或数值非法时加载留空并提示手工核对；异步读取不覆盖已编辑/清空的加载值，切换对象或卸载不回填旧请求。后备系数2.6为配套04的独立合成样例，可编辑；预填不保存、不确认、不代替后端判定。
- 样件“确认比对”写入成功自动关闭明细并返回原按钮，列表显示结果。保存失败留窗，确认保存但重读失败在列表提示并仅重读，不再次写审核；可重新打开查看结果和记录复检。
- 当前一致性报告total=0且current时补充“本次检查未检出一致性冲突；此结论仅对应本次输入快照，不代表全部试验已完成”。零值为当前冲突计数，不是工程数据数目。未知/无报告/stale不据此显示当前零冲突提示，不向用户库自动插入演示冲突。
- 标准演示议题首次点击“导入沟通记录”预填发起消息；导入成功且重读获得该原消息后，自动预填回复并关联实际保存的外部编号，原编号手动修改也适用。同议题关闭重开保留草稿。普通议题保留手工填表，样例按钮仍可显式使用；采用议题参与方、窗口内时间和未占用演示外部编号。回复必须引用真实已保存的原消息，不能生成不存在的响应对象。首条发起消息无上游，响应编号保持空，标签/占位/说明明确回复时填写。仅输入模板，不发送任何外部消息。

## TDD 与实际验证

命令工作目录为 `D:/Pythontest/zhiyan-demo/frontend`；所有输出留在本目录。浏览器使用原有隔离临时库配置，未操作日常用户数据。

| 阶段 | 命令 / 证据 | 实际结果 |
| --- | --- | --- |
| RED | `npm test -- --maxWorkers=2 src/panels/TestingPanel.test.tsx src/panels/SamplesPanel.test.tsx src/panels/CoordinationPanel.test.tsx src/panels/ConsistencyPanel.test.tsx`，RED.txt | exit1，5失败45通过。缺失行为：执行加载/焦点预填、样件确认成功关窗、已保存重读失败后在列表恢复、沟通首条/回复预填、零冲突说明 |
| GREEN首轮 | 同上，GREEN.txt | exit1，48通过2失败。旧测试直接在预填2.6上追加2.5得到2.625；另一个旧测试未保存原消息却期待回复引用DEMO-MSG-01。分别改为清空再编辑、明确断言须先保存原消息，保留提交数值和真实关联检查，不放松产品校验 |
| GREEN复验 | 同上，GREEN-RECHECK.txt | exit0，50通过。静扭2600/2800关联、同版本草稿保留、不自动写入、样件失败留窗及重读、改名原消息的真实回复均通过 |
| 初次构建 | `npm run build`，BUILD.txt | exit2，仅新增测试夹具的TypeScript返回类型/unknown字段不匹配。补全ArtifactConfirmation、返回完整CoordinationRecord并明确字符串字段后BUILD-RECHECK.txt exit0，无运行时代码规避类型检查 |
| 全量覆盖 | `npm run test:coverage -- --maxWorkers=2`，COVERAGE.txt | exit0，36文件228通过；包含额外executionPreset纯函数边界，语句85.02%、分支74.98% |
| 浏览器 | `npx playwright test --config playwright.cockpit.config.ts execution-feedback.spec.ts details.spec.ts`，PLAYWRIGHT-COCKPIT.txt | exit0，6通过（文件名也匹配reduced-details），覆盖样件确认关窗/焦点/重新打开、390px边界、新执行入口和真实消息关联 |
| 浏览器 | `npx playwright test --config playwright.overview.config.ts demo-usability.spec.ts`，PLAYWRIGHT-OVERVIEW.txt | exit0，1通过；完整流程验证蓝色实际计算样式、原件上传/预填、评分、协同等 |
| lint及重构 | `npm run lint`，LINT.txt | exit0但发现新执行状态读取ref及既有文件选择器effect同步setState警告。将用于渲染的执行版本key改为state；文件选择器加载改为请求token并在finally仅结束自身请求，保留禁用期间取消旧回填行为，不抑制规则 |
| 重构后全量 | `npm run test:coverage -- --maxWorkers=2`，COVERAGE-REFACTOR.txt | exit0，228通过，语句85.02%(3158/3714)、分支74.94%(2887/3852)、函数82.65%(977/1182)、行91.22%(2309/2531)，门禁满足 |
| 重构后浏览器 | execution-feedback.spec.ts（cockpit）、demo-usability.spec.ts（overview），对应REFACTOR输出 | 分别exit0，2+1通过，均为上述7个不同用例的重复复验，不累计成10 |
| 最终静态/构建 | `npm run lint`、`npm run build`，LINT-REFACTOR.txt、BUILD-FINAL.txt | exit0，lint无警告；保留既有>500kB构建体积提示，548.20kB主块 |

浏览器执行测试明确证明点击入口时runs写请求为0；手工改系数2.4、再点同一入口仍保留2.4，点击提交才产生1个新执行且后端返回fail，旧执行保留。沟通测试把原消息编号改为CUSTOM-ROOT-01，保存后回复自动关联它，重算得到2小时响应，不是写死DEMO-MSG-01或零时延。

前端覆盖排除沿用vite.config.ts：启动入口src/main.tsx、测试夹具src/test/**及测试文件src/**/*.test.{ts,tsx}。前端无独立领域层、分支门禁65%；后端核心领域90%门禁本轮未重跑，无后端/迁移/协议参考原件变化，不能将历史后端356通过作为本次执行结果。无新增测试排除/跳过或删除业务断言。

## 实际运行与文档

`node docs/test-evidence/2026-10-26/UX-REHEARSAL-08/live-readonly.cjs` exit0。实际5181新浏览器会话仅打开TC-007入口，观察2600/2.6预填，检查1440/390px无页面溢出，并查看零冲突提示。0业务写请求、0页面异常，前后系统备份SHA均：

`769d198912a30857e62348d4ff998d1248801fda3ebfe965038efc0ffb4fec3f`

见LIVE-READONLY.json/txt和live截图。该检查没有提交执行、确认比对、导入沟通、清空、恢复、重启或重导实际项目；写入测试只在隔离库。已查看执行预填和沟通回复截图，预填合成来源及保存动作可辨认。

主操作指南、任务表、开发日志、决策、文档索引与验收摘要同步。刷新当前前端即可继续，保持后端原有审核、版本失效、冲突规则；无需为了展示而恢复初始状态。用户可在基础流程完成后另演示2.4静扭失败或超差样件，再进行真实一致性复检/闭环。
