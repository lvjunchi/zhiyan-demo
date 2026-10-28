# UI-J 页面标题业务化

- 关联：O1–O12 对应页面的展示名称；不改变业务契约、需求 ID、版本或数据。
- 变更：移除五个业务面板共十处标题的内部产物编号（包括 O5 最小集），同步三份既有浏览器测试的标题定位。
- RED：`npx --prefix frontend playwright test --config frontend/playwright.cockpit.config.ts business-titles.spec.ts`，退出码 1；精确业务标题“来源文档导入与规则解析”不可见，页面仍带编号。见 red.txt。
- GREEN：frontend 下 `npx playwright test --config playwright.cockpit.config.ts business-titles.spec.ts`，退出码 0，1 passed；只读遍历五个相关模块，断言业务标题可见且全部标题无括号内 O 编号。截图为当前实际页面。
- 回归：frontend 下 `npm test`，退出码 0，19 文件 / 64 测试通过；`npm run build` 退出码 0；`npm run lint` 退出码 0，仍有既有 10 条 effect 警告。
- REFACTOR：未另作结构重构；不重新计算覆盖率，本次仅标题文案与定位断言变化。
- 未执行：本轮不重复后端、全部业务 E2E 或混沌测试，不据此新增业务验收通过声明。只读浏览器检查不修改项目数据。
- 参考文件只读；O 编号继续用于开发计划及验收映射。
