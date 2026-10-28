# UI-SET-03 清空按钮靠近说明

用户指出清空按钮过度靠右。关联AC-20受控布局；纯CSS调整，没有改变清空、备份、确认或恢复逻辑。

将project-clear-overview改为纵向排列，按钮置于三条保留说明下方，左边缘对齐，间距14px；移除说明区域flex:1。保留白卡/红色图标、按钮，以及手机端整行按钮。

RED：增强既有settings-style浏览器检查，增加1920宽度，要求按钮左边缘与说明对齐（≤1px）、位于说明下方8—20px。修改前同命令退出1（red.txt），原横排远端按钮未满足左对齐要求。

GREEN：`npx playwright test --config playwright.cockpit.config.ts e2e-cockpit/settings-style.spec.ts`退出0，1项通过，包含1920/1440/390设置布局及四种桌面导航高度。保留原有红色图标、确认禁用、取消后焦点返回、无横向溢出、前后整库SHA相等断言；隔离库没有被清空。green.txt及browser截图保留，1920图已目视检查。

`npm run lint`、`npm run build`均退出0。无新增领域行为/额外重构，未重复全量单元测试、后端或覆盖率，不借用此前测试计数。日常业务与初始展示数据未修改。
