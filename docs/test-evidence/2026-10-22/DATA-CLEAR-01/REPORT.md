# DATA-CLEAR-01：按授权清空业务工作区

- 时间：2026-10-22T10:53:00.792640+00:00；关联O1–O13、AC-18/19/21受控维护范围。用户明确要求清空后重新导入，未自动导入或代确认。
- 范围：原2个项目、96需求、4来源文档及下游设计/执行/样件/协同/4材料包全部归档后从当前工作区移除。保留原P01 UUID和项目入口、4型谱、7基础零件、5合成历史项目、编号计数及迁移；原审核/审计在旧库和备份中保留，新库仅有1条恢复审计。参考原件未修改。
- 完整备份：`D:/Pythontest/zhiyan-demo/data/backups/before-clear-20261022T105300057037Z/完整业务备份.json`，同时保存独立SQLite文件，均读回并校验。SHA-256：`9375b16da9a6ae22b8bb029d39a5d36d7283ab6b3078429a36070fd2da816ad6`。空白快照另存同目录。
- 使用现有GET backup / POST restore-preview / POST restore契约；预览后的当前hash必须仍与备份相同才切换，原活动数据库保留，未原地删除或重建data/demo.db。原demo.db SHA-256保持`edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`。

## 实际验证

1. `python docs/test-evidence/2026-10-22/DATA-CLEAR-01/clear_authorized_workspace.py`，退出0。备份校验、空快照结构/外键/完整性、恢复后逐表计数、原示例库hash均通过；原始结果见result.json。该脚本为本次授权的一次性操作记录，不是自动启动步骤。
2. `node docs/test-evidence/2026-10-22/DATA-CLEAR-01/live-check.cjs`，退出0。11页真实浏览器只读走查，无模块报错/页面异常/外网请求/写请求；需求待审核0、全部0。截图与live-check.json保留，总览截图已目视检查。
3. `python docs/test-evidence/2026-10-22/DATA-CLEAR-01/verify_isolated_import.py`，退出0。在临时空库导入fixtures/protocol_v1.txt得到13条草稿、稳定UUID及来源关联；重复解析幂等，重新打开应用仍为13。最后检查日常库需求和文档仍为0。既有Starlette/httpx弃用提示不影响退出码。

## 限制与使用

本轮为数据维护，未改产品实现；无新增产品功能的RED/GREEN、全量回归及覆盖率重跑，不将专项通过称为全部AC重新验收。用户待导入的新文件尚未提供/执行解析，不承诺任意文件的识别效果。

服务保持运行：http://127.0.0.1:5181/，刷新后进入协议解析与澄清→选择协议文件→核对正文→导入并解析→需求清单审核。支持UTF-8 TXT、文本PDF、DOCX，无OCR。重启仍使用空白活动工作区，不回填示例。恢复旧业务可在系统设置验证并恢复上述完整业务备份JSON。
