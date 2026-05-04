"""Concrete XML parser adapter based on lxml for Akoma Ntoso (AKN) documents."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from acai.xml_parser.domain.exceptions import XmlParseError
from acai.xml_parser.domain.xml_config import XmlParserConfig
from acai.xml_parser.domain.xml_models import (
    LawMetadata,
    ParsedArticle,
    ParsedLawDocument,
)
from acai.xml_parser.ports.xml_parser_port import XmlParserPort
from lxml import etree

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


class LxmlParser(XmlParserPort):
    """AKN XML parser implemented with *lxml*.

    Handles namespace discovery, article extraction, heading collection
    and metadata enrichment for Swiss federal law documents.
    """

    VERSION: str = "1.0.7"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        config: XmlParserConfig | None = None,
    ) -> None:
        self._logger = logger
        self._config = config or XmlParserConfig()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    def parse(self, xml_path: Union[str, Path]) -> ParsedLawDocument:
        xml_path = Path(xml_path)
        try:
            root, nsmap = self._load_xml(xml_path)
        except Exception as e:
            raise XmlParseError(f"Failed to load XML {xml_path.name}: {e}") from e

        metadata = self._extract_metadata(root, nsmap, xml_path)
        articles = self._extract_articles(root, nsmap, xml_path)
        return ParsedLawDocument(metadata=metadata, articles=articles)

    # ------------------------------------------------------------------
    # XML loading & namespace resolution
    # ------------------------------------------------------------------

    def _load_xml(self, xml_path: Path) -> tuple[etree._Element, Dict[str, str]]:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(str(xml_path), parser)
        root = tree.getroot()

        akn_ns = self._config.akn_namespace_uri
        nsmap: Dict[str, str] = {"akn": akn_ns, "xml": self._config.xml_namespace_uri}

        for prefix, uri in root.nsmap.items():
            if prefix is None:
                nsmap["default"] = uri
                if uri == akn_ns:
                    nsmap["akn"] = uri
            else:
                nsmap[prefix] = uri
                if uri == akn_ns:
                    nsmap["akn"] = uri

        self._logger.debug(f"Loaded {xml_path.name} - namespaces: {nsmap}")
        return root, nsmap

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _extract_metadata(
        self,
        root: etree._Element,
        nsmap: Dict[str, str],
        xml_path: Path,
    ) -> LawMetadata:
        try:
            lang = self._config.language
            law_number = self._find_attr(root, "FRBRnumber", "value", nsmap)
            law_name = self._find_attr(
                root, f"FRBRname[@xml:lang='{lang}']", "value", nsmap
            )
            short_form = self._find_attr(
                root, f"FRBRname[@xml:lang='{lang}']", "shortForm", nsmap
            )
            return LawMetadata(
                law_number=law_number,
                law_name=law_name,
                short_form=short_form,
            )
        except Exception as e:
            self._logger.warning(f"Metadata extraction failed for {xml_path.name}: {e}")
            return LawMetadata()

    def _find_attr(
        self,
        root: etree._Element,
        tag: str,
        attr: str,
        nsmap: Dict[str, str],
    ) -> Optional[str]:
        for ns_prefix in ("akn", "default"):
            if ns_prefix not in nsmap:
                continue
            try:
                elem = root.find(f".//{ns_prefix}:{tag}", namespaces=nsmap)
                if elem is not None:
                    return elem.get(attr)
            except Exception:
                self._logger.debug(
                    f"Namespace {ns_prefix} lookup failed for {tag}", exc_info=True
                )
                continue
        return None

    # ------------------------------------------------------------------
    # Article extraction
    # ------------------------------------------------------------------

    def _extract_articles(
        self,
        root: etree._Element,
        nsmap: Dict[str, str],
        xml_path: Path,
    ) -> List[ParsedArticle]:
        try:
            article_elements = self._find_article_elements(root, nsmap)
            if not article_elements:
                self._logger.warning(f"No articles found in {xml_path.name}")
                return []

            self._logger.info(
                f"Processing {len(article_elements)} articles in {xml_path.name}"
            )

            processed_ids: Set[str] = set()
            results: List[ParsedArticle] = []

            for elem in article_elements:
                article_id = self._get_article_identifier(elem, nsmap)
                if article_id in processed_ids:
                    continue
                processed_ids.add(article_id)

                article_num = self._get_article_number(elem, nsmap)
                headings = self._get_headings_up_to_element(elem, nsmap)
                level = self._get_depth(elem)
                paragraphs = self._get_paragraphs(elem, nsmap)

                if article_num or paragraphs:
                    results.append(
                        ParsedArticle(
                            article=article_num,
                            headings=headings,
                            level=level,
                            paragraphs=paragraphs,
                        )
                    )

            return results
        except Exception as e:
            self._logger.error(f"Article extraction failed for {xml_path.name}: {e}")
            return []

    # ------------------------------------------------------------------
    # Element search strategies (body → direct → no-ns → preamble)
    # ------------------------------------------------------------------

    def _find_article_elements(
        self,
        root: etree._Element,
        nsmap: Dict[str, str],
    ) -> list[Any]:
        strategies = [
            self._find_articles_via_body,
            self._find_articles_direct,
            self._find_articles_no_namespace,
            self._find_articles_preamble,
        ]
        for strategy in strategies:
            result = strategy(root, nsmap)
            if result:
                return result
        return []

    def _find_articles_via_body(
        self, root: etree._Element, nsmap: Dict[str, str]
    ) -> list[Any]:
        for ns in ("akn", "default"):
            if ns not in nsmap:
                continue
            try:
                bodies = root.xpath(f".//{ns}:body", namespaces=nsmap)
                if bodies:
                    articles = bodies[0].xpath(f".//{ns}:article", namespaces=nsmap)
                    if articles:
                        self._logger.debug(
                            f"Found {len(articles)} articles via body ({ns})"
                        )
                        return articles
            except Exception:
                self._logger.debug(
                    f"Article search via body ({ns}) failed", exc_info=True
                )
                continue
        return []

    def _find_articles_direct(
        self, root: etree._Element, nsmap: Dict[str, str]
    ) -> list[Any]:
        for ns in ("akn", "default"):
            if ns not in nsmap:
                continue
            try:
                articles = root.xpath(f".//{ns}:article", namespaces=nsmap)
                if articles:
                    self._logger.debug(
                        f"Found {len(articles)} articles via direct search ({ns})"
                    )
                    return articles
            except Exception:
                self._logger.debug(
                    f"Direct article search ({ns}) failed", exc_info=True
                )
                continue
        return []

    def _find_articles_no_namespace(
        self, root: etree._Element, nsmap: Dict[str, str]
    ) -> list[Any]:
        try:
            articles = root.xpath("//article")
            if articles:
                self._logger.debug("Found articles without namespace")
                return articles
        except Exception:
            self._logger.debug("No-namespace article search failed", exc_info=True)
        return []

    def _find_articles_preamble(
        self, root: etree._Element, nsmap: Dict[str, str]
    ) -> list[Any]:
        for ns in ("akn", "default"):
            if ns not in nsmap:
                continue
            try:
                preambles = root.xpath(f".//{ns}:preamble", namespaces=nsmap)
                if not preambles:
                    continue
                preamble = preambles[0]
                articles = preamble.xpath(f".//{ns}:article", namespaces=nsmap)
                if articles:
                    self._logger.debug(
                        f"Found {len(articles)} articles in preamble ({ns})"
                    )
                    return articles
                content = self._text_content(preamble).strip()
                if content:
                    self._logger.debug("Treating preamble as single article")
                    return [preamble]
            except Exception:
                self._logger.debug(
                    f"Preamble article search ({ns}) failed", exc_info=True
                )
                continue
        return []

    def _get_article_identifier(
        self, elem: etree._Element, nsmap: Dict[str, str]
    ) -> str:
        article_id = elem.get("id") or elem.get("eId")
        if not article_id:
            num = self._get_article_number(elem, nsmap)
            content = self._text_content(elem)
            article_id = f"{num}_{hash(content)}"
        return article_id

    def _get_article_number(self, elem: etree._Element, nsmap: Dict[str, str]) -> str:
        for ns in ("akn", "default"):
            if ns not in nsmap:
                continue
            try:
                num_elem = elem.find(f"./{ns}:num", namespaces=nsmap)
                if num_elem is not None:
                    return self._text_content(num_elem).strip()
            except Exception:
                self._logger.debug(
                    f"Article number extraction ({ns}) failed", exc_info=True
                )
                continue
        return elem.get("id") or elem.get("eId") or ""

    def _get_paragraphs(self, elem: etree._Element, nsmap: Dict[str, str]) -> List[str]:
        paragraphs: List[str] = []
        seen: Set[str] = set()

        for ns in ("akn", "default"):
            if ns not in nsmap:
                continue
            for tag in ("paragraph", "p", "content"):
                try:
                    for child in elem.xpath(f".//{ns}:{tag}", namespaces=nsmap):
                        text = self._text_content(child).strip()
                        if text and text not in seen:
                            paragraphs.append(text)
                            seen.add(text)
                except Exception:
                    self._logger.debug(
                        f"Paragraph extraction ({ns}:{tag}) failed", exc_info=True
                    )
                    continue

        if not paragraphs:
            text = self._text_content(elem).strip()
            if text:
                paragraphs.append(text)

        return paragraphs

    def _get_headings_up_to_element(
        self, elem: etree._Element, nsmap: Dict[str, str]
    ) -> List[str]:
        headings: List[str] = []
        current: Optional[etree._Element] = elem
        while current is not None:
            heading_text = ""
            num_text = ""
            # Try 'default' namespace for headings (matches original behaviour)
            for ns in ("default", "akn"):
                if ns not in nsmap:
                    continue
                try:
                    h = current.find(f"./{ns}:heading", namespaces=nsmap)
                    if h is not None:
                        heading_text = self._text_content(h).strip()
                        n = current.find(f"./{ns}:num", namespaces=nsmap)
                        if n is not None:
                            num_text = self._text_content(n).strip()
                        break
                except Exception:
                    self._logger.debug(
                        f"Heading extraction ({ns}) failed", exc_info=True
                    )
                    continue
            if heading_text:
                full = (num_text + " " + heading_text).strip()
                headings.append(full)
            current = current.getparent()
        return headings[::-1]

    @staticmethod
    def _get_depth(elem: etree._Element) -> int:
        depth = 0
        parent = elem.getparent()
        while parent is not None:
            depth += 1
            parent = parent.getparent()
        return depth - 3

    @staticmethod
    def _text_content(elem: etree._Element) -> str:
        return " ".join(part.strip() for part in elem.itertext())
