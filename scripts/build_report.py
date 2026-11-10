#!/usr/bin/python3
"""Merge Pandoc's Markdown body into our ODT, then refresh it with LibreOffice."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from xml.dom import minidom as DOM
import zipfile

if __package__:
    from .front_matter import parse, populate_cover, abstract_sections, add_abstracts, set_language
else:
    from front_matter import parse, populate_cover, abstract_sections, add_abstracts, set_language


def elements(node):
    return [n for n in node.childNodes if n.nodeType == n.ELEMENT_NODE]


def first(doc, tag):
    return doc.getElementsByTagName(tag)[0]


def metadata_text(value, ast):
    """Let Pandoc render formatted YAML metadata as plain text."""
    if not value:
        return ''
    kind, data = value['t'], value.get('c')
    if kind == 'MetaList':
        return '; '.join(metadata_text(item, ast) for item in data)
    if kind == 'MetaString':
        return data
    if kind not in ('MetaInlines', 'MetaBlocks'):
        raise ValueError(f'Unsupported metadata value: {kind}')
    blocks = [{'t': 'Plain', 'c': data}] if kind == 'MetaInlines' else data
    document = {'pandoc-api-version': ast['pandoc-api-version'], 'meta': {}, 'blocks': blocks}
    return subprocess.check_output(['pandoc', '-f', 'json', '-t', 'plain', '--wrap=none'],
                                   input=json.dumps(document).encode()).decode().strip()


def text_of(node):
    return ''.join(child.data if child.nodeType == child.TEXT_NODE else text_of(child)
                   for child in node.childNodes)


def uppercase_text(node):
    # Only text nodes: preserve link URLs, bookmark IDs, and formatting attributes.
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            child.data = child.data.upper()
        elif child.nodeType == child.ELEMENT_NODE:
            uppercase_text(child)


def merge(template, markdown, output, start=None):
    ast = json.loads(subprocess.check_output(['pandoc', str(markdown), '-f', 'markdown', '-t', 'json']))
    metadata = parse(ast['meta'], lambda value: metadata_text(value, ast), start)
    start = metadata['chapter-start']
    abstracts = abstract_sections(ast['blocks'], metadata)
    # Cover and abstract metadata are generated separately, not by Pandoc's title block.
    ast['meta'] = {}
    unnumbered = set()

    def walk(value):
        if isinstance(value, dict):
            if value.get('t') == 'Header':
                _, attrs, _ = value['c']
                if 'unnumbered' in attrs[1]:
                    unnumbered.add(attrs[0])
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(ast)
    with tempfile.TemporaryDirectory() as work:
        generated = Path(work) / 'body.odt'
        subprocess.run(['pandoc', '-f', 'json', '-t', 'odt',
                        '--reference-doc', str(template),
                        '--resource-path', str(markdown.parent.resolve()),
                        '-o', str(generated)], input=json.dumps(ast).encode(), check=True)
        with zipfile.ZipFile(template) as base, zipfile.ZipFile(generated) as body:
            content = DOM.parseString(base.read('content.xml'))
            styles = DOM.parseString(base.read('styles.xml'))
            incoming = DOM.parseString(body.read('content.xml'))
            incoming_styles = DOM.parseString(body.read('styles.xml'))
            meta = DOM.parseString(base.read('meta.xml'))
            meta_root = first(meta, 'office:meta')
            for tag, value in [('dc:title', metadata['title']),
                               ('dc:creator', metadata['author']),
                               ('meta:initial-creator', metadata['author']),
                               ('dc:subject', metadata['subject']),
                               ('dc:language', metadata['lang'])]:
                for old in list(meta.getElementsByTagName(tag)):
                    old.parentNode.removeChild(old)
                if value:
                    field = meta.createElement(tag)
                    field.appendChild(meta.createTextNode(value))
                    meta_root.appendChild(field)
            # Imported Word heading styles can still point to independent lists.
            # All numbered heading levels must use the shared outline instead.
            for style in styles.getElementsByTagName('style:style'):
                if (style.getAttribute('style:name').startswith('Heading_20_')
                        and style.getAttribute('style:family') == 'paragraph'):
                    for attr in ('style:list-style-name', 'style:list-level'):
                        if style.hasAttribute(attr):
                            style.removeAttribute(attr)
            # Preserve namespace declarations needed by tables, math, drawings, etc.
            for source, dest in [(incoming, content), (incoming_styles, styles)]:
                for attr in source.documentElement.attributes.values():
                    if attr.name.startswith('xmlns:') and not dest.documentElement.hasAttribute(attr.name):
                        dest.documentElement.setAttribute(attr.name, attr.value)

            auto = first(incoming, 'office:automatic-styles')
            names = {n.getAttribute('style:name'): 'MD_' + n.getAttribute('style:name')
                     for n in elements(auto) if n.hasAttribute('style:name')}
            for node in incoming.getElementsByTagName('*'):
                for attr in list(node.attributes.values()):
                    if (attr.localName.endswith('style-name') or attr.name == 'style:name') and attr.value in names:
                        node.setAttribute(attr.name, names[attr.value])
            for node in elements(auto):
                first(content, 'office:automatic-styles').appendChild(content.importNode(node, True))
            # Pandoc supplies extra styles for code, tables, etc.; existing template styles win.
            for tag, key in [('office:styles', 'style:name'), ('office:font-face-decls', 'style:name')]:
                dest = first(styles, tag)
                known = {n.getAttribute(key) for n in elements(dest)}
                for node in elements(first(incoming_styles, tag)):
                    if node.getAttribute(key) not in known:
                        dest.appendChild(styles.importNode(node, True))

            set_language(styles, metadata['lang'])
            set_language(content, metadata['lang'])
            populate_cover(content, metadata)

            # Pandoc list paragraphs inherit Text body (115% spacing). Use a
            # dedicated body-derived style with explicit 150% and zero item gaps.
            list_style = content.createElement('style:style')
            for key, value in [('style:name', 'MD_List_Paragraph'),
                               ('style:family', 'paragraph'),
                               ('style:parent-style-name', 'Standard')]:
                list_style.setAttribute(key, value)
            props = content.createElement('style:paragraph-properties')
            for key, value in [('fo:line-height', '150%'), ('fo:margin-top', '0in'),
                               ('fo:margin-bottom', '0in')]:
                props.setAttribute(key, value)
            list_style.appendChild(props)
            first(content, 'office:automatic-styles').appendChild(list_style)

            target = first(content, 'office:text')
            toc = first(content, 'text:table-of-content')
            # Keep everything through the ToC; replace all subsequent content.
            while toc.nextSibling:
                target.removeChild(toc.nextSibling)
            first_numbered = True
            # Abstract sections are moved before the ToC once the body is merged.
            abstract_bodies, abstract = {}, None
            for node in elements(first(incoming, 'office:text')):
                for p in [node] + list(node.getElementsByTagName('*')):
                    if p.getAttribute('text:style-name') in ('Text_20_body', 'First_20_paragraph'):
                        p.setAttribute('text:style-name', 'Standard')
                    if p.tagName == 'text:p':
                        parent = p.parentNode
                        while parent is not None and parent is not incoming:
                            if getattr(parent, 'tagName', None) == 'text:list-item':
                                p.setAttribute('text:style-name', 'MD_List_Paragraph')
                                break
                            parent = parent.parentNode
                if node.tagName == 'text:h':
                    marks = node.getElementsByTagName('text:bookmark-start')
                    ids = {m.getAttribute('text:name') for m in marks}
                    is_unnumbered = bool(ids & unnumbered)
                    level = node.getAttribute('text:outline-level')
                    if level == '1':
                        uppercase_text(node)
                        abstract = next((abstracts[i] for i in ids if i in abstracts), None)
                        if abstract:
                            abstract_bodies[abstract] = (text_of(node), [])
                            continue
                    if is_unnumbered and level != '1':
                        # A body paragraph, not an outline heading: no numbering,
                        # no ToC entry, no reset of subsequent numbered headings.
                        paragraph = incoming.createElement('text:p')
                        paragraph.setAttribute('text:style-name', 'Väliotsikko_20_tekstissä')
                        while node.firstChild:
                            paragraph.appendChild(node.firstChild)
                        node = paragraph
                    elif is_unnumbered:
                        node.setAttribute('text:style-name', 'P14')
                        node.setAttribute('text:is-list-header', 'true')
                    elif level == '1' and first_numbered:
                        node.setAttribute('text:restart-numbering', 'true')
                        node.setAttribute('text:start-value', str(start))
                        first_numbered = False
                if abstract:
                    abstract_bodies[abstract][1].append(content.importNode(node, True))
                else:
                    target.appendChild(content.importNode(node, True))
            add_abstracts(content, metadata, abstract_bodies)

            manifest = DOM.parseString(base.read('META-INF/manifest.xml'))
            base_names = set(base.namelist())
            additions = [n for n in body.namelist()
                         if n.startswith(('Pictures/', 'media/')) and n not in base_names]
            for entry in DOM.parseString(body.read('META-INF/manifest.xml')).getElementsByTagName('manifest:file-entry'):
                if entry.getAttribute('manifest:full-path') in additions:
                    manifest.documentElement.appendChild(manifest.importNode(entry, True))
            with zipfile.ZipFile(output, 'w') as out:
                replacements = {'content.xml': content.toxml(encoding='UTF-8'),
                                'styles.xml': styles.toxml(encoding='UTF-8'),
                                'meta.xml': meta.toxml(encoding='UTF-8'),
                                'META-INF/manifest.xml': manifest.toxml(encoding='UTF-8')}
                for info in base.infolist():
                    out.writestr(info, replacements.get(info.filename, base.read(info.filename)))
                for name in additions:
                    out.writestr(name, body.read(name))


def refresh(odt, pdf):
    import uno

    def prop(name, value):
        p = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        p.Name, p.Value = name, value
        return p

    with tempfile.TemporaryDirectory(prefix='report-lo-') as profile:
        pipe = 'report_' + uuid.uuid4().hex
        process = subprocess.Popen(['libreoffice', '-env:UserInstallation=' + Path(profile).as_uri(),
                                    '--headless', '--norestore', '--nodefault',
                                    '--accept=pipe,name=' + pipe + ';urp;StarOffice.ComponentContext'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        desktop = doc = None
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
            deadline = time.monotonic() + 30
            while True:
                try:
                    context = resolver.resolve('uno:pipe,name=' + pipe + ';urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    if time.monotonic() > deadline or process.poll() is not None:
                        raise RuntimeError('Could not connect to headless LibreOffice')
                    time.sleep(0.2)
            desktop = context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
            doc = desktop.loadComponentFromURL(odt.resolve().as_uri(), '_blank', 0,
                                               (prop('Hidden', True), prop('UpdateDocMode', 3)))
            if doc is None:
                raise RuntimeError('LibreOffice could not open the generated ODT')
            # Two passes allow the ToC's own page count to settle.
            for _ in range(2):
                doc.refresh()
                doc.getTextFields().refresh()
                indexes = doc.getDocumentIndexes()
                for i in range(indexes.getCount()):
                    indexes.getByIndex(i).update()
            doc.store()
            doc.storeToURL(pdf.resolve().as_uri(), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
        finally:
            if doc is not None:
                doc.close(True)
            if desktop is not None:
                desktop.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--markdown', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=None,
                        help='Override front matter chapter-start (default: 1)')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only after a successful build, leaving previous output intact on failure.
    with tempfile.TemporaryDirectory(dir=args.output.parent) as work:
        odt = Path(work) / args.output.name
        pdf = odt.with_suffix('.pdf')
        merge(args.template, args.markdown, odt, args.start)
        refresh(odt, pdf)
        odt.replace(args.output)
        pdf.replace(args.output.with_suffix('.pdf'))
    print(f'Built {args.output} and {args.output.with_suffix(".pdf")}')


if __name__ == '__main__':
    main()
