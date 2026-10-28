from io import BytesIO
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.domain.parser import parse_protocol


def _extract(client, filename, content):
    return client.post('/api/document-text', params={'filename': filename}, content=content, headers={'Content-Type': 'application/octet-stream'})


def _pdf(text=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 30 300 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    data = BytesIO(); writer.write(data)
    return data.getvalue()


def test_extracts_utf8_txt_pdf_and_docx_without_persisting_projects(client):
    txt = _extract(client, '协议.txt', '3.1 发动机最大扭矩 2800 N·m。'.encode())
    assert txt.status_code == 200, txt.text
    assert '【TXT 行 1】' in txt.json()['content']
    assert len(txt.json()['sha256']) == 64
    pdf = _extract(client, 'protocol.pdf', _pdf('engine torque 2800 Nm'))
    assert pdf.status_code == 200, pdf.text
    assert '【PDF 第 1 页】' in pdf.json()['content']
    assert 'engine torque 2800 Nm' in pdf.json()['content']
    archive = BytesIO()
    with ZipFile(archive, 'w') as zipped:
        zipped.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>发动机最大扭矩 2800 N·m。</w:t></w:r></w:p></w:body></w:document>')
    docx = _extract(client, '协议.docx', archive.getvalue())
    assert docx.status_code == 200, docx.text
    assert '【DOCX 段落 1】' in docx.json()['content']
    parsed = parse_protocol(docx.json()['content'])
    engine = next(r for r in parsed.requirements if r.key == 'engineMaxTorque')
    assert engine.source_location == 'DOCX 段落 1'
    parsed_pdf = parse_protocol('【PDF 第 2 页】\n3.1 发动机最大扭矩 2800 N·m。')
    assert parsed_pdf.requirements[0].source_location == 'PDF 第 2 页 · 3.1'
    assert client.get('/api/projects').json() == []


@pytest.mark.parametrize('filename,content,message', [
    ('scan.pdf', _pdf(), 'OCR'), ('broken.pdf', b'%PDF-broken', 'PDF'),
    ('bad.docx', b'not a zip', 'DOCX'), ('bad.txt', b'\xff\x00', 'UTF-8'),
    ('empty.txt', b'  ', '文本'), ('script.exe', b'abc', '格式'),
    ('large.txt', b'x' * (8 * 1024 * 1024 + 1), '8 MiB'),
], ids=['scan', 'broken-pdf', 'broken-docx', 'bad-encoding', 'empty', 'unsupported', 'oversize'])
def test_rejects_unsupported_or_invalid_files(client, filename, content, message):
    result = _extract(client, filename, content)
    assert result.status_code == 422, result.text
    assert message in result.json()['error']['message']
