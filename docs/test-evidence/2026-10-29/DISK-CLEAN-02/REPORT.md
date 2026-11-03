# DISK-CLEAN-02 D盘开发与系统缓存清理

日期：2026-10-29（Asia/Shanghai）。任务来源：用户要求继续清理D盘。关联AC-01/19/21；不修改业务功能，不外传、不部署。

## 实际完成

清理前D盘空闲131206733824字节，结束快照143591616512字节；净增加12384882688字节，约12.38GB / 11.534GiB，结束时约133.73GiB可用。这是卷的实测净变化，不能把缓存逻辑长度直接相加当作实际释放量。

| 范围 | 实际处理 |
| --- | --- |
| `D:\Anaconda\pkgs` | 用Conda官方清理命令处理197个未使用包缓存（预览8330962137字节）、255个下载包（491170041字节）、索引及日志缓存；命令exit 0 |
| 上述缓存中的中断下载 | 逐文件核验路径、无链接、旧时间及无活动进程引用后，删除9个 `.partial`，155648000字节 |
| `D:\DeliveryOptimization` | 官方 `Delete-DeliveryOptimizationCache -Force` 成功；后查目录仅剩1个文件，逻辑大小接近0；未直接递归删除系统目录 |
| 项目可再生缓存 | 删除8个目录、约8.91MiB：Vite缓存、临时编译信息、`frontend/dist` 和后端Python字节码缓存；运行/构建时可能重新生成 |

项目此前约2.8GiB，已没有大量可丢弃的历史散文件。本轮保留源码、当前业务数据和备份、参考原件、前端依赖、浏览器、老师交付ZIP和DISK-CLEAN-01历史证据ZIP；未清理下载资料、回收站、其他项目工作文件或已安装应用。Conda包缓存由约18.818GiB降至约9.651GiB，剩余被使用的缓存保留，没有删除整个 `pkgs` 或 `envs`。

## 安全检查及验证

- 本机Conda 24.11.3帮助明确 `--packages` 不检查回指包缓存的软链接。因此先核对4个已注册环境、1048份包记录均为硬链接类型1，并遍历实际环境检查无回指包缓存的链接；再验证预览目标全部落在明确的D盘缓存目录。执行时设置 `CONDA_OFFLINE=true`、`CONDA_PKGS_DIRS=D:\Anaconda\pkgs`，未使用 `--force-pkgs-dirs`。
- 清理前后比较4个环境共268825个文件的相对路径、大小及mtime聚合SHA-256，并逐份比较包元数据SHA-256，完全一致。排除会由Python自行再生成的 `__pycache__` 及Conda临时垃圾目录；基本环境扫描不重复包含 `pkgs` 和 `envs`。此检查不冒充每个环境文件内容的SHA校验。
- 项目466个受保护文件在清理前后及最终运行检查时SHA-256一致，包括当前源码、业务数据和参考原件；记录文档在该核对后更新。`git ls-files --deleted` 为空。
- 默认 `D:\Anaconda\python.exe` 下实际导入fastapi 0.136.3、uvicorn 0.49.0、pydantic 2.13.4、pypdf 6.12.2成功；随机空闲端口运行 `scripts/start_demo.py --check` exit 0，Python、前端依赖、数据库与端口检查通过。没有重置、恢复或写入业务项目。
- 更新记录文档后，最终核对300个活动文档链接无缺失，Git差异格式检查通过、受管文件无误删；除4份预期记录文档外，受保护项目文件无变化。结果见 `FINAL-CHECK.json`。
- 纯缓存清理没有新增业务行为，RED/GREEN/REFACTOR及覆盖率重跑不适用；未重跑pytest/Vitest/Playwright业务全量，不宣称新的完整验收。

## 实际命令与本地证据

1. `py -3.13 docs/test-evidence/2026-10-29/DISK-CLEAN-02/cleanup.py`：exit 0。内部先dry-run，再执行 `D:\Anaconda\Scripts\conda.exe clean --packages --tarballs --index-cache --logfiles --json --yes`，exit 0。
2. `docs/test-evidence/2026-10-29/DISK-CLEAN-02/finish.ps1`：exit 0。清理9个旧partial文件，官方Windows缓存命令成功；本次无需提权，没有更改目录权限。
3. 默认Python的最终只读预检及依赖导入：exit 0，原始命令、端口、版本和输出见 `VERIFY.json`。

本地保留 `RESULT.json`、`CONDA-DRY-RUN.json`、`CONDA-CLEAN.json`、`ENVIRONMENTS-BEFORE.json` / `ENVIRONMENTS-AFTER.json`、`PROTECTED-BEFORE.json` / `PROTECTED-AFTER.json`、`PARTIAL-DELETE-PLAN.json`、`DELIVERY-CACHE.json`、`VERIFY.json` 与执行脚本。源码文档仅本地更新，未提交推送。
