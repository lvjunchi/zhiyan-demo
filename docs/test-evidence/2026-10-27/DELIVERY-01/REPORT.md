# DELIVERY-01 项目精简交付包

2026-10-27；用户要求发送给别人、压缩包小于1GB。关联AC-01/17/19和交付可复现性，无业务规则改动。

## 产物与范围

- `交付打包/zhiyan-demo_20261027.zip`，50,944,667字节（50.94MB / 48.58MiB），小于1,000,000,000字节；4,980个文件。
- SHA-256：`ba7f69813ef0aec448c3a4e1bbdab50e6c5997c4a62346f95a8b55ee12dc28bb`；旁附`.zip.sha256.txt`。
- 解压后文件内容约163.68MB（不含清单自身）。包含前后端源码/测试源码、锁文件、Windows x64前端依赖、最新构建、启动器、操作指南、参考文件、演示协议及独立样例、当前活动工作库的一致性快照、完整初始展示库与恢复JSON。
- 排除Git、IDE配置、运行日志、缓存、历史截图/视频/覆盖率产物、自动化测试浏览器、旧测试库、重复备份、旧恢复指针和临时文件。历史测试只附REPORT.md摘要，大体积原始证据不在交付包内。
- 使用SQLite备份API读取真正的活动库，校验后以独立`data/local-preview/workspace.db`发送，避免把恢复前的旧库当成当前状态；不拷贝旧指针及整批历史恢复目录。不包含浏览器未提交草稿。原项目及业务数据未删除、重置或恢复。
- 启动器优先使用完整初始展示源，过时的`data/demo.db`未附带；不影响本包的启动路径。复制品的初始展示manifest改为相对路径；参考原件保持只读。
- 包内`00_先看这里.txt`说明安装、当前状态、恢复初始、从头操作及精简范围；交付副本的老师说明同步最新批量审核口径。原始业务文件未编辑。

## 实际检查与命令

1. `npm run build`（frontend），exit0。原有549.63kB JS chunk体积提示保留，不影响打包。
2. `python docs/test-evidence/2026-10-27/DELIVERY-01/package_bundle.py`，exit0。按明确白名单打包，逐文件生成SHA-256清单，ZIP CRC检查通过，大小小于十进制1GB。
3. `python docs/test-evidence/2026-10-27/DELIVERY-01/verify_bundle.py`，exit0。实际解压最终ZIP，对4,980文件检查路径安全、排除项、长度与全部SHA-256；两份DB分别校验哈希、全部表计数、integrity_check及foreign_key_check。
4. 在独立解压目录用`Start-Demo.ps1 -CheckOnly`检查，exit0；再用包内原启动器在独立64765/64766端口启动。健康返回数据库connected、迁移018；前端页面、TSX转换及代理`/api/projects`均HTTP200并有项目。输入`stop`正常退出exit0，产生并验证1份退出备份。检查只运行在解压的独立副本，未停止或写入8027/5181的用户服务。
5. 在实际解压包执行`npm run build`，exit0，证明附带Node依赖/本机原生模块可用于当前Windows x64环境。清理本次自建临时目录；保留ZIP和校验文件。

原始输出：`package-result.json`、`verification-result.json`、`EXTRACTED-PREFLIGHT.txt`、`EXTRACTED-STARTUP.txt`、`EXTRACTED-BUILD.txt`。组装/验证脚本只属于本次交付证据，不属于新增业务功能。

## 排查与限制

首轮组装尝试附带旧demo.db时，完整备份校验发现其结构版本过旧，正确失败，未产生最终ZIP；随后排除这个无须使用的备用库。首次临时目录清理遇到未关闭SQLite连接/复制的只读文件，改为显式closing及仅对自建副本的安全清理，最终完成。一次组合PowerShell清理命令被自动审核拦截未执行，改为校验绝对路径后仅清理本次自建临时目录成功；未触及用户文件。

不声称空白电脑离线运行：接收方仍需Python与Node.js（本机验证Python3.12.4、Node24.14.1），首次按包内说明安装Python依赖；如Windows架构不一致需重装前端依赖。未附运行时安装器/便携Python，不含生产连接或模型密钥。未在另一台真实电脑测试；未重复全量领域回归或覆盖率，无业务代码变化。RED/GREEN/REFACTOR不适用本次交付组装；未虚构测试失败或覆盖率结果。
