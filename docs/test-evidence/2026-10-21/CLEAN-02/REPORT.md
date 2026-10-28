# CLEAN-02 实际磁盘清理

日期：2026-10-21。用户明确要求“释放磁盘空间，将废弃的和多余的可以删除了”。本轮执行删除；CLEAN-01 当日仅归档的历史记录保持原样。

## 删除结果

| 批次 | 文件数 | 文件逻辑体积 | 清单 |
| --- | --- | --- | --- |
| 已隔离废弃产物、pytest 与根目录工具缓存 | 166 | 22,873,497 bytes | [deleted.json](deleted.json) |
| 本轮测试后可重建 HTML 覆盖报告、运行结果与 Python 字节码缓存 | 88 | 1,911,202 bytes | [after-tests-deleted.json](after-tests-deleted.json) |
| 合计 | **254** | **24,784,699 bytes / 23.64 MiB** | [最终核对](final-verification.json) |

这是已删除文件的逻辑大小，不把系统磁盘空闲量增量作为精确测量；工具运行后缓存可能重新生成。保留本轮新构建，便于预览验证。旧隔离目录内的初始模板、停用样式、历史构建/测试副产物已清除；其历史路径/哈希仍可由 CLEAN-01 清单追查。

## 执行与保护

- 使用原生 PowerShell Remove-Item -LiteralPath；每个目标先解析绝对路径，必须严格位于工作区，且与明确候选路径一致；拒绝重解析点。
- 执行命令：`& .\docs\test-evidence\2026-10-21\CLEAN-02\cleanup.ps1`、`& .\docs\test-evidence\2026-10-21\CLEAN-02\cleanup-after-tests.ps1`；均退出 0。脚本保留作本次执行记录，非周期清理任务。
- 两次删除前均保存逐文件路径、大小和 SHA-256，见 [初始计划](deletion-plan.json)、[测试后计划](after-tests-plan.json)；删除后验证目标已不存在。
- 参考目录 reference/、参考文档/，data/ 全部业务库/备份，以及 10-19/10-20 历史验收证据共 **697 文件**核对 SHA-256，变化 **0**。清单：[保护基线](protected-before.json)。本轮 UI-L 日志/截图保留在独立证据目录。
- data/demo.db SHA-256 仍为 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。
- 保留约 881 MiB frontend/node_modules 安装依赖以维持已安装环境离线运行；保留六份历史文档/样式快照、源码、锁文件、用户 IDE 设置及参考原件。未清理其他项目或系统临时目录，未重置演示状态。

界面验证另见 [UI-L](../UI-L/REPORT.md)，74 项前端和 5 项隔离浏览器检查及日常预览只读冒烟通过。纯删除整理不虚构业务 RED/GREEN，也不声称重新验收所有 P0。
