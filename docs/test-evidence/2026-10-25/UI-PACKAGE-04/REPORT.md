# UI-PACKAGE-04 材料卡片视觉统一

关联用户本轮反馈、O13、AC-20/21。前轮将统计框单独缩窄，导致它与状态、按钮宽度不一致，视觉更零碎。本轮撤回局部窄框样式，去掉背景和外边框，改为简洁单行统计；与卡片内容和按钮左右对齐。保留真实快照语义、阻断/提示数量及颜色。在空间足够时显示下一步说明，实际行高≤175px时省略说明，按钮继续保留底部内边距。

## RED / GREEN / 重构

在 frontend 执行 `npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts`，RED退出1：统计区背景实际rgb(243,247,252)，不是透明色，见red.txt。

原“最大宽度280px”断言反映前轮已被用户否定的设计，本轮明确替换为无背景/无外框、统计与按钮两侧对齐、横向不溢出的约定；原按钮底部内边距、整卡和统计区无裁切、高度不拉伸等回归均保留，不放宽。

初次 `npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts homepage.spec.ts` 3项通过，见green.txt。细化下一步说明显示范围时，原1920×955回归真实发现底部距离7.703125px低于8.5px，退出1，见refactor.txt。调整说明显示门槛至175px，并增加其前/中/后三个尺寸。最终同命令结果见refactor-final.txt，覆盖23尺寸×2密度（46组）。

`npm run lint`、`npm run build` 最终退出0，102模块构建成功。仅修改局部CSS与浏览器布局约定，无后端/组件全量/覆盖率重跑，无新增覆盖排除。

## 日常服务

`node docs/test-evidence/2026-10-25/UI-PACKAGE-04/live-check.cjs` 退出0。实际5181六尺寸核对：统计区透明/无外框，与按钮左右边界一致，常规高44px、中等40px、矮屏27px；卡内无裁切，按钮留边9/15px。live-*.png已目视检查，写请求0、页面异常0，8027业务备份SHA前后一致，见live-browser.json。未清空、重启或生成材料包。
