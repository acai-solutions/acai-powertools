from dataclasses import dataclass, field

from .exceptions import ConfigurationError


@dataclass
class XmlParserConfig:
    """Configuration value object for XML parser adapters."""

    # Namespace URIs
    akn_namespace_uri: str = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
    xml_namespace_uri: str = "http://www.w3.org/XML/1998/namespace"
    language: str = "de"

    # Namespace resolution order — tried left to right for every lookup
    namespace_search_order: tuple[str, ...] = ("akn", "default")

    # Structural tag names
    article_tag: str = "article"
    body_tag: str = "body"
    preamble_tag: str = "preamble"
    paragraph_tags: tuple[str, ...] = ("paragraph", "p", "content")
    heading_tag: str = "heading"
    num_tag: str = "num"

    # Metadata element/attribute names
    law_number_element: str = "FRBRnumber"
    law_number_attr: str = "value"
    law_name_element: str = "FRBRname"
    law_name_attr: str = "value"
    short_form_attr: str = "shortForm"

    # Number of ancestor wrapper elements to subtract when computing nesting level
    depth_offset: int = 3

    def __post_init__(self) -> None:
        if not self.akn_namespace_uri:
            raise ConfigurationError("akn_namespace_uri must not be empty")
