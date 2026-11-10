import tempfile
import unittest
from pathlib import Path
from xml.dom import minidom as DOM
import zipfile

from scripts.build_report import merge, refresh


ROOT = Path(__file__).resolve().parents[1]


def text(node):
    return ''.join(child.data if child.nodeType == child.TEXT_NODE else text(child)
                   for child in node.childNodes)


class ReportTest(unittest.TestCase):
    def test_formatting_and_metadata_survive_libreoffice(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            md, odt = work / 'body.md', work / 'report.odt'
            md.write_text('''---
title: "Test & report"
author:
  - First Writer
  - Second Writer
subject: Formatting test
---

# Mixed **case** [title](https://example.com/KeepCase) {#first}

Body text.

## Numbered

- First item
  - Nested item
- Second item

1. Ordered item
2. Another item

## In-text heading {.unnumbered}

Paragraph.

### Another in-text heading {.unnumbered}

Paragraph.

## Still numbered

# Second chapter

## Reset subheading

# Lähteet {.unnumbered}

Reference.
''', encoding='utf-8')
            merge(ROOT / 'templates/report.odt', md, odt, 2)
            with zipfile.ZipFile(odt) as z:
                content = DOM.parseString(z.read('content.xml'))
                meta = DOM.parseString(z.read('meta.xml'))
                self.assertEqual(text(meta.getElementsByTagName('dc:title')[0]), 'Test & report')
                self.assertEqual(text(meta.getElementsByTagName('dc:creator')[0]),
                                 'First Writer & Second Writer')
                headings = content.getElementsByTagName('text:h')
                self.assertEqual(text(headings[0]), 'MIXED CASE TITLE')
                self.assertEqual(headings[0].getElementsByTagName('text:a')[0].getAttribute('xlink:href'),
                                 'https://example.com/KeepCase')
                self.assertEqual(headings[0].getElementsByTagName('text:bookmark-start')[0].getAttribute('text:name'),
                                 'first')
                self.assertEqual(text(headings[-1]), 'LÄHTEET')
                self.assertNotIn('In-text heading', [text(h) for h in headings])
                for p in content.getElementsByTagName('text:p'):
                    if text(p) in ('In-text heading', 'Another in-text heading'):
                        self.assertEqual(p.getAttribute('text:style-name'), 'Väliotsikko_20_tekstissä')
                    if text(p) in ('First item', 'Nested item', 'Second item', 'Ordered item', 'Another item'):
                        self.assertEqual(p.getAttribute('text:style-name'), 'MD_List_Paragraph')
                # Exactly the cover title, not an extra Pandoc title block.
                self.assertEqual([text(p) for p in content.getElementsByTagName('text:p')].count('Test & report'), 1)
                list_style = next(s for s in content.getElementsByTagName('style:style')
                                  if s.getAttribute('style:name') == 'MD_List_Paragraph')
                props = list_style.getElementsByTagName('style:paragraph-properties')[0]
                self.assertEqual(props.getAttribute('fo:line-height'), '150%')
                self.assertEqual(props.getAttribute('fo:margin-bottom'), '0in')
            refresh(odt, work / 'report.pdf')
            with zipfile.ZipFile(odt) as z:
                content = DOM.parseString(z.read('content.xml'))
                toc = text(content.getElementsByTagName('text:table-of-content')[0])
                self.assertIn('2 MIXED CASE TITLE', toc)
                self.assertIn('2.1 Numbered', toc)
                self.assertIn('2.2 Still numbered', toc)
                self.assertIn('3 SECOND CHAPTER', toc)
                self.assertIn('3.1 Reset subheading', toc)
                self.assertIn('LÄHTEET', toc)
                self.assertNotIn('In-text heading', toc)
                self.assertNotIn('Another in-text heading', toc)
                meta = DOM.parseString(z.read('meta.xml'))
                self.assertEqual(text(meta.getElementsByTagName('dc:title')[0]), 'Test & report')
            self.assertTrue((work / 'report.pdf').is_file())

    def test_cover_and_optional_abstracts(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            md, odt = work / 'body.md', work / 'report.odt'
            md.write_text('''---
title: Example report
subtitle: Example subtitle
author: Test Writer
work-type: Opinnäytetyö (AMK)
term: Kevät
year: 2026
degree-programme: Tietotekniikka
institution: Oulun ammattikorkeakoulu
lang: fi-FI
chapter-start: 4
appendix-count: 2
abstract:
  supervisor: Test Supervisor
  fi:
    text: |
      Suomenkielinen ensimmäinen kappale.

      Suomenkielinen toinen kappale.
  en:
    title: English title
    institution: Oulu University of Applied Sciences
    degree-programme: Information Technology
    term: Spring
    text: English abstract paragraph.
---

# First chapter

Body.
''', encoding='utf-8')
            merge(ROOT / 'templates/report.odt', md, odt)
            with zipfile.ZipFile(odt) as z:
                content = DOM.parseString(z.read('content.xml'))
                root = content.getElementsByTagName('office:text')[0]
                children = [n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE]
                toc = content.getElementsByTagName('text:table-of-content')[0]
                before_toc = children[:children.index(toc)]
                cover_text = '\n'.join(text(n) for n in before_toc)
                self.assertNotIn('{{', cover_text)
                for value in ('Example report', 'Example subtitle', 'Test Writer', 'Kevät 2026',
                              'Opinnäytetyö (AMK)', 'Tietotekniikka', 'Oulun ammattikorkeakoulu',
                              'TIIVISTELMÄ', 'ABSTRACT', 'Test Supervisor',
                              'Opinnäytetyön otsikko: Example report', 'Title of thesis: English title',
                              'Spring 2026', 'Suomenkielinen toinen kappale.'):
                    self.assertIn(value, cover_text)
                self.assertEqual(len(content.getElementsByTagName('text:page-count')), 2)
                self.assertLess(cover_text.index('TIIVISTELMÄ'), cover_text.index('ABSTRACT'))
            refresh(odt, work / 'report.pdf')
            with zipfile.ZipFile(odt) as z:
                content = DOM.parseString(z.read('content.xml'))
                toc = text(content.getElementsByTagName('text:table-of-content')[0])
                self.assertIn('TIIVISTELMÄ', toc)
                self.assertIn('ABSTRACT', toc)
                self.assertIn('4 FIRST CHAPTER', toc)
                for count in content.getElementsByTagName('text:page-count'):
                    self.assertGreater(int(text(count)), 0)

    def test_each_abstract_language_is_optional(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            md, odt = work / 'body.md', work / 'report.odt'
            for language, title in [('fi', 'TIIVISTELMÄ'), ('en', 'ABSTRACT')]:
                with self.subTest(language=language):
                    md.write_text(f'---\ntitle: Report\nabstract:\n  {language}:\n    text: Summary.\n---\n# Body\n')
                    merge(ROOT / 'templates/report.odt', md, odt)
                    with zipfile.ZipFile(odt) as z:
                        content = DOM.parseString(z.read('content.xml'))
                        headings = content.getElementsByTagName('text:h')
                        self.assertEqual([text(h) for h in headings], [title, 'BODY'])
                        self.assertEqual(headings[-1].getAttribute('text:start-value'), '1')

    def test_invalid_abstract_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            md = work / 'body.md'
            md.write_text('---\nabstract:\n  fi:\n    title: Missing text\n---\n# Heading\n')
            with self.assertRaisesRegex(ValueError, 'abstract.fi.text'):
                merge(ROOT / 'templates/report.odt', md, work / 'report.odt')

    def test_missing_metadata_clears_template_author(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            md, odt = work / 'body.md', work / 'report.odt'
            md.write_text('# Chapter\n', encoding='utf-8')
            merge(ROOT / 'templates/report.odt', md, odt, 2)
            with zipfile.ZipFile(odt) as z:
                meta = DOM.parseString(z.read('meta.xml'))
                for tag in ('dc:title', 'dc:creator', 'meta:initial-creator'):
                    self.assertFalse(meta.getElementsByTagName(tag))
                content = DOM.parseString(z.read('content.xml'))
                headings = content.getElementsByTagName('text:h')
                self.assertEqual(len(headings), 1)
                self.assertEqual(headings[0].getAttribute('text:start-value'), '2')


if __name__ == '__main__':
    unittest.main()
