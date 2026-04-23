class PdfParserError(Exception):
    """Base exception for all PDF-to-JSON operations."""


class PdfParseError(PdfParserError):
    """Parsing a PDF document failed."""


class ConfigurationError(PdfParserError):
    """PDF parser configuration is invalid."""
