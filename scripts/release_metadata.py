#!/usr/bin/env python3
"""Read explicit release labels from public pages and existing URL filenames."""
import argparse
import base64
import datetime
import html.parser
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from check_links import status_key

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOWNLOAD_HOSTS = ('1fichier.com', 'mediafire.com', 'mega.nz', 'drive.google.com',
                  'akirabox.com', 'vikingfile.com', 'filefactory.com', 'filecrypt.co')


def clean(text):
    return ' '.join(text.split()).strip()


def downloadable(url):
    p = urllib.parse.urlsplit(url)
    return (p.scheme in ('http', 'https') and not p.username and not p.password
            and any(p.hostname == h or (p.hostname or '').endswith('.' + h) for h in DOWNLOAD_HOSTS))


def unique(pattern, text):
    values = set(re.findall(pattern, text, re.I))
    return next(iter(values)) if len(values) == 1 else None


def details(text, filename=False):
    """Only explicit markers; v1.00 alone never implies a base game."""
    result = {}
    title_id = unique(r'\b(CUSA\d{5})\b', text.replace('_', ' '))
    version = unique(r'(?:\bv(?:ersion)?\s*|\bupdate\s*v?\s*)(\d{1,3}\.\d{1,3}(?:\.\d+)?)', text.replace('_', ' '))
    if title_id:
        result['title_id'] = title_id.upper()
    if version:
        result['version'] = version
    if not filename:
        region = unique(r'\b(EUR|USA|JPN|ASIA|KOR|UK|EU|US|JP)\b', text)
        if region:
            result['region'] = region.upper()
    normalized = text.replace('_', ' ')
    base = bool(re.search(r'\bbase(?:\s+game)?\b|^\s*game\b', normalized, re.I))
    update = bool(re.search(r'\bupdate\b|\bpatch\b', normalized, re.I))
    dlc = bool(re.search(r'\bdlc(?:pack|s)?\b', normalized, re.I))
    kinds = [kind for present, kind in [(base, 'base'), (update, 'update'), (dlc, 'dlc')] if present]
    if kinds:
        result['kind'] = kinds[0] if len(kinds) == 1 else 'bundle'
    elif re.match(r'^\s*(?:fix|backport)\b', normalized, re.I):
        result['kind'] = 'fix'
    if re.search(r'\bbackport\b|\bfix\s+\d', normalized, re.I):
        result['variant'] = 'Backport / fix'
    firmware = re.search(r'\((?:fix\s*|fw\s*|firmware\s*)?(\d+\.(?:\d+|xx)(?:\s*[/+–-]\s*\d+\.(?:\d+|xx))*\+?)\)', normalized, re.I)
    if filename and not firmware:
        firmware = re.search(r'\[(\d+\.(?:\d+|xx)(?:\s*[/+–-]\s*\d+\.(?:\d+|xx))*\+?)\]', normalized, re.I)
    if firmware:
        result['firmware'] = re.sub(r'\s+', '', firmware[1]).replace('-', '/')
    return result


def filename_details(url):
    p = urllib.parse.urlsplit(url)
    # Only a visible MediaFire filename, never random IDs or arbitrary path digits.
    match = re.match(r'/file/[^/]+/([^/]+)', urllib.parse.unquote(p.path))
    if p.hostname not in ('mediafire.com', 'www.mediafire.com') or not match:
        return {}
    name = match[1]
    result = details(name, filename=True)
    if result:
        result.update(evidence='URL filename', filename=name)
    return result


class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or []), parent, []

    def text(self):
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children if isinstance(c, str) or c.tag not in ('script', 'style'))

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node) and c.tag not in ('script', 'style'):
                yield from c.walk()


class Tree(html.parser.HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        # Match HTML's implicit paragraph closing (source pages contain <p><div>).
        if tag in ('p', 'div', 'table', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote'):
            node = self.current
            while node.parent:
                if node.tag == 'p':
                    self.current = node.parent
                    break
                node = node.parent
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def expand_labels(body):
    # These public labels are base64 text, inserted by the source's own UI.
    # Decode data only: never execute source JavaScript or load embedded resources.
    def decode(match):
        try:
            raw = base64.b64decode(match[1], validate=True)
            return raw.decode('utf-8') if len(raw) <= 500000 else ''
        except (ValueError, UnicodeError):
            return ''
    return re.sub(r'<div\b[^>]*class="secure-data"[^>]*data-payload="([^"]+)"[^>]*>[^<]*</div>', decode, body)


def parse_source(body, source_url):
    if urllib.parse.urlsplit(source_url).hostname != 'dlpsgame.com':
        return []  # Other source layouts need their own proven adapter.
    root = Tree(expand_labels(body)).root
    content = next((n for n in root.walk() if 'entry-content' in n.attrs.get('class', '').split()), None)
    if content is None:
        return []
    result, context, section = [], {}, ''
    for node in content.walk():
        if node.tag not in ('p', 'li', 'h2', 'h3', 'h4'):
            continue
        # A parent paragraph/list item already owns any nested block.
        parent = node.parent
        if any(n.tag in ('p', 'li') for n in ancestors(parent, content)):
            continue
        text = clean(node.text())
        anchors = [n for n in node.walk() if n.tag == 'a']
        if not anchors:
            if re.fullmatch(r'[—–\-_\s]+', text or 'x'):
                context, section = {}, ''
            found = details(text)
            if found.get('title_id'):
                if found['title_id'] != context.get('title_id') or found.get('version'):
                    section = text
                context = {k: found[k] for k in ('title_id', 'region') if k in found}
            continue
        # Capture the row's label before its first anchor, not surrounding prose.
        before = []
        def prefix(n):
            for child in n.children:
                if isinstance(child, str):
                    before.append(child)
                elif child.tag == 'a':
                    return False
                elif not prefix(child):
                    return False
            return True
        prefix(node)
        label = clean(''.join(before)).strip(' :–—-')
        row = details(label)
        if not row.get('kind') or re.search(r'guide|dlc\s+content|changelog', label, re.I):
            continue
        links = [urllib.parse.urljoin(source_url, n.attrs.get('href', '')) for n in anchors]
        links = [url for url in links if downloadable(url)]
        file_data = [filename_details(url) for url in links]
        shared = {}
        # Mirrors in the same explicitly labelled row share unambiguous details.
        for field in ('version', 'firmware', 'variant', 'title_id'):
            values = {m[field] for m in file_data if field in m}
            if len(values) == 1:
                shared[field] = values.pop()
        for url, filename in zip(links, file_data):
            entry = dict(context, **shared)
            entry.update({k: v for k, v in filename.items() if k not in ('evidence', 'filename', 'kind')})
            entry.update(row)
            # Contradictory title IDs/versions must not produce a false label.
            for field in ('title_id', 'version'):
                if field in row and field in filename and row[field] != filename[field]:
                    entry.pop(field, None)
                    entry['conflict'] = True
            entry.update(url=url, evidence='Source page', source_label=label[:300], source_section=section[:200])
            if entry not in result:
                result.append(entry)
    return result


def ancestors(node, stop):
    while node and node is not stop:
        yield node
        node = node.parent


class SourceRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname != 'dlpsgame.com':
            raise ValueError('Source redirect left the approved source host')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_source(url):
    if urllib.parse.urlsplit(url).hostname != 'dlpsgame.com':
        raise ValueError('Unsupported source')
    req = urllib.request.Request(url, headers={'User-Agent': 'PS4CatalogueMetadata/1.0 (public page labels only)', 'Accept': 'text/html'})
    with urllib.request.build_opener(SourceRedirects()).open(req, timeout=25) as response:
        if response.headers.get_content_type() != 'text/html':
            raise ValueError('Not a source page')
        body = response.read(2000001)
        if len(body) > 2000000:
            raise ValueError('Page exceeds metadata size limit')
        body = body.decode('utf-8', errors='replace')
        if re.search(r'checking your browser|verify you are human|too many requests|site unavailable', body, re.I):
            raise ValueError('Source access restricted; stopping checks')
        return body


def write_manifest(manifest, output):
    output.mkdir(parents=True, exist_ok=True)
    data = json.dumps(manifest, ensure_ascii=True, separators=(',', ':'))
    (output / 'release-metadata.json').write_text(data + '\n')
    (output / 'release-metadata.js').write_text('var releaseMetadata = ' + data + ';\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--interval', type=float, default=3)
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'release-results')
    args = parser.parse_args()
    if not 1 <= args.limit <= 500 or args.interval < 3:
        parser.error('limit must be 1–500 and interval at least 3 seconds')
    source = ROOT / 'release-metadata.json'
    manifest = json.loads(source.read_text()) if source.exists() else {'schema_version': 1, 'pages': {}}
    rows = json.loads((ROOT / 'ps4_games_expanded.json').read_text())
    candidates = [r for r in rows if urllib.parse.urlsplit(r['page_url']).hostname == 'dlpsgame.com']
    priorities = ['LEGO 2K Drive Awesome Rivals Edition', '#KILLALLZOMBIES', '11 11 Memories Retold', '1971 Project Helios', '13 Sentinels Aegis Rim']
    candidates.sort(key=lambda r: (r['page_url'] in manifest['pages'], priorities.index(r['name']) if r['name'] in priorities else len(priorities), -len(r.get('download_links', {}).get('1file', []))))
    attempts = []
    for row in candidates[:args.limit]:
        url = row['page_url']
        try:
            entries = parse_source(fetch_source(url), url)
            if not entries:
                raise ValueError('No supported release rows; source layout needs review')
            manifest['pages'][url] = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'links': entries}
            attempt = {'source_url': url, 'name': row['name'], 'release_links': len(entries)}
            attempts.append(attempt)
            print(json.dumps(attempt), flush=True)
            write_manifest(manifest, args.output)
        except Exception as error:
            attempts.append({'source_url': url, 'error': type(error).__name__})
            print('Source check stopped: ' + type(error).__name__, flush=True)
            break
        time.sleep(args.interval)
    write_manifest(manifest, args.output)
    (args.output / 'report.json').write_text(json.dumps({'attempts': attempts, 'pages_with_metadata': len(manifest['pages'])}, indent=2) + '\n')


if __name__ == '__main__':
    main()
