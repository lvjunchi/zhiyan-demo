# UI-N 总览与模块视觉完善

2026-10-21；关联 AC-20，在 START-01/UI-M 完成后实施。保留单项目总览、紧凑密度和侧栏结构，不新增未经测量的指标。

## 变更

新增 finish.css 作为明确的产品视觉层：深蓝产品区配青色机械光效、技术网格与矢量示意细节，卡片边框/层次、指标色条、状态和表单统一。中文优先使用本机 Microsoft YaHei UI / Microsoft YaHei，正文和模块表格沿用 14px，概览标题、指标、辅助信息分级调整，降低浅色小字占比；版本/时间仍便于辨识。

GearboxIllustration 保持代码原生 SVG，明确为结构示意，非工程模型；没有外部图片、字体、模型或遥测。原来的实际参数、当前版本、审核/待复核、旧材料提示和三智能体/两引擎数据均由既有后端返回。

## 验证

- 纯视觉/文字不虚构业务 RED。先以现有严格布局检查验证初稿，再调整本机中文字体后运行完整回归。
- `npx playwright test --config playwright.cockpit.config.ts`：退出 0，**8 passed**，见 [cockpit.txt](cockpit.txt)。1920×1080、1440×900、1366×768 三桌面同屏，关键卡片及内部内容无裁切；1280×720 导航、390px 手机可达；无外网请求。未用隐藏数据或降低断言换通过。
- `npx playwright test --config playwright.r2.config.ts`：退出 0，**7 passed**，见 [workspace.txt](workspace.txt)。业务依据、当前状态、变更定位、只读预览、键盘与响应式均验证。
- 最终 `npm run build` 退出 0：[build-complete.txt](build-complete.txt)；最终前端 83 项、lint 零警告见 [MAINT-01](../MAINT-01/REPORT.md)。
- 真实日常 5181 以 Edge 只读检查，无 pageerror、无外网请求/溢出：[live-check.json](live-check.json)。已使用持久化日常工作副本，不是重新播种的数据。

预览：[1920 日常总览](live-dashboard-1920.png)、[1440 日常总览](live-dashboard-1440.png)、[1366 隔离布局检查](dashboard-1366.png)、[手机](dashboard-mobile.png)。

指定视口/100% 缩放通过不等于所有设备或完整 WCAG 审计。较短窗口或放大允许滚动以保持文字可读。运行方式：根目录 Start-Demo.cmd；当前日常地址 http://127.0.0.1:5181/。
