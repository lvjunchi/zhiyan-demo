# UI-P 实物产品参考图与工程版本弹窗

日期：2026-10-21。关联 O3/O4、AC-07/18/19/20 的受控界面范围。

## 完成内容

- 用户否定 UI-O 线稿后，改用 FASTTE 官网真实 12JS 系列产品图片，删除线稿组件；原始 PNG 随 Vite 本地打包，不依赖运行时外网。SVG 仅作为原图显示视口裁去顶部透明留白，不是再次绘制机械图。图注保留“产品参考图”和来源入口，图像不表示合成基型或当前需求能力。
- 来源：https://fastte.by/zh-hans/node/141；原图：https://fastte.by/sites/default/files/services/12JS200TA.png。图片说明和原始哈希见 frontend/src/assets/SOURCES.md。本轮还比对了另一张集团官网 C12 图，未用于当前界面；参考原件未修改，未外传项目材料、调用生图或部署。
- 工程决策版本详情从列表下方改为原生模态 dialog。版本卡、引用、意见、确认/驳回和审计均在弹窗内。读取中即显示弹窗，失败可重试；关闭不提交，回到触发按钮和原滚动位置；保存中保留上下文。原后端 API、expected_revision、审核和失效规则不改。
- 桌面内容独立滚动，手机单列；背景不可操作，Tab 边界、Esc 与关闭按钮可用。请求序号隔离已关闭窗口的旧响应，项目切换按稳定 ID 隔离工作区。

## TDD 与验证记录

| 阶段 | 真实命令 / 结果 | 证据 |
| --- | --- | --- |
| RED | frontend 下 `npx vitest run src/components/EngineeringRecords.test.tsx`，退出 1；新增弹窗/关闭与错误重试两项因没有 dialog 失败，原两项通过 | red-dialog.txt |
| GREEN | 相同命令，退出 0，4 passed；中途关闭后焦点未返回，改为在点击事件捕获触发按钮后通过 | green-dialog.txt |
| 首轮全量 | `npm run test:coverage`，1 failed / 84 passed；旧图片名称断言仍指向结构示意。按当前真实产品参考图更新可访问名称断言，未删除断言 | frontend-first.txt |
| 浏览器补强 | 首轮 2 passed / 1 failed；原生 dialog 在 Shift+Tab 边界可进入浏览器 chrome，新增显式键盘边界循环 | browser-first.txt |
| 最终全量 | `npm run test:coverage`，退出 0；22 文件 / 85 tests passed | frontend-full.txt |
| 最终浏览器 | `npx playwright test --config playwright.cockpit.config.ts --grep 'complete project dashboard\|version review uses\|archives original bytes'`，退出 0，3 passed | browser.txt |
| REFACTOR | 图像视口去透明留白、截图使用实际视窗后，`--grep 'complete project dashboard\|version review uses'`，退出 0，2 passed；与上述重复检查不加总；前端全量再次 85 passed | browser-refactor.txt、frontend-full.txt |
| 构建/静态检查 | frontend 下 `npm run build`、`npm run lint`，均退出 0，lint 无警告 | build.txt、lint.txt |

浏览器使用独立端口 8049/5199、临时工作库，未连接日常库。三个不同检查覆盖：三桌面同屏/390 手机无横向溢出、原生 top-layer/Tab/Esc/原按钮与滚动恢复/手机弹窗边界、原件归档/版本审核实际持久化/返回材料门禁。旧工作流测试增加关闭弹窗步骤，保留原审核与材料断言。

jsdom 仅替身 showModal/close 的 open 属性，不宣称其能验证原生 top-layer；实际键盘与模态由 Edge 检查。检查截图为 version-dialog-desktop.png、version-dialog-mobile.png、engineering-history-review.png 等。

## 覆盖率、数据与限制

- TS：语句 82.86%（1499/1809）、分支 66.19%（1067/1612）、函数 84.12%、行 87.51%；通过既有 UI 门禁，未新增排除。排除仍仅 main.tsx（启动装配）、src/test/**（测试支持）、*.test.ts/tsx（测试本身）。前端没有独立领域层，不把 UI 分支当核心领域分支。
- 后端未修改，本轮未重跑后端全量或重新采集 Python 覆盖率；VERIFY-03 的领域分支 90.50% 是先前结果，不追认为本轮实测。未新增混沌/长期可靠性结论。
- 日常 5181 页面另以 `node docs/test-evidence/2026-10-21/UI-P/capture.cjs` 只读检查三桌面，无横纵溢出、异常或外网请求；live-check.json、product-preview.png、live-dashboard-*.png 可复查。未操作日常审核/业务数据。
- data/demo.db SHA-256 仍为 edc56dbc3db3ad6f227ca9bb3b3c974cfbb43954d32da89bf2643e995c48b5d0；本地图与原图哈希一致，见 hashes.json。
- 产品图片仅作外观参考，不新增 CAD、仿真或产品合格能力；不签署所有 P0/AC。本地启动仍双击 Start-Demo.cmd，http://127.0.0.1:5181/ 刷新可见。
