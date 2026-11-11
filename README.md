# Markdown report / thesis template

A reusable Oamk-style report and thesis starter. **`report.md`** contains placeholder
cover details, a suggested structure, and commented examples for optional abstracts.
Replace all placeholder and instructional text before submitting your work. The
suggested chapter structure is not mandatory: follow your assignment or thesis
reporting requirements.

Write the report in **`report.md`**, then run:

```sh
make
```

Outputs:

- `build/report.odt` — editable Writer document
- `build/report.pdf` — rendered report

The build fills the cover from front matter, optionally inserts abstract pages,
retains the ToC layout and styles from `templates/report.odt`, and replaces the
body with Markdown. A separate headless LibreOffice instance refreshes the ToC
and page-count fields and exports PDF. The template itself is not changed by a
build.

`make` only rebuilds when its inputs change. `Nothing to be done` means the
outputs are already up to date. Use `make -B` to force a rebuild.

## Front matter and cover

```yaml
---
title: Työn otsikko
# subtitle: Optional subtitle
author:
  - Etunimi Sukunimi
work-type: Opinnäytetyö (AMK)
term: Kevät
year: "20XX"
degree-programme: Tutkinto-ohjelman nimi
institution: Oulun ammattikorkeakoulu
lang: fi-FI
chapter-start: 1
# subject: Optional document metadata
---
```

- `title`, `subtitle`, `author`, `work-type`, `term`, `year`, `degree-programme`,
  and `institution` populate the existing cover positions.
- `author` accepts one name or a YAML list; multiple names are joined with ` & `.
- Omitting `subtitle` leaves its position empty without moving the cover layout.
- `title`, `author`, `subject`, and `lang` also populate document metadata.
- `institution` defaults to `Oulun ammattikorkeakoulu`; `lang` defaults to `fi-FI`;
  `chapter-start` defaults to `1`. Other omitted cover fields are empty.
- `lang` sets the document and style language; it does not translate text.
- No extra Pandoc title block is inserted into the report body.

The template's cover contains `{{title}}`, `{{subtitle}}`, `{{author}}`,
`{{work-type}}`, `{{term}} {{year}}`, `{{degree-programme}}`, and `{{institution}}`
placeholders. When editing the template, keep each placeholder together as plain
text (do not apply different formatting to individual characters within it).
Edit front matter for report-specific text; edit `templates/report.odt` in Writer
for layout and styles.

## Optional abstracts

An abstract has two parts: its metadata block goes in the YAML front matter,
and its text goes in the Markdown body. Add both only when needed:

```yaml
abstract:
  supervisor:
    - Ohjaajan Nimi
  fi:
    # title, degree-programme, institution, term, year, and author
    # inherit their top-level values unless overridden here.
    specialisation: Optional specialisation
  en:
    title: English thesis title
    institution: Oulu University of Applied Sciences
    degree-programme: Degree Programme in Information Technology
    term: Autumn
```

```markdown
# Tiivistelmä {.abstract lang=fi}

Tiivistelmän ensimmäinen kappale.

Tiivistelmän toinen kappale.

# Abstract {.abstract lang=en}

The English abstract goes here.
```

- Omit `abstract`: no abstract pages. An empty mapping (`abstract: {}`) also
  produces none. A bare `fi:` (or `fi: {}`) enables a page that only inherits
  top-level values.
- Each front-matter entry (`abstract.fi`, `abstract.en`) requires exactly one
  body section with the matching `lang`, and each body section requires its
  front-matter entry. The build fails if either side is missing.
- An abstract section is a level-1 heading with `{.abstract lang=fi}` or
  `{.abstract lang=en}`. It ends at the next level-1 heading and may contain only
  paragraphs (inline formatting such as *italic* is kept). The heading text is
  used, uppercased.
- Abstracts appear after the cover and before the ToC, regardless of where the
  sections are in the Markdown. When both exist, Finnish comes first. Each starts
  on a new page and is included in the ToC without chapter numbering.
- Keep each abstract within one page as required by the mallipohja; the build
  does not shorten overflowing text.
- Author, title, degree programme, institution, term, and year inherit the
  top-level values. Override translated English values explicitly.
- `specialisation` is optional. `supervisor` accepts a name or list and can be
  overridden inside each language entry.
- A live page-count field shows the **total generated document page count**,
  including cover, abstracts, ToC, body, and any appendix pages. It is refreshed
  during the build. The build does not yet identify or subtract appendix pages.
- Optional top-level `appendix-count: 2` adds `+ 2 liitettä` / `+ 2 appendices`
  after that total. This is the manually supplied number of appendices, not their
  page count; no automatic appendix detection is implemented.

The starter `report.md` comments out the abstract configuration and the example
sections (inside an HTML comment at the top of the body). Uncomment the `fi`
and/or `en` entries together with the matching sections, then replace the
example text.

## Writing

```markdown
# Oman kirjoittamisen analyysi

Normal paragraph with **bold**, *italic*, and [a link](https://example.com).

## Oma alaotsikko

An introduction to the list:

- First item
- Second item

## Väliotsikko {.unnumbered}

An unnumbered in-text heading, excluded from the ToC.

# Tekstiä lähteiden pohjalta

Another chapter.

# Lähteet {.unnumbered}

Your references here.
```

Do **not** type chapter numbers: `#` headings are numbered automatically;
`##` and `###` headings inherit the chapter number. Top-level headings start new
pages and their actual text is automatically uppercased, including PDF bookmarks.
Link URLs and bookmark IDs are unchanged.

- `# Lähteet {.unnumbered}`: unnumbered chapter, new page, **included in the ToC**.
- `## Väliotsikko {.unnumbered}` (or deeper): the template's **Väliotsikko
  tekstissä** body style, **excluded from the ToC**, no page break. It does not
  advance numbered subheadings.

Regular paragraphs use the template's body style. Bullet and numbered list
paragraphs use 1.5 line spacing with no added spacing between items. Pandoc
handles links, tables, code, and images (image paths are relative to the Markdown
file). Specialist formatting is not fully automated: see `TODO.md`. Inspect the
PDF before submission. Liberation Sans is an accepted substitute for Arial on
this machine.

## Chapter numbering

The starter uses `chapter-start: 1`. If writing only a later part of a report,
change this in front matter, for example:

```yaml
chapter-start: 2
```

An optional command-line override is available:

```sh
make -B START=1
```

`-B` forces a rebuild when only command-line settings change.

## Reusing this repository

1. Create a new repository from this template (or copy/clone it).
2. Replace the cover placeholders in `report.md` with your own details.
3. For a course report, set `work-type` to the course or assignment name, leave
   abstracts disabled, and replace the example chapters with the required structure.
4. For a thesis, set the appropriate work type, enable the required abstract
   languages, and adapt the chapter structure to your thesis type.
5. Run `make`, inspect the PDF, and remove all remaining example/instructional text.

Keep the reusable layout in `templates/report.odt`; report-specific details belong
in Markdown. Optional appendix pages are not included in the starter: add them
only as needed and check the limitations in `TODO.md`.

## Template and generated files

Edit `templates/report.odt` in Writer to change the cover layout, ToC layout, or
styles. Save it before running `make`. Everything after its ToC is discarded
during the build, but the styles remain. Abstract pages are generated by the
build; do not manually insert them into the template.

Generated files are outputs: edits made directly to them are lost on rebuild.
If an output is already open in Writer, use **File → Reload** after building;
do not save the stale open copy over the newly generated file.

## Setup and tests

Requires `uv`, GNU Make (4.3+), Pandoc, LibreOffice Writer, and LibreOffice's Python
UNO bindings. On this machine the bindings are available in `/usr/bin/python3`.

`make setup` creates a **uv-managed environment with system-site-packages** so it
can import the distribution's `uno` module. No PyPI dependencies are needed.
`uv.lock` locks the project. The Makefile uses `uv run --no-sync` after setup to
preserve this environment configuration.

If your UNO-compatible Python is elsewhere:

```sh
make setup SYSTEM_PYTHON=/path/to/python3
```

Use `make clean` to remove generated files (not the template or Markdown).
Run `make test` for regression tests including real headless LibreOffice renders,
ToC refreshes, cover/abstract generation, formatting, and metadata.
