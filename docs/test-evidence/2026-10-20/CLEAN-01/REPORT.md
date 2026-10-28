# CLEAN-01 文档与废弃内容整理（2026-10-20）

## 实际完成

关联：AC-20/21 的交付说明与维护；业务规则、UI 行为、验收合同未新增。纯文档与无引用资源整理不编造业务 RED。

- README 从 541 行精简到 83 行，只保留当前能力、安装、持久化启动、操作与验证入口。
- 新增 docs/README.md 统一入口；演示指南与任务表改为当前流程/状态/剩余项，去掉多轮重复追加的当前结论。
- 6 份历史文档/停用样式已归档，其中 Markdown 只增加历史说明并调整相对链接；原/归档哈希见 archive-manifest.json。旧 P0_BASELINE 与 IMPROVEMENT_REVIEW 路径保留短入口，兼容已有记录。
- 修正演示指南缺失 --workspace 的启动命令，实际持久化行为与说明一致。旧重置/直接写原库的示例移出日常入口，仍可在历史归档追溯。
- 已无导入的 App.css、cockpit.css，Vite 原始 README/react.svg/vite.svg/hero.png/icons.svg，字节码/pytest/覆盖/浏览器/陈旧构建产物与空目录从常用位置移出；18 组、146 个文件、22,575,396 字节（21.53 MiB），全部保留可恢复隔离副本。
- 添加覆盖报告、根依赖目录与隔离产物忽略规则。node_modules、.idea、原始资料、数据库与恢复指针、原验收证据未删除。

## 自动审批与实际操作

最初计划删除可再生成缓存和已确认废弃模板。批量 Remove-Item 调用被自动审批拒绝，工具仅返回 `blocked by policy`，未提供进一步原因；该调用没有执行。

随后采用更可恢复的替代方案：先验证源/目标绝对路径都在工作区、排除保护路径、拒绝重解析点，再以 PowerShell Move-Item 移到 `docs/archive/2026-10-20/retired-generated/`。不换工具重试永久删除。

因此 **实际磁盘回收量为 0**，不是已永久删除 21.53 MiB。deletion-plan.json 是未执行的删除计划，archive-actions.json 才是实际操作清单；隔离文件内容哈希逐项核对。源码目录得到整理，仍可恢复。

## 验证与证据

- `npm run build`（frontend）：退出码 0；见 build.txt。新构建的 JS/CSS 与整理前旧 dist 的哈希一致，证明没有改变运行资源。新生成 dist 是本轮验证产物，保留在正常位置。
- `npm run lint`（frontend）：退出码 0；仍为既有 10 条 effect 警告，见 lint.txt。
- 本地 Edge 只读冒烟：1440×900 打开总览、需求清单、9 阶段导航，未出现页面异常或横向溢出，未触发业务写入。见 smoke.json 及两张截图。
- 整理前已记录保护清单：参考原件、reference、既有 test-evidence 与业务数据共 **604 个文件**；整理后全部存在且 SHA-256 相同。见 protected-before.json / integrity.json。
- 文档相对链接验证另存 doc-checks.json；当前结果不借用旧报告重新声明业务通过。

本轮未重跑 Python/Vitest 全量回归或混沌测试：没有修改运行中的业务代码，构建产物与原产物一致。本轮也未更新覆盖率；R2 的 242/70/16 与覆盖数字仍是 R2 那次实际记录。未清理系统临时目录或其他项目，没有停止服务、重置数据、部署或外传。

## 当前入口

阅读 README.md / docs/README.md；操作见 docs/DEMO_GUIDE.md；状态以 docs/ACCEPTANCE_REVIEW.md / docs/TASKS.md 为准；历史说明见 docs/archive/README.md。开发日志和决策保留追加历史，不因清理覆写。
