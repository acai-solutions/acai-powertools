from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class XmlParserConfig:
    """Configuration value object for XML parser adapters."""

    akn_namespace_uri: str = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
    xml_namespace_uri: str = "http://www.w3.org/XML/1998/namespace"
    language: str = "de"

    def __post_init__(self) -> None:
        if not self.akn_namespace_uri:
            raise ConfigurationError("akn_namespace_uri must not be empty")
