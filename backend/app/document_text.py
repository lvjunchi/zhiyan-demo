"""Offline text extraction for a human-reviewed source document preview."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import PurePath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .errors import DomainValidationError

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_UNPACKED_BYTES = 32 * 1024 * 1024


def extract_text(filename: str, data: bytes) -> dict[str, object]:
    if len(data) > MAX_FILE_BYTES:
        raise DomainValidationError('文档大小不得超过 8 MiB')
    suffix = PurePath(filename).suffix.lower()
    if suffix not in {'.txt', '.pdf', '.docx'}:
        raise DomainValidationError('不支持的文件格式，请选择 TXT、文本 PDF 或 DOCX')
    if not data:
        raise DomainValidationError('文件没有可读取的文本')
    blocks: list[str] = []
    warnings: list[str] = []
    if suffix == '.txt':
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise DomainValidationError('TXT 必须为 UTF-8 编码，请转换后重新选择') from exc
        if '\x00' in text:
            raise DomainValidationError('TXT 包含二进制内容，无法作为文本读取')
        blocks = [f'【TXT 行 {index}】\n{line}' for index, line in enumerate(text.splitlines(), 1) if line.strip()]
    elif suffix == '.pdf':
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise DomainValidationError('PDF 已加密，请先提供未加密的文本 PDF')
            if len(reader.pages) > 1000:
                raise DomainValidationError('PDF 页数超过 1000 页，请拆分文件')
            for index, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                if text.strip():
                    blocks.append(f'【PDF 第 {index} 页】\n{text}')
                else:
                    warnings.append(f'第 {index} 页未提取到文本，可能需要 OCR，不能视为已读取')
                if sum(map(len, blocks)) > MAX_TEXT_CHARS:
                    raise DomainValidationError('提取文本超过 200 万字符，请拆分文件')
        except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
            raise DomainValidationError('PDF 结构损坏或无法提取文本') from exc
    else:
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > MAX_UNPACKED_BYTES:
                    raise DomainValidationError('DOCX 解压内容超过 32 MiB，请缩小文件')
                root = ElementTree.fromstring(archive.read('word/document.xml'))
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for index, paragraph in enumerate(root.findall('.//w:p', ns), 1):
                    text = ''.join(node.text or '' for node in paragraph.findall('.//w:t', ns))
                    if text.strip():
                        blocks.append(f'【DOCX 段落 {index}】\n{text}')
        except (BadZipFile, KeyError, ElementTree.ParseError, OSError, RuntimeError) as exc:
            raise DomainValidationError('DOCX 结构损坏、已加密或不包含正文') from exc
    if not blocks:
        raise DomainValidationError('未提取到有效文本；扫描件/图片不支持 OCR，请提供文本文件')
    content = '\n'.join(blocks)
    if len(content) > MAX_TEXT_CHARS:
        raise DomainValidationError('提取文本超过 200 万字符，请拆分文件')
    return {'content': content, 'filename': filename, 'format': suffix[1:],
            'sha256': hashlib.sha256(data).hexdigest(), 'warnings': warnings, 'mode': 'rule'}
