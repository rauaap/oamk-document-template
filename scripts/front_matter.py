"""Front-matter-driven cover and optional abstract pages for the ODT template."""
import re


def decode(value, render):
    if value['t'] == 'MetaMap':
        return {key: decode(item, render) for key, item in value['c'].items()}
    if value['t'] == 'MetaList':
        return [decode(item, render) for item in value['c']]
    if value['t'] == 'MetaBool':
        return value['c']
    return render(value)


def scalar(data, key, default=''):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f'{key} must be text')
    return value


def names(data, key):
    value = data.get(key, '')
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ' & '.join(value)
    raise ValueError(f'{key} must be a name or list of names')


def integer(value, key, minimum=0):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise ValueError(f'{key} must be an integer') from None
    if isinstance(value, bool) or result < minimum:
        raise ValueError(f'{key} must be at least {minimum}')
    return result


def parse(meta, render, start_override=None):
    data = {key: decode(value, render) for key, value in meta.items()}
    fields = {key: scalar(data, key) for key in
              ('title', 'subtitle', 'work-type', 'term', 'year', 'degree-programme', 'subject')}
    fields['institution'] = scalar(data, 'institution', 'Oulun ammattikorkeakoulu')
    fields['author'] = names(data, 'author')
    fields['lang'] = scalar(data, 'lang', 'fi-FI')
    if not re.fullmatch(r'[a-z]{2,3}(?:-[A-Z]{2})?', fields['lang']):
        raise ValueError('lang must look like fi-FI, en-US, or fi')
    fields['chapter-start'] = integer(start_override if start_override is not None
                                      else data.get('chapter-start', '1'), 'chapter-start', 1)
    fields['appendix-count'] = integer(data.get('appendix-count', '0'), 'appendix-count')
    abstracts = data.get('abstract', {})
    if not isinstance(abstracts, dict):
        raise ValueError('abstract must be a mapping containing fi and/or en')
    unknown = set(abstracts) - {'supervisor', 'fi', 'en'}
    if unknown:
        raise ValueError('Unknown abstract entries: ' + ', '.join(sorted(unknown)))
    fields['abstracts'] = []
    for language in ('fi', 'en'):
        if language not in abstracts:
            continue
        entry = abstracts[language]
        if not isinstance(entry, dict):
            raise ValueError(f'abstract.{language} must be a mapping')
        page = {key: scalar(entry, key, fields.get(key, '')) for key in
                ('title', 'degree-programme', 'institution', 'term', 'year', 'specialisation', 'text')}
        page['author'] = names(entry, 'author') if 'author' in entry else fields['author']
        page['supervisor'] = names(entry, 'supervisor') if 'supervisor' in entry else names(abstracts, 'supervisor')
        page['language'] = language
        if not page['text'].strip():
            raise ValueError(f'abstract.{language}.text is required and must not be empty')
        fields['abstracts'].append(page)
    return fields


def set_text(node, value):
    while node.firstChild:
        node.removeChild(node.firstChild)
    if value:
        node.appendChild(node.ownerDocument.createTextNode(value))


def set_language(styles, lang):
    language, _, country = lang.partition('-')
    for style in styles.getElementsByTagName('*'):
        if style.tagName == 'style:text-properties' and (
                style.hasAttribute('fo:language') or
                style.parentNode.getAttribute('style:name') == 'Standard'):
            style.setAttribute('fo:language', language)
            style.setAttribute('fo:country', country or 'none')


def populate_cover(content, fields):
    """Substitute tokens only before the ToC, preserving cover positioning/styles."""
    target = content.getElementsByTagName('office:text')[0]
    for node in target.childNodes:
        if getattr(node, 'tagName', None) == 'text:table-of-content':
            break
        def replace(parent):
            for child in parent.childNodes:
                if child.nodeType == child.TEXT_NODE:
                    child.data = re.sub(r'\{\{([a-z-]+)\}\}',
                                        lambda m: str(fields.get(m[1], m[0])), child.data)
                else:
                    replace(child)
        replace(node)


def add_abstracts(content, fields):
    target = content.getElementsByTagName('office:text')[0]
    toc = content.getElementsByTagName('text:table-of-content')[0]
    auto = content.getElementsByTagName('office:automatic-styles')[0]
    for page in fields['abstracts']:
        language = page['language']
        style_name = 'Report_Abstract_' + language
        style = content.createElement('style:style')
        for key, value in [('style:name', style_name), ('style:family', 'paragraph'),
                           ('style:parent-style-name', 'Tiivistelmän_20_teksti')]:
            style.setAttribute(key, value)
        props = content.createElement('style:text-properties')
        props.setAttribute('fo:language', language)
        props.setAttribute('fo:country', 'FI' if language == 'fi' else 'US')
        style.appendChild(props)
        auto.appendChild(style)
        heading_style = content.createElement('style:style')
        for key, value in [('style:name', style_name + '_Heading'),
                           ('style:family', 'paragraph'),
                           ('style:parent-style-name', 'Numeroimaton_20_Otsikko_20_1'),
                           ('style:master-page-name', 'Converted1')]:
            heading_style.setAttribute(key, value)
        # Use numbered-page footers after the unnumbered cover.
        heading_props = content.createElement('style:paragraph-properties')
        heading_props.setAttribute('fo:break-before', 'page')
        heading_props.setAttribute('style:page-number', 'auto')
        heading_style.appendChild(heading_props)
        heading_style.appendChild(props.cloneNode(True))
        auto.appendChild(heading_style)

        def paragraph(value='', heading=False):
            p = content.createElement('text:h' if heading else 'text:p')
            p.setAttribute('text:style-name', style_name + '_Heading' if heading else style_name)
            if heading:
                p.setAttribute('text:outline-level', '1')
                p.setAttribute('text:is-list-header', 'true')
            set_text(p, value)
            target.insertBefore(p, toc)
            return p

        paragraph('TIIVISTELMÄ' if language == 'fi' else 'ABSTRACT', heading=True)
        for key in ('institution', 'degree-programme', 'specialisation'):
            if page[key]:
                paragraph(page[key])
        labels = (['Tekijä(t)', 'Opinnäytetyön otsikko', 'Työn ohjaaja(t)',
                   'Työn valmistumislukukausi ja -vuosi', 'Sivumäärä'] if language == 'fi' else
                  ['Author(s)', 'Title of thesis', 'Supervisor(s)',
                   'Term and year when the thesis was submitted', 'Number of pages'])
        for label, value in zip(labels[:4], [page['author'], page['title'], page['supervisor'],
                                            ' '.join(v for v in (page['term'], page['year']) if v)]):
            paragraph(label + ': ' + value)
        p = paragraph(labels[4] + ': ')
        count = content.createElement('text:page-count')
        count.appendChild(content.createTextNode('0'))
        p.appendChild(count)
        if fields['appendix-count']:
            if language == 'fi':
                unit = 'liite' if fields['appendix-count'] == 1 else 'liitettä'
            else:
                unit = 'appendix' if fields['appendix-count'] == 1 else 'appendices'
            p.appendChild(content.createTextNode(f" + {fields['appendix-count']} {unit}"))
        for block in re.split(r'\n\s*\n', page['text'].strip()):
            paragraph(block.replace('\n', ' '))
