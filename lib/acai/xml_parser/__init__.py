"""
acai.xml_parser — Hexagonal XML parsing module
===============================================

Public surface
--------------
- ``XmlParserPort``         — port contract (depend on this)
- ``XmlParserConfig``       — shared configuration value object
- ``ParsedArticle``, ``LawMetadata``, ``ParsedLawDocument`` — domain models
- ``XmlParserError``, ``XmlParseError``, ``ConfigurationError`` — exceptions
- ``create_xml_parser()``   — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.xml_parser.adapters.LxmlParser``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.xml_parser.domain import (
    ConfigurationError,
    LawMetadata,
    ParsedArticle,
    ParsedLawDocument,
    XmlParseError,
    XmlParserConfig,
    XmlParserError,
)
from acai.xml_parser.ports import XmlParserPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_xml_parser(
    logger: Loggable,
    config: XmlParserConfig | None = None,
) -> XmlParserPort:
    """Factory that builds a ready-to-use ``XmlParserPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter for operational logging.
    config:
        Optional configuration.  Defaults target Swiss AKN documents.
    """
    from acai.xml_parser.adapters.outbound.lxml_parser import LxmlParser

    if config is None:
        config = XmlParserConfig()
    return LxmlParser(logger=logger, config=config)


__all__ = [
    "XmlParserPort",
    "XmlParserConfig",
    "ParsedArticle",
    "LawMetadata",
    "ParsedLawDocument",
    "XmlParserError",
    "XmlParseError",
    "ConfigurationError",
    "create_xml_parser",
]
