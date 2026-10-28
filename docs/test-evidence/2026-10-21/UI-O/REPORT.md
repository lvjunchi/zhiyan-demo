# UI-O 总览产品示意调整

日期：2026-10-21。关联：AC-20（视觉/响应式受控范围），不新增 O 产物或工程判定能力。

## 变更

- `GearboxIllustration.tsx` 重绘为统一轴测投影的工程线稿。删除原块面金属渐变、放射形前端、发光圆环/底座和英文装饰标签；区分近侧结构线与远侧辅助线，改为中文结构标注。
- `finish.css` 移除机械图光晕滤镜，调整说明间距；`ProjectShowcase.tsx` 明确“轴测示意，非工程模型”。真实需求数值、版本、审核、失效、材料包和导航均沿用原逻辑。
- 无生图、外部图片、资料上传、新依赖或参考文件修改。本地 SVG 是通用示意，不代表实际产品 CAD/工程尺寸。

## 验证

- 本轮是纯视觉替换，无新增业务行为，不人为制造 RED；不新增镜像实现的单元测试。
- `cd frontend; npm run build`：退出 0（含 TypeScript 检查）；证据 `build.txt`。
- `cd frontend; npm run lint`：退出 0；证据 `lint.txt`。
- `cd frontend; npx playwright test --config playwright.cockpit.config.ts --grep 'complete project dashboard'`：1 passed，退出 0；证据 `layout.txt`。使用独立预览服务/临时库，检查 1920×1080、1440×900、1366×768 同屏、内部无裁切、390×844 无横向溢出、导航与项目列表不变、无页面异常/外网请求。截图 `dashboard-*.png`。
- 首轮检查后细化远侧线条透明度与画面留白，再次 build/同一 Playwright 检查通过；两次运行不重复计算为两个测试。
- 日常 5181 页面另作只读三桌面检查；复现脚本 `capture.cjs`、结果 `live-check.json`、截图 `live-dashboard-*.png` 和 `product-preview.png`。未调用写入 API 或重置工作副本。
- 覆盖率：本轮未重新采集；此前 VERIFY-03 的覆盖数据仅作历史记录，不称本轮结果。未新增覆盖排除。未重跑全量后端/故障注入，因为未修改相关逻辑。

## 限制与启动

本轮仅处理总览插图；不宣称新增真实 CAD、数字孪生、仿真或完成所有 P0/AC。日常启动仍为根目录 `Start-Demo.cmd`，前端 `http://127.0.0.1:5181/`，刷新即可查看。
