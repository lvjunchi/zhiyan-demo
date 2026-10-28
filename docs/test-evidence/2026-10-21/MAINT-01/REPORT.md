# MAINT-01 生命周期、状态隔离与覆盖门禁

2026-10-21；关联 AC-04/18/20/21。在 START-01/UI-M 完成后处理后续维护，不改后端工程判定或审核合同。

## 状态与渲染

九类模块以项目稳定 ID 作为工作区生命周期边界。切换项目时，新工作区使用独立初始状态，旧编辑、对象、错误与选择不会带入；同一项目的审核刷新继续保留未保存的需求修订。移除仅在初始挂载重复设置的同步 loading/error，刷新状态在用户事件中更新。

试验首次加载只请求 API，待结果完成并检查取消标记后应用状态；避免 effect 调用带有同步状态副作用的加载 helper。样件选择在选择事件中清空文件/测量/证据，DOM 文件输入也以样件 ID 隔离。没有禁用 lint 规则、定时器隐藏状态更新或吞错。

## RED / GREEN

| 范围 | RED | GREEN / 后续 |
| --- | --- | --- |
| 项目切换草稿/样件残留 | 退出 1；2 failed / 7 passed，[red.txt](red.txt) | 项目边界重挂载后专项 9 passed，[green.txt](green.txt) |
| 样件原生文件输入残留 | 退出 1；1 failed / 4 passed，原文件仍在输入框，[red-sample-file.txt](red-sample-file.txt) | 样件明细以 ID 区分 DOM 后，最终全量通过 |
| 覆盖门禁混合口径 | 退出 1；7 failed，高编排得分掩盖核心分支不足、边界/缺失/非法计数，[red-coverage-gate.txt](red-coverage-gate.txt) | 实现后 7 passed，[green-coverage-gate.txt](green-coverage-gate.txt)；Black 后全量后端再次通过 |

最终 `npm run test:coverage`：**83 passed / 22 文件**，退出 0；[coverage-complete.txt](coverage-complete.txt)。TS 语句 83.06%（1462/1760），分支 66.47%（1039/1563），函数 84.18%，行 87.60%。既有 main.tsx/测试工具/测试文件排除未变，不以 UI 分支代表纯领域。

最终 `npm run lint`：退出 0，**0 警告**；[lint-complete.txt](lint-complete.txt)。初次收敛后仍发现试验 helper 的一条警告，改用真实异步结果消费流程后清零，未修改 lint 配置。

## 独立覆盖门禁

新增 scripts/check_core_coverage.py，校验 coverage JSON 结构、整型计数与分母，仅计 backend/app/domain/**，分别要求语句 ≥80%、分支 ≥90%。缺失或非法报告明确失败；不能由服务编排覆盖率补高核心分支。

scripts/coverage_core.sh 改为全量 app 覆盖报告加该独立领域检查。Windows 本轮实际执行的是 pytest、coverage json、Python 检查器三个原生命令，未声称运行 Bash 包装器。最终检查 90.50% 核心分支通过，原始报告见 [VERIFY-03](../VERIFY-03/REPORT.md)。覆盖工具不作为业务领域来源排除，app 覆盖范围没有新增排除项。

前端构建与 20 项不同浏览器检查通过，最终样件 DOM 改动另由完整前端测试/构建验证。全项目 CSS 历史覆盖的逐条合并审计仍可后续开展；当前视觉层与既有几何规则职责明确，不宣称删除全部历史样式。
