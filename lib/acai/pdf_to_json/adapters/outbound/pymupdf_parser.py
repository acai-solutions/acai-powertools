"""Concrete PDF parser adapter based on PyMuPDF (fitz) with pdfplumber for tables."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

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
    import fitz
    from acai.logging.ports import Loggable


class PyMuPdfParser(PdfParserPort):
    """PDF parser implemented with *PyMuPDF* (``fitz``) for text/images
    and *pdfplumber* for table extraction.

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
            "Starting PyMuPDF parsing from file",
            source_name=pdf_path.name,
            parser="pymupdf",
            extract_tables=self._config.extract_tables,
            extract_images=self._config.extract_images,
        )
        try:
            data = pdf_path.read_bytes()
        except Exception as exc:
            self._logger.error(
                "Failed to read PDF file",
                source_name=pdf_path.name,
                parser="pymupdf",
                error=str(exc),
            )
            raise PdfParseError(f"Failed to read {pdf_path.name}: {exc}") from exc

        return self.parse_bytes(data, source_name=pdf_path.name)

    def parse_bytes(
        self, data: bytes, *, source_name: str = "<bytes>"
    ) -> ParsedPdfDocument:
        if not data:
            raise PdfParseError("Cannot parse empty PDF data")

        self._logger.info(
            "Starting PyMuPDF parsing from bytes",
            source_name=source_name,
            parser="pymupdf",
            byte_count=len(data),
            extract_tables=self._config.extract_tables,
            extract_images=self._config.extract_images,
        )

        try:
            import fitz  # PyMuPDF
        except ImportError:
            try:
                # PyMuPDF 1.27+ may expose the module as `pymupdf` only.
                import pymupdf as fitz
            except ImportError as exc:
                raise PdfParseError(
                    "PyMuPDF is required for PDF parsing. Install it with: "
                    "pip install pymupdf"
                ) from exc

        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            self._logger.error(
                "Failed to open PDF",
                source_name=source_name,
                parser="pymupdf",
                error=str(exc),
            )
            raise PdfParseError(f"Failed to open PDF '{source_name}': {exc}") from exc

        try:
            metadata = self._extract_metadata(doc, source_name)
            pages = self._extract_pages(doc, data, source_name)
            parsed = ParsedPdfDocument(metadata=metadata, pages=pages)
            self._logger.info(
                "PyMuPDF parsing completed",
                source_name=source_name,
                parser="pymupdf",
                page_count=len(parsed.pages),
            )
            return parsed
        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, doc: "fitz.Document", source_name: str) -> PdfMetadata:
        try:
            info = doc.metadata or {}
            meta = PdfMetadata(
                title=info.get("title") or None,
                author=info.get("author") or None,
                subject=info.get("subject") or None,
                creator=info.get("creator") or None,
                producer=info.get("producer") or None,
                page_count=len(doc),
            )
            self._logger.debug(
                "Extracted PDF metadata",
                source_name=source_name,
                parser="pymupdf",
                page_count=meta.page_count,
            )
            return meta
        except Exception as exc:
            self._logger.warning(
                "Metadata extraction failed",
                source_name=source_name,
                parser="pymupdf",
                error=str(exc),
            )
            return PdfMetadata(page_count=len(doc))

    # ------------------------------------------------------------------
    # Page-level extraction
    # ------------------------------------------------------------------

    def _extract_pages(
        self,
        doc: "fitz.Document",
        raw_data: bytes,
        source_name: str,
    ) -> List[PdfPage]:
        table_pages = self._extract_tables_all_pages(raw_data, source_name)
        pages: List[PdfPage] = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            elements: List[PdfPageElement] = []

            # --- text blocks ---
            text_blocks = self._extract_text_blocks(page, page_num, source_name)
            elements.extend(text_blocks)

            # --- images ---
            if self._config.extract_images:
                images = self._extract_images(doc, page, page_num, source_name)
                elements.extend(images)

            # --- tables ---
            if self._config.extract_tables and page_idx in table_pages:
                for tbl in table_pages[page_idx]:
                    elements.append(PdfPageElement(type=ContentType.TABLE, table=tbl))

            rect = page.rect
            pages.append(
                PdfPage(
                    page_number=page_num,
                    width=rect.width,
                    height=rect.height,
                    elements=elements,
                )
            )

        self._logger.info(
            "Page extraction completed",
            source_name=source_name,
            parser="pymupdf",
            page_count=len(pages),
        )
        return pages

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text_blocks(
        self,
        page: "fitz.Page",
        page_num: int,
        source_name: str,
    ) -> List[PdfPageElement]:
        elements: List[PdfPageElement] = []
        try:
            blocks = page.get_text("dict", flags=0)["blocks"]
            for block in blocks:
                if block.get("type") != 0:  # 0 = text
                    continue
                lines_text: List[str] = []
                font_name = None
                font_size = None
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            lines_text.append(text)
                            if font_name is None:
                                font_name = span.get("font")
                                font_size = span.get("size")
                if lines_text:
                    elements.append(
                        PdfPageElement(
                            type=ContentType.TEXT,
                            text_block=PdfTextBlock(
                                content=" ".join(lines_text),
                                font_name=font_name,
                                font_size=round(font_size, 1) if font_size else None,
                            ),
                        )
                    )
        except Exception as exc:
            self._logger.warning(
                "Text extraction failed",
                source_name=source_name,
                parser="pymupdf",
                page_number=page_num,
                error=str(exc),
            )
        return elements

    # ------------------------------------------------------------------
    # Image extraction
    # ------------------------------------------------------------------

    def _merge_tiled_image_rects(
        self,
        rects: List["fitz.Rect"],
    ) -> List["fitz.Rect"]:
        """Merge thin, vertically tiled image strips into larger rectangles.

        Some PDFs place a single visual image as many 1px rows. This helper
        groups near-contiguous strips that are horizontally aligned so they can
        be rendered as one image instance.
        """
        try:
            import fitz
        except ImportError:
            import pymupdf as fitz

        if not rects:
            return []

        tol_y_gap = 1.5
        min_overlap_ratio = 0.5

        ordered = sorted(rects, key=lambda r: (r.y0, r.x0))
        merged: List[fitz.Rect] = []
        cur = fitz.Rect(ordered[0])
        segment_count = 1

        for rect in ordered[1:]:
            y_gap = rect.y0 - cur.y1
            overlap = max(0.0, min(cur.x1, rect.x1) - max(cur.x0, rect.x0))
            min_width = min(cur.width, rect.width)
            overlap_ratio = (overlap / min_width) if min_width > 0 else 0.0

            if y_gap <= tol_y_gap and overlap_ratio >= min_overlap_ratio:
                cur = fitz.Rect(
                    min(cur.x0, rect.x0),
                    min(cur.y0, rect.y0),
                    max(cur.x1, rect.x1),
                    max(cur.y1, rect.y1),
                )
                segment_count += 1
                continue

            if segment_count >= 5:
                merged.append(cur)
            cur = fitz.Rect(rect)
            segment_count = 1

        if segment_count >= 5:
            merged.append(cur)

        return merged

    def _extract_images(
        self,
        doc: "fitz.Document",
        page: "fitz.Page",
        page_num: int,
        source_name: str,
    ) -> List[PdfPageElement]:
        try:
            import fitz
        except ImportError:
            import pymupdf as fitz

        elements: List[PdfPageElement] = []
        image_format = (self._config.image_format or "png").lower()
        if image_format == "jpg":
            image_format = "jpeg"

        try:
            candidates = self._collect_image_candidates(page, fitz)
            elements = self._render_image_candidates(
                candidates, page, fitz, image_format, source_name, page_num
            )
        except Exception:
            elements = self._extract_images_fallback(
                doc, page, image_format, source_name, page_num
            )
        return elements

    def _collect_image_candidates(
        self,
        page: "fitz.Page",
        fitz,
    ) -> List[tuple[int, "fitz.Rect"]]:
        """Collect candidate images from the page, filtering by size."""
        try:
            import fitz as fitz_module
        except ImportError:
            import pymupdf as fitz_module

        by_xref, xrefless = self._group_images_by_xref(page, fitz_module)
        candidates: List[tuple[int, "fitz.Rect"]] = []
        rejected_small: List["fitz.Rect"] = []

        for xref, rects in by_xref.items():
            c, r = self._process_xref_images(xref, rects)
            candidates.extend(c)
            rejected_small.extend(r)

        c, r = self._process_xrefless_images(xrefless)
        candidates.extend(c)
        rejected_small.extend(r)

        if not candidates and rejected_small:
            candidates.extend(self._recover_from_rejected(rejected_small))

        return candidates

    def _group_images_by_xref(
        self,
        page: "fitz.Page",
        fitz,
    ) -> tuple[dict[int, List["fitz.Rect"]], List["fitz.Rect"]]:
        """Group images by xref and separate xrefless images."""
        by_xref: dict[int, List["fitz.Rect"]] = {}
        xrefless: List["fitz.Rect"] = []

        for info in page.get_image_info(xrefs=True):
            bbox = info.get("bbox")
            if not bbox:
                continue
            rect = fitz.Rect(bbox)
            xref = int(info.get("xref", 0))
            if xref > 0:
                by_xref.setdefault(xref, []).append(rect)
            else:
                xrefless.append(rect)

        return by_xref, xrefless

    def _process_xref_images(
        self,
        xref: int,
        rects: List["fitz.Rect"],
    ) -> tuple[List[tuple[int, "fitz.Rect"]], List["fitz.Rect"]]:
        """Process images with xrefs, filtering by size."""
        min_width = self._config.image_instance_min_width
        min_height = self._config.image_instance_min_height
        min_area = self._config.image_instance_min_area

        qualifying = [
            r
            for r in rects
            if r.width >= min_width
            and r.height >= min_height
            and (r.width * r.height) >= min_area
        ]
        if qualifying:
            return [(xref, rect) for rect in qualifying], []

        merged_rects = self._merge_tiled_image_rects(rects)
        candidates = [
            (xref, rect)
            for rect in merged_rects
            if rect.width >= min_width
            and rect.height >= min_height
            and rect.width * rect.height >= min_area
        ]
        return candidates, rects

    def _process_xrefless_images(
        self,
        xrefless: List["fitz.Rect"],
    ) -> tuple[List[tuple[int, "fitz.Rect"]], List["fitz.Rect"]]:
        """Process images without xrefs, filtering by size."""
        min_width = self._config.image_instance_min_width
        min_height = self._config.image_instance_min_height
        min_area = self._config.image_instance_min_area
        candidates: List[tuple[int, "fitz.Rect"]] = []
        rejected: List["fitz.Rect"] = []

        for rect in xrefless:
            if (
                rect.width >= min_width
                and rect.height >= min_height
                and rect.width * rect.height >= min_area
            ):
                candidates.append((0, rect))
            else:
                rejected.append(rect)

        return candidates, rejected

    def _recover_from_rejected(
        self,
        rejected_small: List["fitz.Rect"],
    ) -> List[tuple[int, "fitz.Rect"]]:
        """Attempt to recover images by merging rejected small rectangles."""
        min_width = self._config.image_instance_min_width
        min_height = self._config.image_instance_min_height
        min_area = self._config.image_instance_min_area
        candidates: List[tuple[int, "fitz.Rect"]] = []

        for rect in self._merge_tiled_image_rects(rejected_small):
            if (
                rect.width >= min_width
                and rect.height >= min_height
                and rect.width * rect.height >= min_area
            ):
                candidates.append((0, rect))

        return candidates

    def _render_image_candidates(
        self,
        candidates: List[tuple[int, "fitz.Rect"]],
        page: "fitz.Page",
        fitz,
        image_format: str,
        source_name: str,
        page_num: int,
    ) -> List[PdfPageElement]:
        """Render image candidates and return PdfPageElement list."""
        render_scale = self._config.image_render_scale
        elements: List[PdfPageElement] = []
        seen: set[tuple] = set()

        for xref, rect in candidates:
            key = (
                xref,
                round(rect.x0, 1),
                round(rect.y0, 1),
                round(rect.x1, 1),
                round(rect.y1, 1),
            )
            if key in seen:
                continue
            seen.add(key)

            pix = page.get_pixmap(
                clip=rect,
                matrix=fitz.Matrix(render_scale, render_scale),
                alpha=False,
            )
            elements.append(
                PdfPageElement(
                    type=ContentType.IMAGE,
                    image=PdfImage(
                        data=pix.tobytes(image_format),
                        width=pix.width,
                        height=pix.height,
                        format=image_format,
                    ),
                )
            )
        return elements

    def _extract_images_fallback(
        self,
        doc: "fitz.Document",
        page: "fitz.Page",
        image_format: str,
        source_name: str,
        page_num: int,
    ) -> List[PdfPageElement]:
        """Fallback image extraction for older PyMuPDF variants."""
        elements: List[PdfPageElement] = []
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        elements.append(
                            PdfPageElement(
                                type=ContentType.IMAGE,
                                image=PdfImage(
                                    data=base_image["image"],
                                    width=base_image.get("width", 0),
                                    height=base_image.get("height", 0),
                                    format=base_image.get("ext", "png"),
                                ),
                            )
                        )
                except Exception as exc:
                    self._logger.debug(
                        "Skipping image xref",
                        source_name=source_name,
                        parser="pymupdf",
                        page_number=page_num,
                        xref=xref,
                        error=str(exc),
                    )
        except Exception as exc:
            self._logger.warning(
                "Image extraction failed",
                source_name=source_name,
                parser="pymupdf",
                page_number=page_num,
                error=str(exc),
            )
        return elements

    # ------------------------------------------------------------------
    # Table extraction (pdfplumber)
    # ------------------------------------------------------------------

    def _extract_tables_all_pages(
        self,
        raw_data: bytes,
        source_name: str,
    ) -> dict[int, List[PdfTable]]:
        """Return a dict mapping 0-based page index → list of PdfTable."""
        if not self._config.extract_tables:
            return {}

        try:
            import pdfplumber
        except ImportError:
            self._logger.warning(
                "pdfplumber is not installed; table extraction disabled",
                source_name=source_name,
                parser="pymupdf",
            )
            return {}

        result: dict[int, List[PdfTable]] = {}
        try:
            with pdfplumber.open(io.BytesIO(raw_data)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_tables = self._extract_tables_from_page(page)
                    if page_tables:
                        result[page_idx] = page_tables
        except Exception as exc:
            self._logger.warning(
                "Table extraction failed",
                source_name=source_name,
                parser="pymupdf",
                error=str(exc),
            )
        return result

    def _extract_tables_from_page(self, page) -> List[PdfTable]:
        """Extract tables from a single page."""
        tables = page.extract_tables(
            table_settings={
                "vertical_strategy": self._config.table_strategy,
                "horizontal_strategy": self._config.table_strategy,
            }
        )
        if not tables:
            return []

        page_tables: List[PdfTable] = []
        for raw_table in tables:
            rows = [[(cell or "") for cell in row] for row in raw_table if row]
            if rows:
                page_tables.append(PdfTable(rows=rows))
        return page_tables
