# UI-Z4 卡车矩形底色修复

用户反馈原图有明显蓝色矩形，与侧栏不融合。范围为AC-20装饰展示；无业务/API/数据库改动。

原因为不透明参考截图直接展示，lighten混合与遮罩没有消除截图底色。改用imagegen技能及内置image_gen编辑工具，生成参考风格的透明线稿，保存至frontend/src/assets/truck-linework.png；原图保留。新图有重绘，不宣称精确抠图。CSS取消lighten和遮罩，正常alpha叠加，透明边缘不再显示矩形色块。

## 最终提示词（内置工具，非CLI）

BACKGROUND REMOVAL / transparent line drawing. Extract ONLY the thin strokes of the truck from this reference. Make a simple flat technical truck wireframe, with uniform solid light steel-blue strokes. Absolutely NO fill in body panels or windows or gaps. Every area other than the actual thin strokes must have alpha ZERO: inside the truck outline, outside it, inside windows, between wheels. NO glow, NO blue fog or halo, NO gradient, NO shadow, NO colored silhouette, NO dark background, NO white background, NO grid. Preserve original three-quarter truck geometry. Thin clean strokes only, isolated on fully transparent canvas, the kind of line-art overlay that can sit seamlessly on any page background. Entire truck visible with wide fully transparent margin around every edge. Uniform stroke color #5689AD.

参数transparent_background=true，参考为原truck-reference.png。首轮输出带明显光晕，未用于项目；第二轮选用上述提示词输出。实际alpha：61.48%像素完全透明，alpha>32像素14.66%，边框最大alpha=1/255。边框测试允许这一档舍入误差，未放宽透明比例及非填充断言。实际侧栏截图目视检查无矩形底色。

## 测试证据

- RED：`npx playwright test --config playwright.cockpit.config.ts platform-shell.spec.ts -g 'truck decoration'`退出1，1失败；原图完全透明比例=0，因缺失透明背景失败。见red.txt、red-trace.zip。
- 增加可见笔画比例上限20%避免填色轮廓冒充线稿；旧179宽像素身份断言改为图片真实加载非零，因用户已授权透明素材替换。透明比例>50%、非空笔画、边框alpha<=1共同检查素材性质。
- GREEN：`npx playwright test --config playwright.cockpit.config.ts platform-shell.spec.ts homepage.spec.ts`退出0，6项通过（green.txt），涵盖透明背景、桌面一屏、侧栏尺寸、键盘导航及手机适配。浏览器使用独立临时库，端口8074/5224，图像green/单独归档。
- `npm run lint`及`npm run build`均退出0（lint.txt、build.txt）。没有独立重构步骤，因此不虚构REFACTOR重跑。2026-10-23仅核对既存证据并补齐文档，未将旧测试记录当作当天重跑。
- `node docs/test-evidence/2026-10-22/UI-Z4/live-check.cjs`退出0，11模块只读，writes/errors/external为空，13需求/1来源保留，前后备份hash均707a983dc73077c88324d3fd67574fe276da29aadfc0510b2afa2173745dcaef。

未修改领域逻辑；未重跑全量141单测、后端pytest或完整P0验收，不宣称全系统重新验收。覆盖率未重测，既有排除无变化。刷新5181可见，启动方式不变。
