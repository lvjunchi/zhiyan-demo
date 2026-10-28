# IMPORT-PROGRESS-RESTORE 协议页进度恢复

2026-10-26。用户反馈协议导入成功后切到其他模块再返回，顶部五步进度重置为灰色未开始。关联O1、AC-01/02/04/18/20。已读开发计划与AGENTS，不改协议原件、数据库或参考基线。

## 原因与最终行为

原phase仅在ParsingPanel组件useState中保存，页面卸载后回到idle；完成后核对草稿被正确清理，所以旧进度不会通过草稿恢复。导入文档/需求仍在后端，问题是显示状态丢失。

现在没有正在操作的正文/文件/核对草稿时，等待来源和处理记录读取完成，从当前项目的最近真实任务重建只读进度快照。标题显示最近任务及文件/文档/版本，完成为已保存；待核对、归档待解析、提取或解析失败、取消分别显示。缺来源/读取失败不虚构完成。使用后端记录时间排序及稳定对象ID，已关联来源不重复作为另一任务；切项目及显式清空后由新数据决定，不另设localStorage成功标志。

现有核对草稿和新选择/填写的任务优先，恢复不写库、不重导、不自动重试解析。纯正文输入的文件检查/提取显示不适用；完成不等于人工确认，来源摘要无待审核需求时明确显示无待审核，避免要求重复确认。

## RED、GREEN、重构

- RED：frontend下`npx vitest run src/panels/ImportProgress.test.tsx`退出1，4失败/1通过，red.txt。包括缺恢复函数及回到页面没有“结果已保存”行为；读取失败不误报完成的既有基线通过。
- GREEN：`npx vitest run src/panels/ImportProgress.test.tsx src/panels/ParsingPanel.test.tsx src/panels/Stage03.test.tsx src/importDrafts.test.ts`退出0，4文件22通过，green-final.txt。
- 覆盖完成恢复、较新失败/待核对/取消覆盖旧完成、已归档不能假称解析、手工正文、其他项目和空数据、切项目、新正文、读取失败、原核对草稿及重试逻辑。
- lint首次提示React Fast Refresh文件导出非组件函数（lint-final.txt），没有忽略或关规则。将只读恢复函数/类型抽至importProgressState.ts，ImportProgress仅呈现；同22项重跑通过（refactor.txt），最终lint-verified.txt无新增警告，build-verified.txt退出0，保留既有约540kB拆包提醒。

## 浏览器和实际运行

- `npx playwright test --config playwright.overview.config.ts`退出0，10通过，browser.txt。增强真实Word导入用例：切到需求页再返回完成5步；刷新仍5步；选择下一份文件转核对阶段且完成仅2步；取消及刷新不假显示完成。清空后草稿和旧记录隔离、原件SHA、无重复解析及项目恢复断言保留。
- 提取恢复函数后，`npx playwright test --config playwright.overview.config.ts import-resume`退出0，2项相关复验通过，browser-refactor.txt。为前述10中的重复，不累计成12个不同用例。
- `node docs/test-evidence/2026-10-26/IMPORT-PROGRESS-RESTORE/live-readonly.cjs`退出0，实际5181切换模块/刷新前后进度文本及步骤一致，桌面和390px无页面横向溢出，业务写请求0、页面错误0；live-restored/live-mobile截图已目视核对。
- 实际项目最近文件为流程演示协议，完成5步，摘要显示当前无待审核需求。检查前后业务SHA相同：`80a1ce379a9a1de2841c0f7659ca178951236fbf6e21bd3a34d1a515d5688db1`，见live-readonly.json。该值与上轮不同是本轮开始时的实际用户状态，不恢复成上轮SHA，不改用户业务以造检查场景。

本次纯前端显示恢复，后端既有API已返回project_id/updated_at，只补客户端可选类型；无API/迁移/判定变化，不重启服务。当前Vite已加载，刷新可见；未清空/恢复日常库，也不需要用户重新导入协议。

本轮没有重跑全量213前端、后端全量或覆盖率，不冒称本次结果；未修改覆盖排除。独立浏览器库允许的恢复/清空不影响日常库。文档主指南、任务表、日志及决策同步。
