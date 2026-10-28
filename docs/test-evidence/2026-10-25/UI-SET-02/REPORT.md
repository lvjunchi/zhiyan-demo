# UI-SET-02 重新开始项目的统一卡片样式

2026-10-25；设置页可用性与AC-18/20/21受控交互。用户要求解释两引擎，并让重新开始项目与其他设置板块一致、标志使用红色。

引擎1是一致性检测，依据当前需求、工程决策、试验、样件及引用版本检查参数/版本/证据冲突；引擎2是协同风险，依据沟通记录及参与方计划/实际/交付版本计算风险。编号用于区分两项贯穿能力，不是不同系统实例。本轮未改引擎判定或标题名称。

## 实现

ProjectClearPanel使用与显示/运行状态相同的settings-section-heading及36px图标容器；白色卡片、正常标题色/字阶、统一分隔线，说明与操作区分开。仅警告图标/图标底色及清空按钮使用红色提示。删除旧粉色整卡、褐色标题和手机隐藏图标的覆盖样式，去掉旧按钮58px补偿缩进。所有预览、版本哈希、备份、项目编号确认、错误重试及成功处理逻辑保持原样。

## RED → GREEN与检查

- RED：增强既有浏览器settings-style.spec.ts的视觉约定，检查卡片底色/标题字阶与运行状态一致、桌面与手机红色图标可见，仍验证取消不清空、编号未填禁用、焦点返回、页面无横向溢出及前后完整备份SHA相等。`npx playwright test --config playwright.cockpit.config.ts e2e-cockpit/settings-style.spec.ts`退出1，预期白色rgb(255,255,255)，实际旧粉色rgb(255,248,248)。见red.txt；失败源自缺失的样式行为。
- GREEN：相同命令退出0，1项通过，包含1440和390设置页及四种桌面导航高度；见green.txt。截图browser/settings-refined-1440.png和390.png已分别目视检查。
- `npx vitest run src/panels/Stage03.test.tsx src/panels/SettingsPanel.test.tsx`退出0，2文件8项通过，覆盖清空取消/失败重新预览/成功备份和设置保存。见components.txt。
- `npm run lint`与`npm run build`均退出0；见lint.txt、build.txt。

无新增领域行为和后端修改，未重复全量331/180/39或核心覆盖；不将本次8+1计为完整回归。不做额外REFACTOR，无伪造重跑。浏览器服务使用独立库，SHA前后相等；没有清空用户日常数据。
