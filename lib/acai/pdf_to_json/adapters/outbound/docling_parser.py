"""Concrete PDF parser adapter based on Docling (IBM)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from acai.pdf_to_json.domain.exceptions import PdfParseError
from acai.pdf_to_json.domain.pdf_config import PdfParserConfig
from acai.pdf_to_json.domain.pdf_models import (
    ContentType,
    ParsedPdfDocument,
    PdfImage,
    PdfMetadata,
    PdfPage,
    PdfPageElement,
    PdfTable,
    PdfTextBlock,
)
from acai.pdf_to_json.ports.pdf_parser_port import PdfParserPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


class DoclingParser(PdfParserPort):
    """PDF parser using IBM *Docling* (``DocumentConverter``).

    Docling provides advanced layout analysis, table-structure recognition
    and picture classification powered by deep-learning models.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``PdfParserPort``.
    """

    VERSION: str = "1.0.0"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        config: PdfParserConfig | None = None,
    ) -> None:
        self._logger = logger
        self._config = config or PdfParserConfig()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    def parse_file(self, pdf_path: Union[str, Path]) -> ParsedPdfDocument:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise PdfParseError(f"PDF file not found: {pdf_path}")

        self._logger.info(
            "Starting Docling PDF parsing from file",
            source_name=pdf_path.name,
            parser="docling",
            extract_tables=self._config.extract_tables,
            extract_images=self._config.extract_images,
        )

        try:
            converter = self._create_converter()
            result = converter.convert(str(pdf_path))
            parsed = self._convert_result(result, source_name=pdf_path.name)
            self._logger.info(
                "Docling PDF parsing completed",
                source_name=pdf_path.name,
                parser="docling",
                page_count=len(parsed.pages),
            )
            return parsed
        except PdfParseError:
            raise
        except Exception as exc:
            self._logger.error(
                "Docling PDF parsing failed",
                source_name=pdf_path.name,
                parser="docling",
                error=str(exc),
            )
            raise PdfParseError(f"Failed to parse '{pdf_path.name}': {exc}") from exc

    def parse_bytes(
        self, data: bytes, *, source_name: str = "<bytes>"
    ) -> ParsedPdfDocument:
        if not data:
            raise PdfParseError("Cannot parse empty PDF data")

        self._logger.info(
            "Starting Docling PDF parsing from bytes",
            source_name=source_name,
            parser="docling",
            byte_count=len(data),
            extract_tables=self._config.extract_tables,
            extract_images=self._config.extract_images,
        )

        try:
            from docling.datamodel.base_models import DocumentStream
        except ImportError as exc:
            raise PdfParseError(
                "docling is required for this adapter. "
                "Install with: pip install docling"
            ) from exc

        try:
            stream = DocumentStream(name=source_name, stream=io.BytesIO(data))
            converter = self._create_converter()
            result = converter.convert(stream)
            parsed = self._convert_result(result, source_name=source_name)
            self._logger.info(
                "Docling PDF parsing completed",
                source_name=source_name,
                parser="docling",
                page_count=len(parsed.pages),
            )
            return parsed
        except PdfParseError:
            raise
        except Exception as exc:
            self._logger.error(
                "Docling PDF parsing failed",
                source_name=source_name,
                parser="docling",
                error=str(exc),
            )
            raise PdfParseError(f"Failed to parse '{source_name}': {exc}") from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_converter(self) -> Any:
        """Lazy-import and build a ``DocumentConverter``."""
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise PdfParseError(
                "docling is required for this adapter. "
                "Install with: pip install docling"
            ) from exc

        # Disable OCR to avoid extra OCR model downloads in restricted environments.
        pdf_options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=self._config.extract_tables,
            generate_picture_images=self._config.extract_images,
        )
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            }
        )

    def _convert_result(
        self,
        result: Any,
        source_name: str,
    ) -> ParsedPdfDocument:
        """Map a Docling ``ConversionResult`` to our domain model."""
        doc = result.document  # DoclingDocument

        metadata = self._extract_metadata(doc, source_name)
        pages = self._build_pages(doc, source_name)
        return ParsedPdfDocument(metadata=metadata, pages=pages)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, doc: Any, source_name: str) -> PdfMetadata:
        try:
            page_count = (
                doc.num_pages() if callable(getattr(doc, "num_pages", None)) else 0
            )
            title: Optional[str] = None
            # Try to get title from the first heading
            for item in getattr(doc, "texts", []):
                label = getattr(item, "label", "")
                if label and "heading" in str(label).lower():
                    title = getattr(item, "text", None)
                    break
            return PdfMetadata(title=title, page_count=page_count)
        except Exception as exc:
            self._logger.warning(
                "Docling metadata extraction failed",
                source_name=source_name,
                parser="docling",
                error=str(exc),
            )
            return PdfMetadata()

    # ------------------------------------------------------------------
    # Page building
    # ------------------------------------------------------------------

    def _build_pages(self, doc: Any, source_name: str) -> List[PdfPage]:
        """Walk Docling items, bucket them by page, return ``PdfPage`` list."""
        page_elements: Dict[int, List[PdfPageElement]] = {}

        # --- text items ---
        for item in getattr(doc, "texts", []):
            text = getattr(item, "text", "")
            if not text:
                continue
            prov_list = getattr(item, "prov", [])
            page_no = self._page_from_prov(prov_list)
            page_elements.setdefault(page_no, []).append(
                PdfPageElement(
                    type=ContentType.TEXT,
                    text_block=PdfTextBlock(content=text),
                )
            )

        # --- tables ---
        if self._config.extract_tables:
            for tbl_item in getattr(doc, "tables", []):
                rows = self._table_item_to_rows(tbl_item)
                if rows:
                    prov_list = getattr(tbl_item, "prov", [])
                    page_no = self._page_from_prov(prov_list)
                    page_elements.setdefault(page_no, []).append(
                        PdfPageElement(
                            type=ContentType.TABLE,
                            table=PdfTable(rows=rows),
                        )
                    )

        # --- pictures ---
        if self._config.extract_images:
            for pic_item in getattr(doc, "pictures", []):
                prov_list = getattr(pic_item, "prov", [])
                page_no = self._page_from_prov(prov_list)
                img = self._picture_item_to_image(pic_item)
                page_elements.setdefault(page_no, []).append(
                    PdfPageElement(type=ContentType.IMAGE, image=img)
                )

        # Build pages sorted by number
        if not page_elements:
            self._logger.warning(
                "No content extracted from PDF",
                source_name=source_name,
                parser="docling",
            )
            return []

        pages: List[PdfPage] = []
        for page_no in sorted(page_elements):
            pages.append(PdfPage(page_number=page_no, elements=page_elements[page_no]))

        self._logger.info(
            "Docling page extraction completed",
            source_name=source_name,
            parser="docling",
            page_count=len(pages),
        )
        return pages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _page_from_prov(prov_list: Any) -> int:
        """Extract 1-based page number from a Docling provenance list."""
        if prov_list:
            first = prov_list[0] if isinstance(prov_list, list) else prov_list
            return getattr(first, "page_no", 1) or 1
        return 1

    @staticmethod
    def _table_item_to_rows(tbl_item: Any) -> List[List[str]]:
        """Convert a Docling ``TableItem`` to a list-of-lists."""
        data = getattr(tbl_item, "data", None)
        if data is None:
            return []
        # data.grid is a list of lists of TableCell
        grid = getattr(data, "grid", None)
        if grid is None:
            return []
        rows: List[List[str]] = []
        for row in grid:
            rows.append([getattr(cell, "text", "") for cell in row])
        return rows

    @staticmethod
    def _picture_item_to_image(pic_item: Any) -> PdfImage:
        """Convert a Docling ``PictureItem`` to our ``PdfImage``."""
        image_data = b""
        width = 0
        height = 0
        img_obj = getattr(pic_item, "image", None)
        if img_obj is not None:
            pil_img = getattr(img_obj, "pil_image", None)
            if pil_img is not None:
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                image_data = buf.getvalue()
                width, height = pil_img.size
        return PdfImage(data=image_data, width=width, height=height, format="png")
