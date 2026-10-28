# UI-R：计算结果弹窗与产品名称

关联 O2/O6、AC-05/18/20/21。产品名称统一为“智研引擎 · 智能研制平台”；Top-3 与相似项目结果使用宽幅弹窗，保留版本依据、匹配差异、缺失项和评分口径。缓存查看不发起新计算；选用基型仅填入分析输入，不自动分析或审核。失败在弹窗内显示并显式重试，计算中使用计算提示。

- RED：`npx vitest run src/panels/BasesPanel.test.tsx src/panels/DesignPanel.test.tsx`，退出1，3失败/5通过；失败为缺少预期的计算结果 dialog。原始 red.txt。
- GREEN：相同命令退出0，8通过，green.txt。
- REFACTOR 完整验证：`npm run test:coverage`，96通过/22文件；`npm run build`、`npm run lint` 均退出0，lint零警告。
- TS 语句84.37%（1587/1881）、分支67.72%（1152/1701），函数84.84%、行88.70%。排除 main.tsx（启动装配）、src/test/**（测试支持）与测试文件，未新增排除。
- `npx playwright test --config playwright.cockpit.config.ts`：13通过；review 配置：1通过。14个不同浏览器检查，截图含桌面/手机。缓存重开、选用意图、键盘、失败与真实业务走查通过。

后端无改动，本轮未重跑pytest/Python覆盖；R2端到端配置未重跑，不能据此签署全P0。后续 UI-S 新增变型结果弹窗，并对最终源码重新全量验证。UI-R/live-state.json 是材料更新前的历史只读快照，不作为当前就绪依据。
