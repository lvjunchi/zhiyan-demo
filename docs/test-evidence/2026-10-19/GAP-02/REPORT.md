# GAP-02 · 工程决策独立版本（2026-10-19）

关联：O3/O4、AC-07/08/09/16/18；按 R1 顺序实施。

变更：014_engineering_versions.sql、engineering_versions.py、事务审计、设计引用、材料领域门禁、工程审核界面。

实际证据：最初 red.txt 是 xUnit setup 夹具错误，非有效 RED，最早版本实现 TDD 缺口保留。之后 red-domain-gate / red-revision-integrity / red-malformed-snapshot / frontend-red 是实际缺失行为；green-final.txt：工程 8 条 + 备份 8 条共 16 passed；手工输入引用与恢复审核留痕一致性有实际 RED（red-manual-reference / red-review-integrity）；最终全量见 VER-01。

限制：迁移只保留当时当前行；任意全图依赖未穷尽，旧更早历史不可补造。

完整命令、失败诊断、GREEN/格式化重跑、分层覆盖与数据保留见 ../VER-01/REPORT.md。本任务数包含在 R1 总数中，不重复叠加；历史无效 RED 不补造。

本轮仅独立库/本地临时预览，原库 SHA-256 保持 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0；启动见 README。
