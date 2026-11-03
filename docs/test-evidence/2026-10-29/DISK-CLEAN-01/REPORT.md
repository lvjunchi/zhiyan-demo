# DISK-CLEAN-01 缓存清理与历史证据归档

日期：2026-10-29（Asia/Shanghai）。关联用户本轮明确清理授权、AC-01/19/21；无业务功能修改。

## 实际结果

- 使用 npm 自带 `cache clean --force` 和默认 Python 的 `pip cache purge` 清理下载缓存，两条命令均 exit 0；pip 报告移除1581个缓存文件。随后清理官方命令保留的 `_npx`，27040文件、257597225字节。npm 的 `--force` 警告来自其缓存清理命令，不代表安装依赖被删除。
- 逐目标检查绝对路径、链接及进程引用后，删除261个测试临时目录（约1.137GiB）和22个Codex `.staging-*` 副本（约2.959GiB）；保留当前Codex运行组件、已安装Python/前端依赖及Playwright浏览器。
- 历史证据5665个可读取文件、2043838114字节，归档为 `交付打包/历史测试证据_20261029.zip`（1145052441字节，约1.07GiB）。逐文件SHA-256与ZIP读取校验全部通过后，删除5572个已归档散文件、2043463149字节；报告和Git受管文件保留原位。
- 归档SHA-256：`f9f23e03b33d9be12500b88c284f5d4d21fb6914a36c37acf2e78d9f300dc179`。ZIP内含 `__archive_manifest__.json`，旁边保留 `.zip.sha256.txt`。
- 清理前后对466个源码、业务数据、参考文件等受保护文件的SHA-256比对全部一致；记录文档在该核对后更新。未清空/恢复数据库，未强杀进程，未修改权限，未提交或推送Git。

按磁盘可用空间快照实测：C盘增加14666674176字节，约14.67GB / 13.659GiB；D盘增加138543104字节，约0.129GiB。此为当时卷的净变化，不能用文件逻辑长度替代实际释放空间；历史证据归档仍占D盘约1.07GiB。详细快照见本地 `RESULT.json`。

## 运行与检查证据

| 操作 | 实际结果 |
| --- | --- |
| `py -3.13 docs/test-evidence/2026-10-29/DISK-CLEAN-01/cleanup.py` | exit 0；归档、校验、缓存和临时目录处理完成 |
| `npm cache clean --force` | exit 0 |
| `D:\Anaconda\python.exe -m pip cache purge` | exit 0 |
| `cleanup_npx.ps1` | exit 0；目标路径/链接/进程检查通过，目录已移除 |
| 默认Python运行 `scripts/start_demo.py --check`，使用临时空闲端口 | exit 0；Python、前端依赖、数据库和端口检查通过 |
| `git ls-files --deleted` | 空，无受管文件误删 |
| `python docs/test-evidence/2026-10-29/DISK-CLEAN-01/verify.py` | 最终exit 0；466受保护文件除5份预期文档更新外无变化，297个活动文档链接无缺失，浏览器保留、最终启动预检和Git差异格式检查通过 |

首次用额外安装的Python 3.13做启动预检exit 1，原因是该解释器没有fastapi/uvicorn/pydantic/pypdf；改用启动器实际默认的 `D:\Anaconda\python.exe` 后通过。两次原始结果分别保留在 `PREFLIGHT.json`、`PREFLIGHT-DEFAULT.json`，没有安装依赖或把失败改记成功。

归档后的首次文档验证exit 1，发现TASKS中HANDOFF-01旧README链接指向已归档散文件；保留原路径说明并将链接改为归档取回入口后，相同验证器exit 0、297链接无缺失。原失败记入 `VERIFY-FIRST-FAILURE.txt`，最终结果见 `VERIFY.json` 与 `PREFLIGHT-FINAL.json`。

纯文件清理不新增业务行为，RED/GREEN/REFACTOR及覆盖率不适用；未重跑全量业务测试、浏览器业务闭环或覆盖率，不将启动预检描述为完整验收。测试源码、当前运行依赖及浏览器仍保留。

## 跳过项与恢复方法

7个无权限目录保持原状：历史证据中 `2026-10-23/UI-Z5/pytest-{full,green,red}-isolated` 三项，以及C盘Temp中的 `zhiyan-empty-overview-cx12h4sw`、`zhiyan-empty-overview-ih6_gh8v`、`zhiyan-preview-e9wzpa79`、`zhiyan-preview-yevl63wd`。未强行接管权限。

查阅旧截图、命令日志、JSON时，将上述ZIP解压到独立临时目录。需要恢复报告中的相对链接时，把所需文件按ZIP内相对路径放回 `docs/test-evidence/`。原报告时间与历史测试结果保持不变；本轮新清理清单和校验记录保留在本任务目录，未包含在此前生成的ZIP中。

本地证据：`ARCHIVE-MANIFEST.json`、`ARCHIVED-REMOVED-FILES.json`、`RESULT.json`、`PROTECTED-BEFORE.json`、`PROTECTED-AFTER.json`、`NPX-DELETE-PLAN.json` 及执行脚本。它们不随公开源码自动上传。
