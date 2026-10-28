# CLEAN-03 项目磁盘瘦身

2026-10-22。用户授权删除多余文件、缩减项目占用。关联交付维护、AC-19/21；本轮不修改业务行为，不重新签署业务验收。

## 实际结果

- 删除 **0 个文件**。两次原生 PowerShell 删除请求均在启动前被自动审批拒绝，返回 `blocked by policy`，未执行；没有改用其他工具绕过拒绝。
- 完成 `frontend/node_modules/` 与 `docs/test-evidence/` 的 NTFS 无损压缩；路径、内容和使用方式保留，不需要手动解压。依赖、测试浏览器和历史证据仍在，未联网下载。
- 同一项目文件集合逐文件 `GetCompressedFileSizeW` 汇总：压缩前 **1,324,234,323 bytes**，压缩后检查时 **978,800,136 bytes**，减少 **345,434,187 bytes / 329.43 MiB**。约从 1.23 GiB 降至 0.91 GiB；后一个数字包含当时已经新增的本轮记录，不含此后生成的少量文档。逻辑文件大小基本不变；不把磁盘空闲量波动当作测量结果。
- 识别的 1,324 个可重建文件合计 45,310,631 bytes（43.21 MiB）仍保留：Python/pytest 缓存、覆盖率副产物、前端构建、Vitest 缓存、TypeScript 构建缓存和测试运行标记。失败浏览器 trace/error-context 单独保留，未将其当作普通缓存。

## 命令与检查

1. 原生 PowerShell 计划删除：逐项解析绝对路径、限定工作区、拒绝重解析点、核对文件 SHA-256 后 `Remove-Item -LiteralPath`；自动审批拒绝，进程未启动。随后单独明确路径删除 `.vitest-cache` 同样被拒绝；没有实际删除或伪造退出码。
2. `compact.exe /C /S:D:\Pythontest\zhiyan-demo\frontend\node_modules /I /Q /A`，退出 **0**，见 [依赖压缩日志](compress-dependencies.txt)。
3. `compact.exe /C /S:D:\Pythontest\zhiyan-demo\docs\test-evidence /I /Q /A`，退出 **0**，见 [证据压缩日志](compress-evidence.txt)。两项只修改上述目录的文件系统压缩属性，未使用系统级 CompactOS。
4. `python scripts/start_demo.py --check --backend-port <空闲本地端口> --frontend-port <另一空闲本地端口>`，退出 **0**，依赖/数据库/端口检查通过；实际命令保存于 [启动检查](launcher-check.txt)。不停止现有服务，不启动或替换日常工作库。
5. `PLAYWRIGHT_BROWSERS_PATH=0` 下用本地 Playwright 启动 headless Chromium，`setContent` 后核对标题并关闭，退出 **0**，见 [浏览器检查](browser-check.txt)。没有网络导航或业务 API 写入。

## 内容保护与并行变化

- [压缩前记录](before.json) 保存文件数、体积、受保护内容汇总 SHA-256 和候选缓存逐文件哈希。[压缩后记录](verification.json) 如实保留初次汇总校验不匹配（退出 1），没有改成虚假的通过。
- 差异来自同时新增的 `docs/TASKS.md` UI-Y 任务段。仅在内存中去掉该段、按原换行计算，**7,014 个受保护文件**的路径/大小/内容汇总重新匹配压缩前 SHA-256；见 [并行变化核对](concurrent-change-verification.json)，退出 **0**。没有回退或覆盖该任务段。候选缓存逐文件哈希也均未变化。
- 汇总保护排除：本轮自身证据、明确候选缓存（另有逐文件校验）、运行日志 `.runtime/`、运行中 SQLite WAL/SHM、活动 Vite 缓存。运行中日志/共享内存变化不宣称为静态内容。
- 源 `data/demo.db` SHA-256 为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`。数据、备份、恢复指针、原始参考资料、IDE 设置、源码、锁文件、历史验收文件均未被删除。

纯文件系统维护，无业务实现或新的覆盖排除；RED/GREEN/业务全量测试和覆盖率本轮**未执行/不适用**，不引用旧结果冒充新运行。未改启动入口，日常仍使用 `Start-Demo.cmd`。进一步删除被自动审批阻止，缓存占用保留并已明确披露。
