# UI-PART-ART-02 联网参考后再细化零件示意

2026-10-25；关联用户本轮“联网看看类似零件，再优化一轮”、会议18、AC-20。

## 参考来源与范围

- [Eaton 16速同步变速器维修手册](https://www.eaton.com/content/dam/eaton/products/transmissions/vehicle-transmissions/service-manuals/eaton-16-speed-synchromesh-transmission-service-manual-en-gb.pdf)：公开厂商资料，输入轴、齿轮、轴承及壳体分项。web可读正文与部件清单；截图端请求403，不把失败截图说成已目检原图。
- [法士特公开壳体结构专利 CN218236040U](https://patents.google.com/patent/CN218236040U/zh)：参考多轴壳体、加强筋、结合面及安装连接的结构主题；只作类别外观示意，不套用其具体尺寸/性能或声称获得制造设计。
- [Eaton 变速器子总成页](https://www.eaton.com/us/en-us/catalog/transmissions/transmission-subassemblies.html)：初次正文可读，后续请求403；作为补充分类背景。图片检索结果用于辅助外形检索，不下载或打包第三方照片。部分供应商/聚合站搜索结果未作为工程参数来源。

用户明确授权本轮联网查询公开资料。没有外传项目原件或数据、调用收费接口、引入在线图片/字体依赖。运行时仍使用本地原生SVG，合成标识保留。

## 改动

- 齿轮以较厚的斜齿侧面、钢质轮缘、环形车削纹、中心花键孔表现；去掉原有装饰性减重孔，钢件更深、机加工面更亮。
- 输入轴改纵向花键、轴承台阶、退刀/卡环槽、端部齿段和导向端；这些是概念示意，无齿数/制造公差或型号专有结构承诺。
- 主箱壳体改多孔前端面、铸造筋、侧盖、顶盖及结合面，区分铸件与机加工边缘。离合器壳补安装耳，法兰安装孔不再画成已装螺钉；取力器接口突出六孔安装面及孔口，执行机构区分电连接器。
- 轻微固定种子的铸造颗粒、钢件/铸件分色，仍保留白底、统一光照和柔和接触影。无业务数据、匹配、审核、版本、门槛、基础库修改，无新依赖。

## 验证与证据

- `npm test -- src/panels/PartChoicesPanel.test.tsx src/panels/BasesPanel.test.tsx`：2文件10项通过、退出0。
- `npx playwright test --config playwright.overview.config.ts review-usability.spec.ts`：独立库1浏览器闭环通过、退出0；保留上游阻塞、驳回、空意见确认、自动关闭、绿色样式、间距和390px不溢出断言。八类图库、审核弹窗及窄屏PNG已目检。截图隐藏吸顶栏仅为防遮挡，不改实际页面。
- `npm run lint`、`npm run build`通过；103模块、主JS523.07kB，Vite默认500kB体积提醒保留。终端NO_COLOR提醒不影响测试。
- 日常服务仅只读确认前端模块已更新，无业务写入、清空、恢复或后端重启。

本轮只改可逆的展示，没有新增领域行为，不补造RED；复用现有交互回归并目检。没有执行全量后端/全量前端覆盖或其他浏览器组，不把历史全量结果计为本轮验证。
