# UI-T：协议问题与协同记录右侧抽屉

关联：O1最小问题闭环、协同引擎；AC-04/07/15/18/20/21。依赖UI-Q共享DetailOverlay及现有问题/协同API。按用户顺序先实现问题处置，再实现沟通记录；没有更改后端业务规则或日常保存数据。

## 交付行为

- 协议解析与澄清 → 问题闭环 → 关闭/重开：打开右侧抽屉，集中展示原文位置、摘录、阻塞、建议、上次处置及追溯标识，明确人工提交。关闭/Esc不提交；同一问题本页输入保留，另一问题/项目清空。错误在抽屉内显示，重试保留意见和证据；成功按API返回对象更新原行并收起，焦点回到变为关闭/重开的原按钮。
- 协同风险 → 议题 → 查看沟通记录/导入沟通记录：同一右侧抽屉展示议题范围、参与方、记录时间线及导入表单；导入入口定位编号输入，查看入口定位关闭按钮。保存后更新记录、清除已提交编号/摘要/响应对象；已有指标保留原计算快照，提示另行重算。不同议题和项目不带入旧输入。
- POST失败保留输入；POST成功而GET刷新失败明确区分，禁用再次导入并提供只重试读取的按钮，避免重复写入。保存/刷新中禁止关闭，关闭本身不产生业务动作。
- 共享DetailOverlay增加可选initialFocus引用，在原生showModal之后定位指定输入；原有弹窗默认焦点不变。正文独立滚动，手机单列表单、时间线自动换行。

## RED → GREEN → REFACTOR

1. `npx vitest run src/panels/ParsingPanel.test.tsx`：RED退出1，3失败/3通过；缺少问题dialog，含既有重开路径增加的dialog断言。实现后GREEN退出0，6通过。issues-red.txt / issues-green.txt。
2. `npx vitest run src/panels/CoordinationPanel.test.tsx`：最终RED退出1，4失败/2通过；缺少抽屉入口、当前导入表单直接出现在主页面。实现后GREEN退出0，6通过。coordination-red.txt / coordination-green.txt。
3. 初次真实浏览器专项：1通过/1失败，导入输入未获得焦点；保留drawers-initial.txt。将焦点初始化移入DetailOverlay，在showModal之后执行，未删除焦点断言；重跑2通过（drawers.txt）。
4. 初次构建发现新RTL测试使用不支持的exact选项，退出2；保留build-initial.txt。移除冗余选项，断言保留；最终构建退出0。
5. 最终 `npm run test:coverage`：退出0，**103通过/22文件**。TS语句85.08%（1654/1944），分支68.35%（1201/1757），函数85.49%（548/641），行89.32%（1398/1565）。main.tsx排除启动装配，src/test/**排除测试支持，测试文件排除自身；无新增排除。该分支比例是前端UI全量，非Python核心领域门禁。
6. `npm run build`、`npm run lint`：退出0，lint零警告。原始frontend-full.txt / build.txt / lint.txt。
7. `npx playwright test --config playwright.cockpit.config.ts`：退出0，**15通过**；review配置退出0，**1通过**。共16个不同浏览器检查，不将专项重跑/历史轮次相加。使用临时数据库、8049/5199及8050/5200端口，不复用日常数据。

新专项覆盖真实问题关闭/重开及API读回、取消未写、失败保留、保存中Esc阻止、手机边界/焦点；协同记录初始展示、导入失败重试、响应对象真实持久化及第二议题隔离。既有全部弹窗、主工作台、真实审核、备份恢复/API故障及九模块走查通过。桌面/手机截图已视觉检查。

## 日常只读核验与边界

`node docs/test-evidence/2026-10-22/UI-T/live-check.cjs`退出0，日常5181的两处抽屉可打开，导入输入定位正确，关闭恢复原按钮，无写请求/页面异常。live-check.json及两张live截图留档；不加入16个隔离浏览器检查计数。原data/demo.db SHA-256仍为edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0。

后端未修改，本轮未重跑pytest/Python覆盖或R2专项；不签全部P0、不宣称生产混沌测试。未替用户关闭真实问题、导入沟通记录或进行人工审批；未重置/恢复日常工作库。未提交草稿仅当前页面内保留，不承诺刷新/跨模块后保留。
