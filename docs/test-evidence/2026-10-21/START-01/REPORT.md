# START-01 启动与运行保障

2026-10-21；关联 AC-01/18/19/21。新增根目录 Start-Demo.cmd / Start-Demo.ps1 与 scripts/start_demo.py，本地运行，不联网安装或部署。

## 实现

- 只读预检：Python 运行依赖、Node、前端入口与安装包、数据库完整性、恢复指针与恢复文件、原库与副本隔离、端口范围和占用。缺失明确反馈，不替换数据或结束已有进程。
- 使用已有持久化副本启动器；工作库仅首次初始化。后端真实 health 的数据库连接及迁移版本通过，再启动前端；前端代理 health 通过后才打印系统就绪并打开浏览器。
- 子服务标准输入隔离，后台日志保存在 .runtime/，监管实际退出码和启动超时。输入 stop 回车或 Ctrl+C 走停止流程，仅处理本次持有的子进程。
- 退出前从 API 获取 JSON 备份，校验 Base64 和数据库字节 SHA-256，fsync 保存至工作副本旁 launcher-backups/；失败保留运行服务，等待显式重试。不会把备份失败当成功继续停止。
- 默认仍为 127.0.0.1:8027 / 5181；Windows 控制台 UTF-8。源库、恢复文件和用户工作副本均保留。

## 实际命令与证据

| 执行 | 结果 | 证据 |
| --- | --- | --- |
| python -m pytest backend/tests/test_demo_launcher.py --no-cov -q（初始空行为） | 退出 1；5 failed，端口/损坏库与恢复/health/超时/备份缺失行为 | [RED](red.txt) |
| 新增不完整前端安装用例（仅 Vite 存在） | 退出 1，缺少 React 安装检查；实现后全量通过 | [RED](red-incomplete-deps.txt) |
| launcher + persistent preview 专项 | 最终前置专项 7 passed；后来新增依赖检查纳入全量 | [GREEN](green-2.txt) |
| python -m pytest backend/tests/test_demo_launcher_runtime.py --no-cov -q | 退出 0；1 passed，双次真实启动、修订、退出备份、保留 ID/revision/value 与原库哈希 | [复演](runtime-2.txt) |
| cmd.exe /c Start-Demo.cmd -CheckOnly | 退出 0；真实 Windows cmd → PowerShell → Python 只读预检 | [入口](windows-entry.txt) |
| python -m black scripts/start_demo.py backend/tests/test_demo_launcher.py backend/tests/test_demo_launcher_runtime.py | 退出 0，最终格式整理 | [格式](black-final.txt) |
| python -m pytest backend/tests -q（最终格式/实现后） | 退出 0；249 passed，1 条既有 testclient warning | [完整回归](backend-full.txt) |

初次实现误列项目不使用的 multipart/docx 依赖，预检失败；按实际锁文件与标准库 DOCX 提取实现纠正，不新增不必要依赖。第一次真实启动复演失败：子进程继承输入导致前端/停止未按预期响应，测试超时仅清理该测试的独立进程树；日志 [runtime.txt](runtime.txt) 保留。隔离子服务 stdin、设 CI 环境后，真实复演通过；不是删除断言或放宽超时换绿。

Python app：语句 95.34%（5404/5668），分支 84.96%（1373/1616）；domain/** 核心分支 **90.50%**（505/558），语句 96.87%。见 [完整覆盖 JSON](python-coverage.json)、[领域汇总](core-coverage.json)。沿用 --cov=backend/app，启动工具属于运行编排，不冒充核心领域；未新增 app 业务排除。工具以独立端口、临时库、确定性失败与真实双启动测试验证。

## 范围与限制

没有自动安装缺失软件、恢复用户备份、重置已有数据或关闭外部进程。缺少预装依赖时给安装指引，不承诺空白环境离线安装。自动打开系统默认浏览器的桌面手动点击未单独录像；Windows 包装入口与 no-browser 完整双启动已实测。系统级磁盘故障、任意时点强杀与长期负载未在本轮完成。

原 data/demo.db SHA-256 保持 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。启动方式见根 README；本轮不签全部 AC。
