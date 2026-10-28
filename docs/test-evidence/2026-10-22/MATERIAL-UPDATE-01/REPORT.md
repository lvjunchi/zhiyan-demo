# MATERIAL-UPDATE-01：当前材料快照更新

关联 O13、AC-16/17。按用户明确要求更新日常进度的旧版材料；这是运行现有API的业务操作，不是新增判定规则，无新增RED/GREEN。独立测试中的材料门禁与导出回归见UI-S。

2026-10-22 12:06（Asia/Shanghai）先GET `/api/system/backup` 保存 before.json；验证database_base64解码的SHA-256为 2cf94e0d3265a36c9f15e82ad43d35ef7987815c3dfb3d3f662cd7a5d6cc74d1。未恢复、重置、覆盖用户数据库。

POST `/api/projects/6509d027-9457-4203-8189-3a905c064844/material-packages`，include_originals=false，actor=演示工程师，生成 **MP-P01-002**（0f6cf91d-2c02-4a38-9406-cf4a55777cc1）。新包requires_regeneration=false；总览API已指向该包，旧包保留历史。

当前状态为 **draft**，11条阻断：DFMEA V12未确认/待重新确认两条提示，以及1项变型点+8项复用件决策V2未审核。设计评审已由用户确认，未替用户执行工程签核。先在型谱页逐项核对“查看版本”，再到设计成果确认当前DFMEA；完成后重新生成材料，后端重新检查门禁，满足后才可人工批准冻结。

下载 MP-P01-002.zip（31604字节），整体SHA-256验证 f84d32b19c8a17b65afd9679d0e51d3640d34629b76e34bc2626e6327d11e398。ZIP共13项，manifest列出的12项文件哈希逐一匹配；生成快照/门禁及审批保持真实。原始响应new-package.json、校验verification.json和overview-after.json留档。原data/demo.db SHA-256仍为 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。

此状态是记录时的现场状态，之后编辑/确认需要重新生成快照；更新旧包不等于自动通过全部门禁。JSON备份不是O13材料包。
