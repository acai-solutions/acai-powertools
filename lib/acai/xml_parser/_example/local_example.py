"""
Example: Parsing AKN XML law documents
=======================================

Run directly::

    python -m acai.xml_parser._example.local_example

Demonstrates metadata extraction, article parsing, heading hierarchy,
configuration options, error handling, and the ``create_xml_parser`` factory.

Requirements
------------
- lxml installed (``pip install lxml``)
"""

import shutil
import tempfile
import textwrap
from pathlib import Path

from acai.logging import LoggerConfig, LogLevel, create_logger
from acai.xml_parser import XmlParseError, XmlParserConfig, create_xml_parser

AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"

SAMPLE_XML = textwrap.dedent(f"""\
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
            <heading>Einleitung</heading>
            <article eId="art_1">
              <num>Art. 1</num>
              <heading>A. Anwendung des Rechts</heading>
              <paragraph eId="art_1__para_1">
                <content>
                  <p>Das Gesetz findet auf alle Rechtsfragen Anwendung.</p>
                </content>
              </paragraph>
            </article>
            <article eId="art_2">
              <num>Art. 2</num>
              <heading>B. Inhalt der Rechtsverhaeltnisse</heading>
              <paragraph eId="art_2__para_1">
                <content>
                  <p>Jedermann hat in der Ausuebung seiner Rechte nach Treu und Glauben zu handeln.</p>
                </content>
              </paragraph>
              <paragraph eId="art_2__para_2">
                <content>
                  <p>Der offenbare Missbrauch eines Rechtes findet keinen Rechtsschutz.</p>
                </content>
              </paragraph>
            </article>
          </section>
        </body>
      </act>
    </akomaNtoso>
""")


def main() -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="acai_xmlparser_example_"))
    logger = create_logger(
        LoggerConfig(service_name="xml-parser-example", log_level=LogLevel.DEBUG)
    )

    try:
        # Write sample XML to disk
        xml_path = work_dir / "sample_law.xml"
        xml_path.write_text(SAMPLE_XML, encoding="utf-8")

        # ── 1. Basic parsing ──────────────────────────────────────────
        parser = create_xml_parser(logger)
        result = parser.parse(xml_path)

        print("── 1. Metadata ─────────────────────────────────────")
        print(f"  Law number : {result.metadata.law_number}")
        print(f"  Law name   : {result.metadata.law_name}")
        print(f"  Short form : {result.metadata.short_form}")

        print(f"\n── 2. Articles ({len(result.articles)}) ─────────────────────────")
        for art in result.articles:
            print(f"\n  {art.article}")
            print(f"    Headings   : {art.headings}")
            print(f"    Level      : {art.level}")
            print(f"    Paragraphs : {len(art.paragraphs)}")
            for i, p in enumerate(art.paragraphs, 1):
                print(f"      {i}. {p[:80]}")

        # ── 3. French config ──────────────────────────────────────────
        print("\n── 3. French metadata ──────────────────────────────")
        fr_parser = create_xml_parser(logger, XmlParserConfig(language="fr"))
        fr_result = fr_parser.parse(xml_path)
        print(f"  Law name   : {fr_result.metadata.law_name}")
        print(f"  Short form : {fr_result.metadata.short_form}")

        # ── 4. Context manager ────────────────────────────────────────
        print("\n── 4. Context manager ──────────────────────────────")
        with create_xml_parser(logger) as ctx_parser:
            ctx_result = ctx_parser.parse(xml_path)
            print(f"  Parsed {len(ctx_result.articles)} articles via context manager")

        # ── 5. Error handling ─────────────────────────────────────────
        print("\n── 5. Error handling ───────────────────────────────")
        try:
            parser.parse(work_dir / "does_not_exist.xml")
            print("  ERROR — should have raised XmlParseError")
        except XmlParseError as exc:
            print(f"  Caught expected error: {exc}")

        # ── 6. Real file (if available) ───────────────────────────────
        real_dir = Path(__file__).resolve().parents[5] / "data" / "20-xml-store"
        if real_dir.exists():
            real_files = list(real_dir.glob("*.xml"))[:1]
            if real_files:
                print(f"\n── 6. Real file: {real_files[0].name} ──────────")
                real_result = parser.parse(real_files[0])
                print(f"  Law number : {real_result.metadata.law_number}")
                print(f"  Law name   : {real_result.metadata.law_name}")
                print(f"  Articles   : {len(real_result.articles)}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"\nCleaned up {work_dir}")


if __name__ == "__main__":
    main()
