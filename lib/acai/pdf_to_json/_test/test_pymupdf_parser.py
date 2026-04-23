"""Tests for ``acai.pdf_to_json`` — PyMuPdfParser adapter.

Uses both in-memory PDFs and shipped fixture files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from acai.pdf_to_json import (
    ConfigurationError,
    ContentType,
    ParsedPdfDocument,
    PdfParseError,
    PdfParserConfig,
    create_pdf_parser,
)
from acai.pdf_to_json.adapters.outbound.pymupdf_parser import PyMuPdfParser
from acai.pdf_to_json.domain.pdf_models import PdfImage
from acai.pdf_to_json.ports.pdf_parser_port import PdfParserPort

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_simple_pdf() -> bytes:
    """Build a minimal single-page PDF with text using PyMuPDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Hello, world!", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _write_pdf(tmp_path: Path, data: bytes, name: str = "test.pdf") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / name
    path.write_bytes(data)
    return path


# ── PdfParserConfig validation ────────────────────────────────────────────────


class TestPdfParserConfig:
    def test_defaults(self):
        cfg = PdfParserConfig()
        assert cfg.extract_images is True  # nosec B101
        assert cfg.extract_tables is True  # nosec B101
        assert cfg.image_format == "png"  # nosec B101

    def test_invalid_image_format_raises(self):
        with pytest.raises(ConfigurationError, match="Unsupported image_format"):
            PdfParserConfig(image_format="bmp")

    def test_invalid_dpi_raises(self):
        with pytest.raises(ConfigurationError, match="image_dpi must be positive"):
            PdfParserConfig(image_dpi=0)

    def test_custom_config(self):
        cfg = PdfParserConfig(extract_images=False, image_dpi=300)
        assert cfg.extract_images is False  # nosec B101
        assert cfg.image_dpi == 300  # nosec B101

    def test_invalid_image_render_scale_raises(self):
        with pytest.raises(
            ConfigurationError, match="image_render_scale must be positive"
        ):
            PdfParserConfig(image_render_scale=0)

    def test_invalid_image_instance_thresholds_raise(self):
        with pytest.raises(
            ConfigurationError, match="image_instance_min_width must be non-negative"
        ):
            PdfParserConfig(image_instance_min_width=-1)

        with pytest.raises(
            ConfigurationError, match="image_instance_min_height must be non-negative"
        ):
            PdfParserConfig(image_instance_min_height=-1)

        with pytest.raises(
            ConfigurationError, match="image_instance_min_area must be non-negative"
        ):
            PdfParserConfig(image_instance_min_area=-1)


# ── Port contract ─────────────────────────────────────────────────────────────


class TestPortContract:
    def test_parser_implements_port(self, logger):
        parser = PyMuPdfParser(logger=logger)
        assert isinstance(parser, PdfParserPort)  # nosec B101

    def test_context_manager(self, logger):
        parser = PyMuPdfParser(logger=logger)
        with parser as p:
            assert p is parser  # nosec B101


# ── parse_bytes ───────────────────────────────────────────────────────────────


class TestParseBytes:
    def test_empty_data_raises(self, logger):
        parser = PyMuPdfParser(logger=logger)
        with pytest.raises(PdfParseError, match="empty"):
            parser.parse_bytes(b"")

    def test_invalid_pdf_raises(self, logger):
        parser = PyMuPdfParser(logger=logger)
        with pytest.raises(PdfParseError, match="Failed to open"):
            parser.parse_bytes(b"not-a-pdf")

    def test_simple_pdf_parses(self, logger):
        pdf_data = _make_simple_pdf()
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_bytes(pdf_data, source_name="test.pdf")

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert result.metadata.page_count == 1  # nosec B101
        assert len(result.pages) == 1  # nosec B101
        assert result.pages[0].page_number == 1  # nosec B101

    def test_text_blocks_extracted(self, logger):
        pdf_data = _make_simple_pdf()
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_bytes(pdf_data)

        text_elements = [
            e for e in result.pages[0].elements if e.type == ContentType.TEXT
        ]
        assert len(text_elements) >= 1  # nosec B101
        assert "Hello" in text_elements[0].text_block.content  # nosec B101


# ── parse_file with fixtures ─────────────────────────────────────────────────


class TestParseFile:
    def test_file_not_found_raises(self, logger, work_dir):
        parser = PyMuPdfParser(logger=logger)
        with pytest.raises(PdfParseError, match="not found"):
            parser.parse_file(work_dir / "missing.pdf")

    def test_parses_from_file(self, logger, work_dir):
        pdf_data = _make_simple_pdf()
        path = _write_pdf(work_dir, pdf_data)
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        assert isinstance(result, ParsedPdfDocument)  # nosec B101
        assert result.metadata.page_count == 1  # nosec B101

    def test_fixture_sample_text(self, logger):
        path = FIXTURES / "sample_text.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        assert result.metadata.page_count >= 1  # nosec B101
        all_text = " ".join(
            e.text_block.content
            for p in result.pages
            for e in p.elements
            if e.type == ContentType.TEXT and e.text_block
        )
        assert len(all_text) > 0  # nosec B101

    def test_fixture_multipage(self, logger):
        path = FIXTURES / "sample_multipage.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        assert result.metadata.page_count == 3  # nosec B101
        assert len(result.pages) == 3  # nosec B101
        assert result.pages[0].page_number == 1  # nosec B101
        assert result.pages[2].page_number == 3  # nosec B101

    def test_fixture_table_pdf(self, logger):
        path = FIXTURES / "sample_table.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        assert result.metadata.page_count >= 1  # nosec B101
        # The PDF should have at least some text elements
        total_elements = sum(len(p.elements) for p in result.pages)
        assert total_elements > 0  # nosec B101

    def test_fixture_multipage_page_dimensions(self, logger):
        path = FIXTURES / "sample_multipage.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        for page in result.pages:
            assert page.width > 0  # nosec B101
            assert page.height > 0  # nosec B101

    def test_no_images_when_disabled(self, logger):
        path = FIXTURES / "sample_multipage.pdf"
        cfg = PdfParserConfig(extract_images=False)
        parser = PyMuPdfParser(logger=logger, config=cfg)
        result = parser.parse_file(path)

        image_elements = [
            e for p in result.pages for e in p.elements if e.type == ContentType.IMAGE
        ]
        assert len(image_elements) == 0  # nosec B101

    def test_no_tables_when_disabled(self, logger):
        path = FIXTURES / "sample_table.pdf"
        cfg = PdfParserConfig(extract_tables=False)
        parser = PyMuPdfParser(logger=logger, config=cfg)
        result = parser.parse_file(path)

        table_elements = [
            e for p in result.pages for e in p.elements if e.type == ContentType.TABLE
        ]
        assert len(table_elements) == 0  # nosec B101

    def test_fixture_report_images_are_rendered_instances(self, logger):
        path = FIXTURES / "24030-03_06072004.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        image_elements = [
            e.image
            for p in result.pages
            for e in p.elements
            if e.type == ContentType.IMAGE and e.image
        ]
        assert len(image_elements) >= 1  # nosec B101
        assert all(img.width >= 3 for img in image_elements)  # nosec B101
        assert all(img.height >= 3 for img in image_elements)  # nosec B101

    def test_fixture_report_page_two_has_image(self, logger):
        path = FIXTURES / "24030-03_06072004.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)

        page_two = next((p for p in result.pages if p.page_number == 2), None)
        assert page_two is not None  # nosec B101

        page_two_images = [
            e.image
            for e in page_two.elements
            if e.type == ContentType.IMAGE and e.image
        ]

        assert len(page_two_images) >= 1  # nosec B101


# ── to_dict serialisation ────────────────────────────────────────────────────


class TestToDict:
    def test_round_trips_to_dict(self, logger):
        pdf_data = _make_simple_pdf()
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_bytes(pdf_data)
        d = result.to_dict()

        assert "metadata" in d  # nosec B101
        assert "pages" in d  # nosec B101
        assert d["metadata"]["page_count"] == 1  # nosec B101
        assert len(d["pages"]) == 1  # nosec B101
        assert d["pages"][0]["page_number"] == 1  # nosec B101

    def test_elements_serialise_type(self, logger):
        pdf_data = _make_simple_pdf()
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_bytes(pdf_data)
        d = result.to_dict()

        if d["pages"][0]["elements"]:
            elem = d["pages"][0]["elements"][0]
            assert elem["type"] in ("text", "image", "table")  # nosec B101

    def test_multipage_fixture_to_dict(self, logger):
        path = FIXTURES / "sample_multipage.pdf"
        parser = PyMuPdfParser(logger=logger)
        result = parser.parse_file(path)
        d = result.to_dict()

        assert d["metadata"]["page_count"] == 3  # nosec B101
        assert len(d["pages"]) == 3  # nosec B101
        for page_dict in d["pages"]:
            assert "page_number" in page_dict  # nosec B101
            assert "elements" in page_dict  # nosec B101


# ── PdfImage base64 ──────────────────────────────────────────────────────────


class TestPdfImage:
    def test_base64_encoding(self):
        img = PdfImage(data=b"\x89PNG", width=10, height=10, format="png")
        assert img.data_base64 == "iVBORw=="  # nosec B101

    def test_empty_data_base64(self):
        img = PdfImage()
        assert img.data_base64 == ""  # nosec B101


# ── factory ───────────────────────────────────────────────────────────────────


class TestFactory:
    def test_creates_default_parser(self, logger):
        parser = create_pdf_parser(logger)
        assert isinstance(parser, PdfParserPort)  # nosec B101
        assert isinstance(parser, PyMuPdfParser)  # nosec B101

    def test_creates_parser_with_config(self, logger):
        cfg = PdfParserConfig(extract_images=False)
        parser = create_pdf_parser(logger, config=cfg)
        assert isinstance(parser, PyMuPdfParser)  # nosec B101
