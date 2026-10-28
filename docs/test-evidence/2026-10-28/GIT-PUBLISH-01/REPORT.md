# GIT-PUBLISH-01 首次公开源码提交

2026-10-28；用户明确授权提交并推送到`https://github.com/lvjunchi/zhiyan-demo`。关联交付复现、AC-01/19，无业务规则变更。

## 范围与本地准备

保留源码、启动器、锁文件、测试源码、合成演示资料和初始展示源；不上传当前工作库、历史恢复/备份、测试浏览器和依赖目录、大体积历史测试产物、交付压缩包、IDE/凭据配置或参考原件。历史测试只保留REPORT.md摘要；原始证据继续留在开发电脑。更新.gitignore和GitHub首次启动说明；本地业务文件未清空或恢复。

远程原有`main`，起点`e0418a8e7bc495e8e7786806745df9cdb004f3f6`（Initial commit，README）。仅fetch读取并以其为本地main基线，通过read-tree更新索引、不覆盖工作文件；新增项目提交将作为其后代，不强推或改写原提交。

## 实际校验

- 暂存区初次审计478文件、10,903,391字节，最大单文件1,951,548字节。审计读取实际Git blob，验证文件范围、大小及SHA-256，不扫描无关的Git对象缓存。后续只增加本报告和更新文档，提交前重跑审计。
- 常见GitHub/OpenAI/AWS令牌及私钥格式检查：初始备份的base64字符串首次命中AWS格式；核对后改为验证备份SHA-256并扫描解码后的实际数据库及JSON元信息，未发现命中。没有忽略实际数据库或降低规则来掩盖结果。
- `python -m pytest backend/tests/test_demo_launcher.py backend/tests/test_demo_launcher_runtime.py backend/tests/test_initial_showcase.py -q --no-cov --basetemp docs/test-evidence/2026-10-28/GIT-PUBLISH-01/pytest-verified`，exit0：12 passed，1条既有httpx弃用提示。首次命令因basetemp父目录未创建出现2通过/10个setup错误；创建独立证据父目录后用新的目录重跑通过，未改测试断言。测试只用独立副本，不操作日常工作库。
- `git diff --cached --check`发现既有前端文件末尾空行与只读开发计划书中的Markdown两空格换行；本轮未以公开提交为由改写参考文件或业务源码，不将这些格式提示误报成业务失败。
- 本轮无新增领域行为，RED/GREEN/REFACTOR及新增覆盖率不适用；未重复此前全量357后端/230前端/4浏览器回归，也未把历史数量计作本轮结果。

## 网络与推送状态

本机全局Git代理127.0.0.1:7897不可连接；仅对本轮网络命令临时传入空http/https proxy，未改变全局代理。公开读取和fetch成功，dry-run推送因缺少GitHub登录凭据失败，未上传任何项目文件。用户的公开推送授权已具备，不再重复请求；本地提交完成后使用Git Credential Manager官方登录流程认证，再推送并核对远程提交。

实际结果：主提交`f2eabb9f41e19b2aca695a2108f464e4623cfa89`已成功推送至origin/main，原e0418a8提交保留，479个受管文件约10.91MB；main已设置跟踪origin/main。后续仅补充本次核验记录。


## 完成补记

本地`git commit` exit0。Git Credential Manager浏览器登录命令返回账号lvjunchi已有凭据，说明最初dry-run的问题是未明确选择已有账号；无需用户重新输入凭据或打开网页授权。仅在本仓库设置credential.https://github.com.username=lvjunchi，随后`git -c http.proxy= -c https.proxy= -c credential.interactive=false push -u origin main` exit0，e0418a8→f2eabb9，跟踪建立。逐命令代理绕过不影响全局设置。原提交后git status干净；补记另作普通文档提交，不amend或强推。最终再次用ls-remote核对远程main与本地HEAD一致。审计脚本最终确认479文件10,908,393字节，最大单文件小于2MB，范围内凭据格式无命中；原始审计和测试输出保留本地、不上传。
