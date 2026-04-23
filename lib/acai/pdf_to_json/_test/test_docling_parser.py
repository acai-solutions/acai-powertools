"""Tests for ``acai.pdf_to_json`` — DoclingParser adapter.

Unit tests mock the heavy ``docling`` dependency so they run fast.
Integration tests (marked ``@pytest.mark.integration``) use real fixture PDFs
and require ``docling`` to be installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from acai.pdf_to_json import (
    ContentType,
    ParsedPdfDocument,
    PdfParseError,
    PdfParserConfig,
    create_pdf_parser,
)
from acai.pdf_to_json.adapters.outbound.docling_parser import DoclingParser
from acai.pdf_to_json.ports.pdf_parser_port import PdfParserPort

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ── Fake Docling objects for mocking ──────────────────────────────────────────


@dataclass
class _FakeProv:
    page_no: int = 1


@dataclass
class _FakeTextItem:
    text: str = ""
    label: str = "paragraph"
    prov: List[_FakeProv] = field(default_factory=list)


@dataclass
class _FakeTableCell:
    text: str = ""


@dataclass
class _FakeTableGrid:
    grid: List[List[_FakeTableCell]] = field(default_factory=list)


@dataclass
class _FakeTableItem:
    data: Optional[_FakeTableGrid] = None
    prov: List[_FakeProv] = field(default_factory=list)


@dataclass
class _FakePictureItem:
    image: Any = None
    prov: List[_FakeProv] = field(default_factory=list)


@dataclass
class _FakeDoclingDocument:
    texts: List[_FakeTextItem] = field(default_factory=list)
    tables: List[_FakeTableItem] = field(default_factory=list)
    pictures: List[_FakePictureItem] = field(default_factory=list)

    def num_pages(self) -> int:
        pages = set()
        for item in self.texts + self.tables + self.pictures:
            for p in getattr(item, "prov", []):
                pages.add(p.page_no)
        return len(pages) or 1


@dataclass
class _FakeConversionResult:
    document: _FakeDoclingDocument = field(default_factory=_FakeDoclingDocument)


def _make_fake_result(
    texts: list[tuple[str, int]] | None = None,
    tables: list[tuple[list[list[str]], int]] | None = None,
    pictures_count: int = 0,
) -> _FakeConversionResult:
    """Build a ``_FakeConversionResult`` for mocking.

    Parameters
    ----------
    texts:
        List of (text, page_no) tuples.
    tables:
        List of (rows, page_no) tuples where rows is list-of-list-of-str.
    pictures_count:
        Number of stub pictures to add (page 1).
    """
    doc = _FakeDoclingDocument()

    if texts:
        for txt, page_no in texts:
            doc.texts.append(
                _FakeTextItem(
                    text=txt,
                    label="paragraph",
                    prov=[_FakeProv(page_no=page_no)],
                )
            )
    if tables:
        for rows, page_no in tables:
            grid = _FakeTableGrid(
                grid=[[_FakeTableCell(text=cell) for cell in row] for row in rows]
            )
            doc.tables.append(
                _FakeTableItem(data=grid, prov=[_FakeProv(page_no=page_no)])
            )
    if pictures_count:
        for _ in range(pictures_count):
            doc.pictures.append(_FakePictureItem(prov=[_FakeProv(page_no=1)]))

    return _FakeConversionResult(document=doc)


# ── Port contract ─────────────────────────────────────────────────────────────


class TestPortContract:
    def test_parser_implements_port(self, logger):
        parser = DoclingParser(logger=logger)
        assert isinstance(parser, PdfParserPort)  # nosec B101

    def test_context_manager(self, logger):
        parser = DoclingParser(logger=logger)
        with parser as p:
            assert p is parser  # nosec B101


# ── parse_bytes (mocked) ─────────────────────────────────────────────────────


class TestParseBytesUnit:
    def test_empty_data_raises(self, logger):
        parser = DoclingParser(logger=logger)
        with pytest.raises(PdfParseError, match="empty"):
            parser.parse_bytes(b"")

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_parses_single_page(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            texts=[("Hello from Docling", 1), ("Second paragraph", 1)]
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(b"%PDF-fake", source_name="test.pdf")

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert len(result.pages) == 1  # nosec B101
        text_elements = [
            e for e in result.pages[0].elements if e.type == ContentType.TEXT
        ]
        assert len(text_elements) == 2  # nosec B101
        assert "Hello" in text_elements[0].text_block.content  # nosec B101

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_parses_multipage(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            texts=[
                ("Page one text", 1),
                ("Page two text", 2),
                ("Page three text", 3),
            ]
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(b"%PDF-fake")

        assert len(result.pages) == 3  # nosec B101
        assert result.pages[0].page_number == 1  # nosec B101
        assert result.pages[2].page_number == 3  # nosec B101

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_extracts_tables(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            tables=[
                ([["Name", "Age"], ["Alice", "30"], ["Bob", "25"]], 1),
            ]
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(b"%PDF-fake")

        table_elements = [
            e for e in result.pages[0].elements if e.type == ContentType.TABLE
        ]
        assert len(table_elements) == 1  # nosec B101
        assert table_elements[0].table.rows[0] == ["Name", "Age"]  # nosec B101
        assert len(table_elements[0].table.rows) == 3  # nosec B101

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_no_tables_when_disabled(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            tables=[([["A", "B"], ["1", "2"]], 1)],
            texts=[("Some text", 1)],
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        cfg = PdfParserConfig(extract_tables=False)
        parser = DoclingParser(logger=logger, config=cfg)
        result = parser.parse_bytes(b"%PDF-fake")

        table_elements = [
            e for p in result.pages for e in p.elements if e.type == ContentType.TABLE
        ]
        assert len(table_elements) == 0  # nosec B101

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_no_images_when_disabled(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            texts=[("Text", 1)],
            pictures_count=2,
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        cfg = PdfParserConfig(extract_images=False)
        parser = DoclingParser(logger=logger, config=cfg)
        result = parser.parse_bytes(b"%PDF-fake")

        image_elements = [
            e for p in result.pages for e in p.elements if e.type == ContentType.IMAGE
        ]
        assert len(image_elements) == 0  # nosec B101

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_metadata_extraction(self, mock_converter_factory, logger):
        fake = _make_fake_result(texts=[("My Document Title", 1), ("Body text", 1)])
        # Make the first text item look like a heading
        fake.document.texts[0].label = "section_heading"
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(b"%PDF-fake")

        assert result.metadata.title == "My Document Title"  # nosec B101


# ── parse_file (mocked) ──────────────────────────────────────────────────────


class TestParseFileUnit:
    def test_file_not_found_raises(self, logger, work_dir):
        parser = DoclingParser(logger=logger)
        with pytest.raises(PdfParseError, match="not found"):
            parser.parse_file(work_dir / "missing.pdf")

    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_parses_existing_file(self, mock_converter_factory, logger):
        fake = _make_fake_result(texts=[("Hello", 1)])
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        path = FIXTURES / "sample_text.pdf"
        parser = DoclingParser(logger=logger)
        result = parser.parse_file(path)

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        mock_converter.convert.assert_called_once_with(str(path))


# ── to_dict serialisation ────────────────────────────────────────────────────


class TestToDict:
    @patch(
        "acai.pdf_to_json.adapters.outbound.docling_parser.DoclingParser._create_converter"
    )
    def test_round_trips_to_dict(self, mock_converter_factory, logger):
        fake = _make_fake_result(
            texts=[("First", 1), ("Second", 2)],
            tables=[([["A", "B"], ["1", "2"]], 2)],
        )
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake
        mock_converter_factory.return_value = mock_converter

        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(b"%PDF-fake")
        d = result.to_dict()

        assert "metadata" in d  # nosec B101
        assert "pages" in d  # nosec B101
        assert len(d["pages"]) == 2  # nosec B101
        # Page 2 should have a table element
        page2_types = [e["type"] for e in d["pages"][1]["elements"]]
        assert "table" in page2_types  # nosec B101


# ── factory ───────────────────────────────────────────────────────────────────


class TestFactory:
    def test_creates_docling_parser(self, logger):
        parser = create_pdf_parser(logger, use_docling=True)
        assert isinstance(parser, PdfParserPort)  # nosec B101
        assert isinstance(parser, DoclingParser)  # nosec B101

    def test_creates_docling_parser_with_config(self, logger):
        cfg = PdfParserConfig(extract_images=False)
        parser = create_pdf_parser(logger, config=cfg, use_docling=True)
        assert isinstance(parser, DoclingParser)  # nosec B101


# ── Integration tests (require docling installed) ─────────────────────────────


def _docling_available() -> bool:
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _docling_available(), reason="docling not installed")
class TestDoclingIntegration:
    """These tests actually run Docling against the fixture PDFs.

    They are skipped when ``docling`` is not installed.
    """

    def test_sample_text_pdf(self, logger):
        path = FIXTURES / "sample_text.pdf"
        parser = DoclingParser(logger=logger)
        result = parser.parse_file(path)

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert len(result.pages) >= 1  # nosec B101
        all_text = " ".join(
            e.text_block.content
            for p in result.pages
            for e in p.elements
            if e.type == ContentType.TEXT and e.text_block
        )
        assert len(all_text) > 0  # nosec B101

    def test_sample_multipage_pdf(self, logger):
        path = FIXTURES / "sample_multipage.pdf"
        parser = DoclingParser(logger=logger)
        result = parser.parse_file(path)

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert result.metadata.page_count >= 1  # nosec B101

    def test_sample_table_pdf(self, logger):
        path = FIXTURES / "sample_table.pdf"
        parser = DoclingParser(logger=logger)
        result = parser.parse_file(path)

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        total_elements = sum(len(p.elements) for p in result.pages)
        assert total_elements > 0  # nosec B101

    def test_parse_bytes(self, logger):
        path = FIXTURES / "sample_text.pdf"
        data = path.read_bytes()
        parser = DoclingParser(logger=logger)
        result = parser.parse_bytes(data, source_name="sample_text.pdf")

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert len(result.pages) >= 1  # nosec B101

    def test_to_dict(self, logger):
        path = FIXTURES / "sample_text.pdf"
        parser = DoclingParser(logger=logger)
        result = parser.parse_file(path)
        d = result.to_dict()

        assert "metadata" in d  # nosec B101
        assert "pages" in d  # nosec B101
        assert len(d["pages"]) >= 1  # nosec B101
