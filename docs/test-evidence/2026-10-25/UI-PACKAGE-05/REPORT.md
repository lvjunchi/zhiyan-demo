# UI-PACKAGE-05 保留原框宽度，仅降低高度

关联用户明确截图、O13、AC-20/21。按最新澄清恢复整行浅蓝色圆角框、原“生成时快照”上标签与下方双指标，宽度与按钮及卡片内容一致；自然高度约50—52px，矮屏27px，不随卡片剩余高度拉伸。撤回前轮无框单行样式。辅助说明按可用行高180px决定是否显示，按钮保留底部留边。真实快照、状态及数量不变。

RED：先将既有测试的无框样式约定替换为用户明确要求的浅蓝框/1px边界，保留等宽对齐、高度≤60px、内部无裁切和按钮留边等约定。frontend执行 `npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts` 退出1，实际透明背景不符合浅蓝框，见red.txt。

GREEN：`npx playwright test --config playwright.cockpit.config.ts package-boundary.spec.ts homepage.spec.ts` 3项通过、退出0，见green.txt。23尺寸×2密度共46组布局检查，既有临界高度、桌面同屏、平板手机和业务模块回归均保留。没有放宽边界或裁切断言，无额外结构重构。

`npm run lint`、`npm run build` 退出0，102模块构建成功。本轮纯CSS，没有重跑后端/全量组件/覆盖率，无新增覆盖排除。

实际服务：`node docs/test-evidence/2026-10-25/UI-PACKAGE-05/live-check.cjs` 退出0，六尺寸复核并截图目视；1920×1001统计框320.66×49.80px，与按钮同宽且左右对齐。常规高度52px、矮屏27px，按钮底部留边9/15px。写请求0、页面异常0、8027业务SHA前后相同，详见live-browser.json。未重启、清空或生成材料包。
