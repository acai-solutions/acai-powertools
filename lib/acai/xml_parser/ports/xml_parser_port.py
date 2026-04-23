from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union

from acai.xml_parser.domain.xml_models import ParsedLawDocument


class XmlParserPort(ABC):
    """Outbound port defining the contract every XML parser adapter must fulfil."""

    VERSION: str = "1.0.0"  # inject_version

    @abstractmethod
    def parse(self, xml_path: Union[str, Path]) -> ParsedLawDocument:
        """Parse an XML file and return a structured law document.

        Parameters
        ----------
        xml_path:
            Path to the XML file to parse.

        Returns
        -------
        ParsedLawDocument
            Metadata and articles extracted from the document.

        Raises
        ------
        XmlParseError
            If the file cannot be parsed.
        """
        ...

    def __enter__(self) -> "XmlParserPort":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass
