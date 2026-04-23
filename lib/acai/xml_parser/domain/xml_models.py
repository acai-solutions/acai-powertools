from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedArticle:
    """A single article extracted from an AKN XML document."""

    article: str = ""
    headings: List[str] = field(default_factory=list)
    level: int = 0
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class LawMetadata:
    """Metadata extracted from the FRBRWork section of an AKN document."""

    law_number: Optional[str] = None
    law_name: Optional[str] = None
    short_form: Optional[str] = None


@dataclass
class ParsedLawDocument:
    """Complete result of parsing an AKN XML law document."""

    metadata: LawMetadata
    articles: List[ParsedArticle]
