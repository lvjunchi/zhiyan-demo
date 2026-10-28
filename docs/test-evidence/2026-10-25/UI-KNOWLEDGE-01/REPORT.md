# UI-KNOWLEDGE-01 知识库数量层次

关联本轮截图、AC-20/21展示范围。原数量使用18px（矮屏16px）粗体等宽数字，中文单位也随之放大，抢过库名称。改为12px、500字重、继承界面字体的小号浅蓝标签；数字与单位紧凑连接，文字颜色柔和。图标尺寸、名称层次、库数量来源和导航不变；未知仍为—，检测规则仍显示原三类关键词。

## RED → GREEN / 回归

在既有首页浏览器测试增加前三个资源数量的次级字号、字重、自然宽度及无裁切约定。frontend执行 `npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts -g 'complete project dashboard'`，退出1：实际18px大于13px，见red.txt。

修改后执行 `npx playwright test --config playwright.cockpit.config.ts homepage.spec.ts package-boundary.spec.ts`，3项通过、退出0，见green.txt。保留图标至少28px、标题至少12px、桌面同屏、模块导航及材料卡片46组布局回归。

`npm test -- src/panels/OverviewPanel.test.tsx` 34项通过、退出0，见component.txt。包括空白介绍、已导入、未知和实际统计及既有追溯/材料/预警交互。初始介绍使用独立资源区，不改其文字或布局。`npm run lint`、`npm run build` 退出0，102模块构建成功。

仅局部样式和数量文案间距调整，无额外结构重构，无后端/前端全量/覆盖重跑和新增排除。首次rg搜索使用Windows不接受的路径通配符，随即按具体文件重查；该工具输入问题不作为产品测试结果。

## 实际页面

`node docs/test-evidence/2026-10-25/UI-KNOWLEDGE-01/live-check.cjs` 退出0。实际5181六尺寸只读复核及截图目视，当前数量为4款/5个/1份，标签12px、500字重、自然宽度约33px，无裁切；矮屏图标与名称仍可读。写请求0、页面异常0，8027业务备份SHA前后相同，见live-browser.json。未重启、清空或修改用户业务数据。
