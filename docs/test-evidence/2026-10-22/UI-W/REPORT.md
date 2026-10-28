# UI-W：设计评审、样件比对与冲突证据整理

日期：2026-10-22。关联O7/O12、一致性引擎、AC-07/13/14/18/20/21的受控界面范围。按用户指定的设计评审→样件比对→冲突证据顺序逐项实施，每项先完成RED/GREEN与浏览器检查，再进入下一项。

## 实现与验收行为

| 任务 | 变更 | 保留和核验 |
| --- | --- | --- |
| UI-W1 设计评审 | 主区改为数量/编号摘要，完整检查清单集中“预览设计评审” | 完整预览补齐依赖需求列，标准/角色/来源/审核保留；主区生成/确认、版本状态、缺口及对象定位锚点保留，DFMEA评分编辑不受影响 |
| UI-W2 样件比对 | 新建时参数与实测合为一张表，已有比对只显示保存的结果表 | 期望值/公差/单位取保存结果；当前登记图纸来源单独折叠且标明范围，不替换历史基准；文件、视觉标识、确认、失败重试与对象隔离保留 |
| UI-W3 冲突证据 | 列表保留摘要/状态，完整证据集中抽屉 | 开放项“查看 / 处置”；关闭项“查看详情”只读回看处置意见、证据、处理人、时间及流转。原提交契约、失败输入保留、关闭焦点和状态分离保留 |

界面不新增通过判定、不替工程师签核；未修改后端、数据库结构或业务门禁。当前登记图纸的来源是当前登记信息，不宣称它就是历史比对保存时的原件版本。已关闭冲突仍保留完整查阅入口。

## RED → GREEN → REFACTOR

所有命令从frontend运行，日志保留在本目录。测试使用确定性替身或独立临时数据库，不使用日常数据制造冲突。

| 阶段 | 命令 | RED | GREEN | 日志 |
| --- | --- | --- | --- | --- |
| UI-W1 | `npx vitest run src/panels/DesignPanel.test.tsx` | 退出1，1失败/3通过，缺少设计评审工作区摘要 | 退出0，4通过 | review-red.txt / review-green.txt |
| UI-W2 | `npx vitest run src/panels/SamplesPanel.test.tsx` | 退出1，2失败/9通过，原界面重复参数表且无统一输入表 | 退出0，11通过 | samples-red.txt / samples-green.txt |
| UI-W3 | `npx vitest run src/panels/ConsistencyPanel.test.tsx` | 退出1，2失败/8通过，列表仍有详细证据且关闭项缺入口 | 退出0，10通过 | conflicts-red.txt / conflicts-green.txt |

单项浏览器命令依次执行并退出0：

- `npx playwright test --config playwright.cockpit.config.ts reduced-details.spec.ts`：1通过，review-browser.txt。检查摘要、完整预览依赖、对象定位、桌面/手机及关闭焦点。
- `npx playwright test --config playwright.cockpit.config.ts details.spec.ts -g "sample comparison"`：1通过，samples-browser.txt。真实上传、参数输入、保存及确认，前后仅一张参数表，登记来源可展开。
- `npx playwright test --config playwright.cockpit.config.ts details.spec.ts -g "conflict drawer"`：1通过，conflicts-browser.txt。真实处置，关闭后完整记录只读回看，无二次处置表单，取消/焦点/手机。

重构复核保留已有业务断言，修改定位以匹配新入口。冲突单测过程中出现一次全局文本匹配到列表和抽屉的歧义，改为在对应行内断言；未删去版本/状态检查。随后最终10项通过。补充真实事件类型的中文流转标签后，再构建并执行完整浏览器复查。

## 最终回归

| 命令 | 结果 | 日志 |
| --- | --- | --- |
| `npm run test:coverage` | 退出0，112通过/22文件 | frontend-full.txt |
| `npm run lint` | 退出0，零警告 | lint.txt |
| `npm run build` | 退出0，TypeScript与Vite构建成功 | build.txt |
| `npx playwright test --config playwright.cockpit.config.ts` | 最终退出0，17通过 | cockpit.txt |
| `npx playwright test --config playwright.review.config.ts` | 退出0，1通过 | walkthrough.txt |
| `npx playwright test --config playwright.r2.config.ts workspace.spec.ts` | 退出0，5通过 | workspace.txt |

共23个不同浏览器检查，不叠加专项、重跑或日常冒烟；未执行整个R2套件。覆盖原详情/计算结果、审核与版本、备份恢复/API失败、材料待办、九模块和响应式布局。桌面/手机截图已目视核对，见review-summary-desktop.png、review-detail-mobile.png、sample-comparison-desktop.png、sample-comparison-mobile.png、closed-conflict-desktop.png等。

TS覆盖：语句85.72%（1681/1961）、分支69.26%（1246/1799）、函数86.40%（553/640）、行89.86%（1419/1579）。排除维持main.tsx（启动装配）、src/test/**（测试支持）、测试文件本身，无新增排除。此为前端覆盖，不代表Python核心领域覆盖；本轮后端未改，未重跑pytest或重新采集Python覆盖率。

### 首次失败与复查

首次完整cockpit为16通过/1失败，桌面需求可读性检查未读到需求行，页面提示Failed to fetch。原始文本保留cockpit-initial.txt。当时检查到同一需求GET出现200与-1记录，根因未确定；不能据此断定为热更新或业务代码错误。相关需求业务代码本轮未修改。未删除断言、加重试或放宽超时，完整重跑17项通过。原Playwright临时trace由重跑覆盖，未另行留存，不宣称保留该trace。此为一次未复现的读取失败，后续若再次出现须继续定位，不当作已证明长期运行无故障。

## 日常只读核验与范围

根目录执行 `node docs/test-evidence/2026-10-22/UI-W/live-check.cjs`，退出0。日常5181查看现有样件单表及一致性列表，关闭焦点正确，无写请求/页面异常，见live-check.json及截图。设计页挂载会自动计算相似项目并产生审计，因此日常只读检查没有打开该页；设计交互在隔离测试库验证。未对日常数据生成、确认、处置、恢复或删除。

原data/demo.db SHA-256仍为 `edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0`。该哈希只证明原始库未变；日常工作副本的无写结论以只读脚本记录为准。

README、使用指南、老师说明、验收复核、任务、开发日志与决策同步。沿用根目录Start-Demo.cmd启动，已运行的5181刷新即可。UI-REVIEW-01的解析、试验两项仍为建议，本轮没有实施；本轮不签全部P0/AC，不将受控交互测试等同于当前材料全部可提交或生产级混沌验证。
