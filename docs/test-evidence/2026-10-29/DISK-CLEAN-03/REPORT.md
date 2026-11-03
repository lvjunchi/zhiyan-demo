# DISK-CLEAN-03 按授权清理前四类文件，保留回收站

日期：2026-10-29（Asia/Shanghai）。用户明确授权清理旧安装包/重复副本、JetBrains索引缓存日志、旧更新文件/崩溃转储、uv/pnpm缓存；回收站不清理。关联AC-01/19/21，无业务功能变更。

## 实测结果

| 卷 | 清理前空闲字节 | 结束快照空闲字节 | 可用空间净增加 |
| --- | ---: | ---: | ---: |
| C | 155332435968 | 178781581312 | 23449145344字节，约23.45GB / 21.839GiB |
| D | 143590608896 | 144359235584 | 768626688字节，约0.77GB / 0.716GiB |

以上为当时卷的实测净变化，文件逻辑大小不等于实际释放量。结束快照约C盘166.50GiB、D盘134.45GiB可用。

## 清理范围

- C盘下载目录51个逐名称核对的2022—2024年旧安装包，12962407411字节（12.072GiB）。包括SHA-256相同的两份旧PyCharm安装包；重复副本不另加计数。保留DEBUG、LINK、MASM工具，以及用途未充分确定的 `install.exe`。未清理文档、压缩资料、D盘ISO或其他下载文件。
- JetBrains仅清理7个 `index` / `caches` / `log` 目录，7322个文件、7794747430字节（7.259GiB）。关闭状态经进程核验，无强杀；保留LocalHistory、plugins、workspace和其他配置。
- 3个明确的旧更新安装目录（WorkBuddy、VS Code、Reasonix），5文件、833776751字节（0.777GiB）；另清理8个旧 `.dmp`，271382668字节（0.253GiB）。
- `uv cache clean --cache-dir C:\Users\LvXiao\AppData\Local\uv\cache --offline --no-python-downloads --no-progress` exit 0，工具报告移除64508文件、1.6GiB。保留内置占用检查，没有使用 `--force`。
- 使用已安装的本地pnpm 11.25.0 CLI执行 `--store-dir C:\Users\LvXiao\AppData\Local\pnpm\store store prune`，exit 0；工具报告移除32750文件（578 MB）、457缓存包、2个未引用全局虚拟存储包及缓存元数据。该逻辑路径实际由Windows应用数据虚拟化重定向到当前账户D盘WpSystem的Codex包LocalCache，已逐字核对预期账户、包名和store/v11真实位置；因此本轮D盘也释放空间。

所有删除目标均先验证明确绝对路径、白名单/范围、无链接或junction及进程引用，清单落盘后再处理。uv/pnpm命令禁止联网及自动引导下载；未删除已安装运行依赖。

## 保留项与验证

- **没有清空C盘或D盘回收站。** 两盘当前账户回收站顶层条目及原始路径元数据（`$I`）摘要前后完全一致，见 `RECYCLE-BEFORE.json` / `RECYCLE-AFTER.json`。这是元数据对照，不冒充回收站全部文件内容的哈希检查。
- 1436个受保护的项目源码/业务/参考文件、IDE本地历史/插件/工作区及保留工具SHA-256全部一致，见 `PROTECTED-BEFORE.json` / `PROTECTED-AFTER.json`；记录文档在验证后更新。
- 已安装前端依赖的文件路径/大小/mtime摘要一致；两个交付/历史证据ZIP重新计算SHA-256，均与原有校验文件一致。没有重置、恢复或写入业务数据。
- 默认Anaconda Python实际导入fastapi 0.136.3、uvicorn 0.49.0、pydantic 2.13.4、pypdf 6.12.2成功；随机空闲端口运行 `scripts/start_demo.py --check` exit 0。原命令、端口和输出见 `VERIFY-RUNTIME.json`。
- 没有受管文件误删，没有提交推送。纯文件清理无新增业务行为，RED/GREEN/REFACTOR及覆盖率不适用；未重跑pytest/Vitest/Playwright业务全量，不宣称新的完整验收。
- 最终记录检查exit 0：302个活动文档链接无缺失、Git差异格式检查通过；1436受保护文件除3份预期记录文档更新外无变化，见 `FINAL-CHECK.json`。

## 执行过程中的失败与修复

1. 首次 `py -3.13 .../cleanup.py` exit 1：回收站存在失效链接，`stat()`尝试跟随目标而失败。发生在任何删除操作前。改为 `lstat()`读取条目本身、仅对普通 `$I` 文件取哈希，未处理或删除该回收站条目；原失败见 `FIRST-RUN-FAILURE.txt`。
2. 第二次同命令完成旧安装包/更新/转储、大部分IDE缓存及uv清理后exit 1：pnpm逻辑C盘路径与真实D盘位置不一致，安全断言暂停，pnpm尚未执行。另两个IDE索引因Windows长路径在预扫描中被跳过。原解释及路径见 `RESUME-REASON.txt`。
3. `py -3.13 .../resume.py` exit 0：严格核验两个索引根目录及全部子项无reparse point，用Windows扩展长度路径完成清理；逐项核验pnpm真实缓存路径，再离线执行官方prune。两个旧跳过记录保留并注明已解决，最终未解决跳过项为空。没有绕过权限或自动审批限制。

本地详细证据：`TARGET-PLAN.json`、`RESULT.json`（各目标完整文件清单及命令输出）、`DUPLICATE-VERIFIED.json`、`PNPM-CANONICAL-PATH.json`、`ARCHIVES-VERIFIED.json`、受保护文件/依赖/回收站前后摘要和执行脚本。回收站清空后无法从回收站恢复，其他恢复方式也不保证成功；本轮保留其内容。
