class XmlParserError(Exception):
    """Base exception for all XML parser operations."""


class XmlParseError(XmlParserError):
    """Parsing an XML document failed."""


class ConfigurationError(XmlParserError):
    """XML parser configuration is invalid."""
