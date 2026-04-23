"""Tests for ``acai.xml_parser`` — LxmlParser adapter.

All tests use in-memory XML strings so no real files need to be shipped.
"""

import textwrap
from pathlib import Path

import pytest
from acai.xml_parser import (
    ConfigurationError,
    LawMetadata,
    ParsedArticle,
    ParsedLawDocument,
    XmlParseError,
    XmlParserConfig,
    create_xml_parser,
)
from acai.xml_parser.adapters.outbound.lxml_parser import LxmlParser
from acai.xml_parser.ports.xml_parser_port import XmlParserPort

# ── XML fixtures ──────────────────────────────────────────────────────

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"

MINIMAL_LAW_XML = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <akomaNtoso xmlns="{AKN_NS}">
      <act name="publicLaw">
        <meta>
          <identification source="#ch.bk">
            <FRBRWork>
              <FRBRnumber value="210"/>
              <FRBRname xml:lang="de" value="Schweizerisches Zivilgesetzbuch" shortForm="ZGB"/>
              <FRBRname xml:lang="fr" value="Code civil suisse" shortForm="CC"/>
            </FRBRWork>
          </identification>
        </meta>
        <body>
          <section eId="sec_1">
            <num>Erster Titel</num>
            <heading>Allgemeine Bestimmungen</heading>
            <article eId="art_1">
              <num>Art. 1</num>
              <paragraph eId="art_1__para_1">
                <content>
                  <p>Das Gesetz findet Anwendung.</p>
                </content>
              </paragraph>
            </article>
            <article eId="art_2">
              <num>Art. 2</num>
              <paragraph eId="art_2__para_1">
                <content>
                  <p>Jedermann hat Rechte.</p>
                </content>
              </paragraph>
              <paragraph eId="art_2__para_2">
                <content>
                  <p>Missbräuchliche Rechtsausübung ist unzulässig.</p>
                </content>
              </paragraph>
            </article>
          </section>
        </body>
      </act>
    </akomaNtoso>
""")

NO_ARTICLES_XML = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <akomaNtoso xmlns="{AKN_NS}">
      <act name="publicLaw">
        <meta>
          <identification source="#ch.bk">
            <FRBRWork>
              <FRBRnumber value="999"/>
            </FRBRWork>
          </identification>
        </meta>
        <body/>
      </act>
    </akomaNtoso>
""")

PREAMBLE_ONLY_XML = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <akomaNtoso xmlns="{AKN_NS}">
      <act name="publicLaw">
        <meta>
          <identification source="#ch.bk">
            <FRBRWork>
              <FRBRnumber value="101"/>
            </FRBRWork>
          </identification>
        </meta>
        <preamble>
          <p>Die Bundesversammlung beschliesst:</p>
        </preamble>
      </act>
    </akomaNtoso>
""")

NESTED_HEADINGS_XML = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <akomaNtoso xmlns="{AKN_NS}">
      <act name="publicLaw">
        <meta>
          <identification source="#ch.bk">
            <FRBRWork>
              <FRBRnumber value="220"/>
              <FRBRname xml:lang="de" value="Obligationenrecht" shortForm="OR"/>
            </FRBRWork>
          </identification>
        </meta>
        <body>
          <part eId="part_1">
            <num>Erster Teil</num>
            <heading>Allgemeine Bestimmungen</heading>
            <title eId="tit_1">
              <num>Erster Titel</num>
              <heading>Die Entstehung der Obligationen</heading>
              <chapter eId="chap_1">
                <num>Erstes Kapitel</num>
                <heading>Die Entstehung durch Vertrag</heading>
                <article eId="art_1">
                  <num>Art. 1</num>
                  <paragraph eId="art_1__para_1">
                    <content>
                      <p>Zum Abschlusse eines Vertrages ist die Willenseinigung erforderlich.</p>
                    </content>
                  </paragraph>
                </article>
              </chapter>
            </title>
          </part>
        </body>
      </act>
    </akomaNtoso>
""")


# ── helpers ───────────────────────────────────────────────────────────


def _write_xml(tmp_path: Path, xml_str: str, name: str = "test.xml") -> Path:
    """Write an XML string to a temp file and return the path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / name
    path.write_text(xml_str, encoding="utf-8")
    return path


# ── XmlParserConfig validation ────────────────────────────────────────


class TestXmlParserConfig:
    def test_defaults(self):
        cfg = XmlParserConfig()
        assert cfg.akn_namespace_uri == AKN_NS  # nosec B101
        assert cfg.language == "de"  # nosec B101

    def test_empty_namespace_raises(self):
        with pytest.raises(ConfigurationError, match="must not be empty"):
            XmlParserConfig(akn_namespace_uri="")

    def test_custom_language(self):
        cfg = XmlParserConfig(language="fr")
        assert cfg.language == "fr"  # nosec B101


# ── metadata extraction ──────────────────────────────────────────────


class TestMetadataExtraction:
    def test_extracts_law_number(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        parser = LxmlParser(logger=logger)
        result = parser.parse(path)
        assert result.metadata.law_number == "210"  # nosec B101

    def test_extracts_law_name_german(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        parser = LxmlParser(logger=logger)
        result = parser.parse(path)
        assert (
            result.metadata.law_name == "Schweizerisches Zivilgesetzbuch"
        )  # nosec B101

    def test_extracts_short_form(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        parser = LxmlParser(logger=logger)
        result = parser.parse(path)
        assert result.metadata.short_form == "ZGB"  # nosec B101

    def test_french_config_extracts_french_name(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        cfg = XmlParserConfig(language="fr")
        parser = LxmlParser(logger=logger, config=cfg)
        result = parser.parse(path)
        assert result.metadata.law_name == "Code civil suisse"  # nosec B101
        assert result.metadata.short_form == "CC"  # nosec B101

    def test_missing_metadata_returns_defaults(self, logger, work_dir):
        xml = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <akomaNtoso xmlns="{AKN_NS}">
              <act><meta/><body/></act>
            </akomaNtoso>
        """)
        path = _write_xml(work_dir, xml)
        parser = LxmlParser(logger=logger)
        result = parser.parse(path)
        assert result.metadata.law_number is None  # nosec B101
        assert result.metadata.law_name is None  # nosec B101
        assert result.metadata.short_form is None  # nosec B101


# ── article extraction ────────────────────────────────────────────────


class TestArticleExtraction:
    def test_finds_articles_in_body(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        parser = LxmlParser(logger=logger)
        result = parser.parse(path)
        assert len(result.articles) == 2  # nosec B101

    def test_article_number(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert result.articles[0].article == "Art. 1"  # nosec B101
        assert result.articles[1].article == "Art. 2"  # nosec B101

    def test_paragraphs_extracted(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert any(
            "Anwendung" in p for p in result.articles[0].paragraphs
        )  # nosec B101

    def test_multiple_paragraphs(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        art2 = result.articles[1]
        assert len(art2.paragraphs) >= 2  # nosec B101

    def test_no_articles_returns_empty_list(self, logger, work_dir):
        path = _write_xml(work_dir, NO_ARTICLES_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert result.articles == []  # nosec B101

    def test_preamble_fallback(self, logger, work_dir):
        path = _write_xml(work_dir, PREAMBLE_ONLY_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert len(result.articles) >= 1  # nosec B101
        assert any(  # nosec B101
            "Bundesversammlung" in p for a in result.articles for p in a.paragraphs
        )

    def test_deduplication_by_eid(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        eids = [a.article for a in result.articles]
        assert len(eids) == len(set(eids))  # nosec B101

    def test_result_types(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert isinstance(result, ParsedLawDocument)  # nosec B101
        assert isinstance(result.metadata, LawMetadata)  # nosec B101
        assert all(isinstance(a, ParsedArticle) for a in result.articles)  # nosec B101


# ── heading hierarchy ─────────────────────────────────────────────────


class TestHeadingHierarchy:
    def test_nested_headings_collected(self, logger, work_dir):
        path = _write_xml(work_dir, NESTED_HEADINGS_XML)
        result = LxmlParser(logger=logger).parse(path)
        assert len(result.articles) == 1  # nosec B101
        headings = result.articles[0].headings
        # Must contain headings from chapter up to part
        assert any("Allgemeine Bestimmungen" in h for h in headings)  # nosec B101
        assert any("Entstehung" in h for h in headings)  # nosec B101

    def test_headings_ordered_root_to_leaf(self, logger, work_dir):
        path = _write_xml(work_dir, NESTED_HEADINGS_XML)
        result = LxmlParser(logger=logger).parse(path)
        headings = result.articles[0].headings
        # Root-level headings come first
        assert len(headings) >= 2  # nosec B101
        # First heading should be from the outermost element
        combined = " ".join(headings)
        allgemein_pos = combined.find("Allgemeine Bestimmungen")
        vertrag_pos = combined.find("Vertrag")
        assert allgemein_pos < vertrag_pos  # nosec B101


# ── depth / level ─────────────────────────────────────────────────────


class TestArticleLevel:
    def test_level_is_integer(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        result = LxmlParser(logger=logger).parse(path)
        for article in result.articles:
            assert isinstance(article.level, int)  # nosec B101


# ── error handling ────────────────────────────────────────────────────


class TestErrorHandling:
    def test_missing_file_raises_parse_error(self, logger, work_dir):
        with pytest.raises(XmlParseError, match="Failed to load"):
            LxmlParser(logger=logger).parse(work_dir / "no_such_file.xml")

    def test_invalid_xml_raises_parse_error(self, logger, work_dir):
        path = work_dir / "bad.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("this is not xml at all {{{", encoding="utf-8")
        with pytest.raises(XmlParseError):
            LxmlParser(logger=logger).parse(path)

    def test_empty_file_raises_parse_error(self, logger, work_dir):
        path = work_dir / "empty.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        with pytest.raises(XmlParseError):
            LxmlParser(logger=logger).parse(path)


# ── factory ───────────────────────────────────────────────────────────


class TestFactory:
    def test_create_xml_parser_returns_lxml(self, logger):
        parser = create_xml_parser(logger)
        assert isinstance(parser, LxmlParser)  # nosec B101
        assert isinstance(parser, XmlParserPort)  # nosec B101

    def test_create_xml_parser_with_config(self, logger):
        cfg = XmlParserConfig(language="fr")
        parser = create_xml_parser(logger, cfg)
        assert isinstance(parser, LxmlParser)  # nosec B101

    def test_context_manager(self, logger, work_dir):
        path = _write_xml(work_dir, MINIMAL_LAW_XML)
        with create_xml_parser(logger) as parser:
            result = parser.parse(path)
            assert len(result.articles) == 2  # nosec B101


# ── exception hierarchy ──────────────────────────────────────────────


class TestExceptions:
    def test_parse_error_is_xml_parser_error(self):
        from acai.xml_parser.domain.exceptions import XmlParserError

        assert issubclass(XmlParseError, XmlParserError)  # nosec B101

    def test_configuration_error_is_xml_parser_error(self):
        from acai.xml_parser.domain.exceptions import XmlParserError

        assert issubclass(ConfigurationError, XmlParserError)  # nosec B101
