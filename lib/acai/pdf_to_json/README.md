# acai.pdf_to_json

Hexagonal module that reads a PDF and produces a nested JSON structure
reflecting the document's content: **text blocks**, **images**, and **tables**.

## Architecture

```
Port (PdfParserPort)
  ├─ parse_file(path)   → ParsedPdfDocument   (reads from filesystem)
  └─ parse_bytes(data)  → ParsedPdfDocument   (accepts raw bytes)

Adapter
  └─ PyMuPdfParser  (PyMuPDF for text/images, pdfplumber for tables)

Domain models
  └─ ParsedPdfDocument
       ├─ PdfMetadata (title, author, page_count, …)
       └─ List[PdfPage]
            └─ List[PdfPageElement]
                 ├─ PdfTextBlock  (content, font_name, font_size)
                 ├─ PdfImage      (data bytes, width, height, format)
                 └─ PdfTable      (rows as list-of-lists)
```

## Quick start

```python
from acai.pdf_to_json import create_pdf_parser
from acai.logging import create_logger, LoggerConfig

logger = create_logger(LoggerConfig(service_name="demo"))
parser = create_pdf_parser(logger)

# From a file path
doc = parser.parse_file("report.pdf")

# From bytes (e.g. downloaded via API)
doc = parser.parse_bytes(raw_bytes, source_name="upload.pdf")

# Serialise to JSON-friendly dict
import json
print(json.dumps(doc.to_dict(), indent=2))
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `pymupdf` | Text & image extraction |
| `pdfplumber` | Table extraction (optional — gracefully skipped if missing) |

```bash
pip install pymupdf pdfplumber
```

## Configuration

```python
from acai.pdf_to_json import PdfParserConfig

cfg = PdfParserConfig(
    extract_images=True,       # default True
    extract_tables=True,       # default True
    image_format="png",        # png | jpeg | jpg
    image_dpi=150,             # resolution for rasterised images
    table_strategy="lines_strict",  # pdfplumber strategy
)
parser = create_pdf_parser(logger, config=cfg)
```
