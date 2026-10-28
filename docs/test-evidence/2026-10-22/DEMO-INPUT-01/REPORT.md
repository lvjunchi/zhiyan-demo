# DEMO-INPUT-01 Word演示协议

## 实际交付

- 演示导入文件/01_重型变速器技术协议_V1.docx，1页Letter，合成演示标识；正文4条完整沿用fixtures/protocol_v1.txt，保持2600 N·m、12档AMT、独立额定输入扭矩派生关系、取力器、重量上限及未明确耐久标准。非企业真实协议，原参考资料未改。
- 演示导入文件/使用说明.txt。README、DEMO_GUIDE、老师说明同步具体文件位置、导入与审核步骤。
- Word SHA-256：5bd022e55a1bcc6206c965558c3799598dbb979ddbac4aa8b4ae2d68af1bc51b。

## 验证与命令

1. 使用已安装Codex主运行时的python.exe和python-docx生成。工作区依赖加载工具本轮不可用，通过本地runtime.json确认运行时；没有安装或下载依赖。生成前运行文档技能mark_artifact_operation_started.mjs --operation-kind create --expected-output-count 1 --output-format docx，退出0。
2. 使用技能render_docx.py --output_dir ... --emit_pdf，实际退出1：Windows没有LibreOffice soffice.exe。原始日志render-canonical.txt保留，未宣称其通过。改用新建的隐藏Microsoft Word COM实例只读打开本轮文件，ExportAsFixedFormat PDF，关闭本次实例，不操作用户已打开文档；再用运行时Poppler pdftoppm生成PNG，退出0。首次图发现模板标题残留蓝色下划线，移除继承pBdr后重生成、重渲染，最终1页已目视检查，无边框残留/缺字/截断/溢出。最终图见render-word/page-1.png。PDF为验证中间物，只在证据目录保留。
3. `python docs/test-evidence/2026-10-22/DEMO-INPUT-01/verify_import.py`最终退出0。复制当前空工作库至临时目录，在真实FastAPI TestClient执行DOCX二进制预览→正文及原件归档→规则解析，13草稿/2问题，源扭矩与派生要求分开，重量<=300，来源/引用保留，下载原件字节相同，重复解析幂等，重开应用仍13条。校验最终Word重新执行，结果见import-result.json。
4. 日常库只读检查：来源和需求仍0，未代用户导入/确认/创建下游成果，保留其亲自开始演示。固定字段编号映射可留空走现有自动编号；不以自动编号样例冒称固定编号验收合同全测。

## 范围

关联O1与AC-02/03/04/07/19/20的受控样例验证。本轮为文档和演示输入补齐，未修改产品逻辑，无新产品行为的RED/GREEN或全量回归/覆盖率重跑。技能规范渲染工具缺组件的限制已记录，Word原生渲染作为本地替代；文档实际导入链验证通过。未验证用户未来的任意复杂协议，也未自动完成后续设计、试验或材料门禁。
