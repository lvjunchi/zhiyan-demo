# PRE-REHEARSAL-02 再次操作前复核

2026-10-25；关联用户本轮“再检查一遍”、AC-01/02/07—21。结论：本轮关键回归与完整受控排练通过；检查发现的旧运行后端已正常更新，未改用户当前演示数据。

## 发现及处理

1. 后端51680于14:32启动，晚于此时的审核代码修改未加载；健康018不能证明已载入这些修复。实际`part-candidates`响应中缺少`confirmation_blockers`，确认此问题存在。
2. 当前已恢复的初始场景正常：1文档、13需求均确认、10工程记录、5用例确认且固定集合覆盖/合成执行5/5；8零件中2个显式候选已确认、6个未显式选择；1个材料包仍为draft，这是场景的实际待办，不把草稿宣称为已提交。真实14个相关GET接口全部可读。
3. 先使用现有save_shutdown_backup完整保存快照，fsync并回读验证SQLite字节SHA，元数据见restart-backup.json。再向已核实属于本项目的启动器41572的控制台输入现有`stop`命令，程序执行自己的退出前备份与停服，留下data/local-preview/launcher-backups/stop-20261025T105725Z-5857888c.json；没有调用强制结束进程命令。
4. 确认原启动器及其前后端均退出、原端口释放后，以相同工作路径、端口及活动数据指针重新隐藏启动。新启动器10140，后端17428、前端53440；018健康正常，实际8个零件响应均提供新版blockers字段。
5. 重启前后及初次核对的SHA均为`a519de271e6561cf22761ff8543075ff3f96bf2933ecc9711039dfac3562a8cf`，用户刚恢复的初始展示保留。未清空/恢复/审核用户库。此前直接结束服务进程的操作曾被自动审批拒绝；本轮使用应用已有的备份后正常退出协议，解决运行更新限制。

## 实际验证

- `python -m pytest backend/tests/test_part_selection.py backend/tests/test_engineering_versions.py backend/tests/test_testing_edges.py backend/tests/test_test_plan_api.py backend/tests/test_backup_restore.py backend/tests/test_initial_showcase.py --no-cov -q --basetemp docs/test-evidence/2026-10-25/PRE-REHEARSAL-02/pytest-focused`：44通过，退出0，105.70秒；1条Starlette/httpx弃用提醒。此次未重跑全量后端或后端核心覆盖，引用历史全量时必须注明历史范围。
- `npm run test:coverage -- --maxWorkers=4`：31文件198通过，退出0；语句85.00%、分支73.36%、函数82.49%、行91.07%，沿用覆盖排除配置，门槛通过。
- `npx playwright test --config playwright.overview.config.ts`：9个不同用例通过，退出0。包含完整初始展示/恢复夹具、Word/PDF导入、跨模块及刷新核对草稿、批量审核/修订、零件及试验驳回和阻塞、清空备份及窄屏；端口8075/5225为独立测试服务。
- `python scripts/rehearse_demo.py --output-dir docs/test-evidence/2026-10-25/PRE-REHEARSAL-02/rehearsal`：退出0，status=passed。独立API主线：Word19条、80→60→80→100覆盖、旧执行保留、当前复核、human_approved材料快照、修改后冻结导出不变、备份清空、PDF19条且ID不复用。日志rehearsal.txt及rehearsal/rehearsal-report.json。
- `npm run lint`、`npm run build`：退出0。主JS523.07kB，仍有默认500kB体积提醒，未掩盖阈值。坏PDF用例的解析诊断、NO_COLOR及Starlette弃用提醒如实保留，不是未解释的测试失败。
- 新服务上实际11个菜单只读加载，页面错误0、API错误0、业务写请求0、1440px无页面横向溢出，见live-browser.json与live-overview.png。浏览器路由直接阻止所有非读取API，防止误触用户数据。
- 综合演示11个文件大小与SHA匹配；操作指南与当前运行状态说明同步。

本轮为检查与运行更新，无新增领域实现，不制造TDD RED；以现有回归和完整排练验证。没有把健康探针、截图或历史全量数量单独作为业务通过证明。顶部状态卡片压缩/底部下一步仍属于上一条建议，用户未要求实施，本轮不改其布局。

## 操作时需保留的边界

- 完整重演：备份→清空当前项目→导入综合协议；不清空直接导入会追加，重参数可阻止后续计算，不会自动替换旧成果。
- Word主要为DOCX，PDF为文本PDF；旧DOC、扫描件不当作已支持。
- 选型先审核依赖的变型点；新导入需求先审核/澄清；耐久缺标准不能确认。不同来源的样件、试验及协同数据仍需按指南独立登记。
- 覆盖固定5条，协议综合版19条；审核、覆盖、执行及通过分开统计，不把图表100%泛化为所有条款均已验证。
- 初始展示恢复使用data/initial-showcase/initial-backup.json整库快照；重新启动保留当前活动库，不会自动覆盖为初始展示。
