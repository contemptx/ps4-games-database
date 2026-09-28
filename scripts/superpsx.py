#!/usr/bin/env python3
"""Index public SuperPSX PS4 articles and their explicitly linked download tables."""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from release_metadata import Tree, clean, details, downloadable, is_access_error
from check_links import status_key

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = 'https://www.superpsx.com/'
UA = 'PS4CatalogueMetadata/1.0 (public page labels only)'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_url(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in ('www.superpsx.com', 'superpsx.com') and not p.username and not p.password


def article(body, url):
    root = Tree(body).root
    content = next((n for n in root.walk() if 'entry-content' in n.attrs.get('class', '').split()), None)
    title = next((clean(n.text()) for n in root.walk() if n.tag == 'h1'), '')
    if content is None or not re.search(r'\bPS4\b', title, re.I):
        return None
    # A title and explicit download-page link are required; navigation links don't count.
    pages = []
    for n in content.walk():
        if n.tag != 'a':
            continue
        target = urllib.parse.urljoin(url, n.attrs.get('href', ''))
        if source_url(target) and re.match(r'/dll-[^/]+/?$', urllib.parse.urlsplit(target).path):
            if target not in pages:
                pages.append(target)
    if not pages:
        return None
    return {'name': title, 'page_url': url, 'source': 'SuperPSX', 'download_pages': pages}


def parse_downloads(body, url):
    root = Tree(body).root
    content = next((n for n in root.walk() if 'entry-content' in n.attrs.get('class', '').split()), None)
    if content is None:
        return []
    result, pending_edition = [], ''
    for table in (n for n in content.walk() if n.tag == 'table'):
        context, section, edition = {}, '', pending_edition
        pending_edition = ''
        for row in (n for n in table.walk() if n.tag == 'tr'):
            cells = [n for n in row.children if not isinstance(n, str) and n.tag in ('td', 'th')]
            if len(cells) == 1:
                heading = clean(cells[0].text())
                if re.search(r'\bCUSA\d{5}\b', heading, re.I):
                    edition = heading[:250]
                    pending_edition = edition
                    context, section = {}, ''
                continue
            if len(cells) < 2:
                continue
            pending_edition = ''
            label = clean(cells[0].text()).strip(' ⇛:–—-')
            text = clean(' '.join(c.text() for c in cells[1:]))
            if re.match(r'^version\b', label, re.I):
                found = details(text)
                if edition and details(edition).get('title_id') != found.get('title_id'):
                    edition = ''
                # Reset at every edition header, even if its identifier is unknown.
                context = {k: found[k] for k in ('title_id', 'region') if k in found}
                section = clean((edition + ' · ' if edition and edition != text else '') + text)[:450]
                continue
            meta = details(label)
            # SuperPSX also writes firmware ranges in square brackets.
            firmware = details(label, filename=True).get('firmware')
            if firmware:
                meta['firmware'] = firmware
            # Named language/mod patches are not game-version updates.
            if meta.get('kind') == 'update' and re.search(r'\bpatch\b', label, re.I) and not re.match(r'^(?:update|patch)\b', label, re.I):
                meta['kind'] = 'patch'
            integer_version = re.search(r'\bv(\d+)(?![\d.])\b', label, re.I)
            if not meta.get('version') and integer_version:
                meta['version'] = integer_version[1]
            if edition:
                meta['edition'] = edition
            if not meta.get('kind') or re.search(r'guide|changelog|content list', label, re.I):
                continue
            for cell in cells[1:]:
                for anchor in (n for n in cell.walk() if n.tag == 'a'):
                    target = urllib.parse.urljoin(url, anchor.attrs.get('href', ''))
                    if not downloadable(target):
                        continue
                    entry = dict(context, **meta, url=target, evidence='Source page', source_label=label[:300], source_section=section, source_url=url)
                    if entry not in result:
                        result.append(entry)
    return result


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed):
        self.allowed = allowed
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not source_url(newurl) or not self.allowed(newurl):
            raise ValueError('Redirect outside permitted source pages')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Reader:
    def __init__(self, interval, cache):
        self.interval, self.cache, self.last = interval, cache, 0
        self.robots = None
        self.cache.mkdir(parents=True, exist_ok=True)
    def allowed(self, url):
        return source_url(url) and (self.robots is None or self.robots.can_fetch(UA, url))
    def get(self, url):
        if not self.allowed(url):
            raise ValueError('Source robots rules exclude this URL')
        dest = self.cache / (hashlib.sha256(url.encode()).hexdigest() + '.txt')
        if dest.exists():
            return dest.read_text()
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html, application/xml, text/plain'})
        try:
            with urllib.request.build_opener(Redirects(self.allowed)).open(request, timeout=25) as response:
                if response.headers.get_content_type() not in ('text/html', 'application/xml', 'text/xml', 'text/plain'):
                    raise ValueError('Unexpected source content type')
                body = response.read(3000001)
                if len(body) > 3000000:
                    raise ValueError('Source exceeds metadata size limit')
                body = body.decode('utf-8', errors='replace')
                if '<html' in body.lower() and is_access_error(body):
                    raise ValueError('Source access restricted; stopping')
                dest.write_text(body)
                return body
        finally:
            self.last = time.monotonic()
    def start(self):
        rules = self.get(SITE + 'robots.txt')
        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.parse(rules.splitlines())
        self.interval = max(self.interval, self.robots.crawl_delay(UA) or 0)


def discover(reader):
    index = ET.fromstring(reader.get(SITE + 'sitemap_index.xml'))
    candidates = {}
    for node in index.findall('s:sitemap', NS):
        url = node.findtext('s:loc', '', NS)
        if not source_url(url) or not re.fullmatch(r'/post-sitemap\d*\.xml', urllib.parse.urlsplit(url).path):
            continue
        sitemap = ET.fromstring(reader.get(url))
        for item in sitemap.findall('s:url', NS):
            url = item.findtext('s:loc', '', NS)
            # Images supply PS4 hints for opaque article slugs; articles are verified later.
            hints = ' '.join(item.itertext())
            if source_url(url) and re.search('ps4', hints, re.I):
                candidates[url] = item.findtext('s:lastmod', '', NS)
    return candidates


def save(manifest, output):
    output.mkdir(parents=True, exist_ok=True)
    manifest['updated_at'] = now()
    raw = json.dumps(manifest, ensure_ascii=True, separators=(',', ':'))
    for name, text in [('superpsx-catalog.json', raw + '\n'), ('superpsx-catalog.js', 'var superpsxCatalog = ' + raw + ';\n')]:
        temporary = output / (name + '.tmp')
        temporary.write_text(text)
        temporary.replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'superpsx-results')
    parser.add_argument('--cache', type=pathlib.Path, default=ROOT / '.superpsx-cache')
    args = parser.parse_args()
    if not 1 <= args.limit <= 500 or args.interval < 2:
        parser.error('limit must be 1–500 and interval at least 2 seconds')
    previous = args.output / 'superpsx-catalog.json'
    if not previous.exists():
        previous = ROOT / 'superpsx-catalog.json'
    manifest = json.loads(previous.read_text()) if previous.exists() else {'source': 'SuperPSX', 'records': [], 'checked': {}}
    records = {r['page_url']: r for r in manifest['records']}
    reader = Reader(args.interval, args.cache)
    report = {'started_at': now(), 'attempts': [], 'stopped': None}
    try:
        reader.start()
        candidates = discover(reader)
        manifest['discovered_candidates'] = len(candidates)
        # Unchecked articles first, newest first; imported results resume subsequent runs.
        ordered = sorted(candidates, key=lambda u: candidates[u], reverse=True)
        ordered.sort(key=lambda u: manifest['checked'].get(u, {}).get('checked_at', ''))
        for url in ordered[:args.limit]:
            print('Reading ' + url, flush=True)
            try:
                record = article(reader.get(url), url)
                if record:
                    links = []
                    for page in record['download_pages']:
                        links.extend(parse_downloads(reader.get(page), page))
                    record['release_links'] = links
                    record['download_links'] = {'other': list(dict.fromkeys(e['url'] for e in links))}
                    record['checked_at'] = now()
                    if links:
                        records[url] = record
                    else:
                        records.pop(url, None)
                else:
                    records.pop(url, None)
                status = {'checked_at': now(), 'links': len(record['release_links']) if record else 0}
                manifest['checked'][url] = status
                report['attempts'].append(dict(url=url, **status))
            except urllib.error.HTTPError as error:
                if error.code not in (404, 410):
                    raise
                status = {'checked_at': now(), 'http_status': error.code, 'links': 0}
                manifest['checked'][url] = status
                records.pop(url, None)
                report['attempts'].append(dict(url=url, **status))
            manifest['records'] = sorted(records.values(), key=lambda r: r['name'].lower())
            save(manifest, args.output)
    except (ValueError, urllib.error.URLError, TimeoutError, ET.ParseError, KeyboardInterrupt) as error:
        report['stopped'] = str(error) or 'Interrupted; completed articles were saved'
        print('Stopped: ' + str(error), flush=True)
    manifest['records'] = sorted(records.values(), key=lambda r: r['name'].lower())
    save(manifest, args.output)
    report.update(finished_at=now(), attempted=len(report['attempts']), listings=len(records),
                  links=sum(len(r['download_links']['other']) for r in records.values()),
                  checked_articles=len(manifest['checked']), discovered_candidates=manifest.get('discovered_candidates', 0),
                  note='Public source labels only. File availability is unverified. Candidate discovery uses PS4 hints in post sitemaps; coverage is partial.')
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'attempts'}, indent=2))
    if report['stopped']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
