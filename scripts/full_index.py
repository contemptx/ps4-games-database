#!/usr/bin/env python3
"""Finite, checkpointed pass across the catalogue's public source pages."""
import argparse
import collections
import concurrent.futures
import copy
import datetime
import hashlib
import json
import os
import pathlib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from release_metadata import Tree, clean, details, downloadable, expand_labels, is_access_error, parse_source, filename_details, download_url
from superpsx import article, parse_downloads, discover
from check_links import candidates as check_candidates, host_family, inspect, merge_result, status_key

ROOT = pathlib.Path(__file__).resolve().parents[1]
UA = 'PS4CatalogueMetadata/1.0 (public page labels only)'
FILES = ['release-metadata.json', 'release-metadata.js', 'superpsx-catalog.json', 'superpsx-catalog.js',
         'additional-catalog.json', 'additional-catalog.js', 'link-status.json', 'link-status.js',
         'index-state.json', 'index-progress.json', 'index-progress.js', 'source-review.json']
LABELS = {'dlps': 'DLPSGame', 'superpsx': 'SuperPSX', 'arabic': 'ArabicPS4Games', 'romsfun': 'RomsFun', 'linklists': 'Public link lists', 'mediafire': 'MediaFire checks'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(content)
    temporary.replace(path)


def write_pair(root, name, data, variable):
    raw = json.dumps(data, ensure_ascii=True, separators=(',', ':'))
    atomic(root / (name + '.json'), raw + '\n')
    atomic(root / (name + '.js'), 'var ' + variable + ' = ' + raw + ';\n')


class Held(Exception):
    pass


class Missing(Exception):
    pass


class PageError(Exception):
    pass


class Reader:
    """One serial reader per origin; no cookies, auth, binary bodies or off-site redirects."""
    def __init__(self, site, interval=3):
        self.site = site
        self.host = urllib.parse.urlsplit(site).hostname.removeprefix('www.')
        self.interval, self.last, self.robot = interval, 0, None
        owner = self
        class Redirects(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not owner.allowed(newurl):
                    raise PageError('Redirect left the permitted source pages')
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        self.opener = urllib.request.build_opener(Redirects())
        self.cache = {}
    def allowed(self, url):
        p = urllib.parse.urlsplit(url)
        return (p.scheme == 'https' and not p.username and not p.password and
                (p.hostname or '').removeprefix('www.') == self.host and
                (self.robot is None or self.robot.can_fetch(UA, url)))
    def start(self):
        try:
            rules = self.get(self.site + 'robots.txt')
        except Missing:
            rules = ''
        self.robot = urllib.robotparser.RobotFileParser()
        self.robot.parse(rules.splitlines())
        self.interval = max(self.interval, self.robot.crawl_delay(UA) or 0)
    def get(self, url):
        if not self.allowed(url):
            raise PageError('Robots rules or source boundary exclude this URL')
        if url in self.cache:
            return self.cache[url]
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html, application/xml, text/plain'})
        try:
            with self.opener.open(req, timeout=25) as response:
                if ('attachment' in response.headers.get('Content-Disposition', '').lower() or
                        response.headers.get_content_type() not in ('text/html', 'text/plain', 'application/xml', 'text/xml', 'application/xhtml+xml')):
                    raise PageError('Non-metadata response closed without reading file contents')
                body = response.read(8000001)
                if len(body) > 8000000:
                    raise PageError('Source exceeds the 8 MB metadata limit')
                body = body.decode('utf-8', errors='replace')
                if '<html' in body.lower() and is_access_error(body):
                    raise Held('Access challenge or unavailable source')
                # Small per-run cache for shared download tables and sitemap discovery.
                if len(self.cache) < 500:
                    self.cache[url] = body
                return body
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                raise Missing('HTTP ' + str(error.code)) from error
            if error.code in (401, 403, 429):
                raise Held('HTTP ' + str(error.code) + '; source paused') from error
            raise Held('HTTP ' + str(error.code) + '; source needs retry review') from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise Held('Network failure: ' + type(error).__name__) from error
        finally:
            self.last = time.monotonic()


def content_node(body):
    root = Tree(expand_labels(body)).root
    return root, next((n for n in root.walk() if 'entry-content' in n.attrs.get('class', '').split() or n.attrs.get('id') == 'articleContent'), None)


def supplement(body, url, entries):
    """Retain recognised download hosts even when a release label cannot be parsed."""
    _, content = content_node(body)
    if content is None:
        return entries
    known = {status_key(e['url']) for e in entries}
    for n in content.walk():
        if n.tag != 'a':
            continue
        target = download_url(url, n.attrs.get('href', ''))
        if downloadable(target) and status_key(target) not in known:
            known.add(status_key(target))
            entry = {'url': target, 'evidence': 'Source page', 'source_url': url,
                     'source_label': clean(n.text())[:200], 'unlabelled': True}
            entry.update(filename_details(target))
            entries.append(entry)
    return entries


def arabic_figures(body, url):
    result = []
    root = Tree(body).root
    for figure in (n for n in root.walk() if n.tag == 'figure' or 'inside-page__container' in n.attrs.get('class', '').split()):
        title = next((clean(n.text()) for n in figure.walk() if n.tag == 'h2' and clean(n.text())), '')
        if not title and 'inside-page__container' in figure.attrs.get('class', '').split():
            title = next((clean(n.text()) for n in figure.walk() if n.tag == 'font' and n.attrs.get('color') == 'white' and clean(n.text())), '')
        if not title:
            continue
        links = []
        for node in figure.walk():
            if node.tag == 'a':
                target = urllib.parse.urljoin(url, node.attrs.get('href', ''))
                p = urllib.parse.urlsplit(target)
                if p.scheme in ('http', 'https') and p.hostname and not p.username and not p.password and target not in links:
                    links.append(target)
        if links:
            result.append({'name': title, 'page_url': url, 'links': links})
    return result


def initial_state(rows, releases, super_manifest, link_status):
    state = {'schema_version': 1, 'started_at': now(), 'batch': 0, 'sources': {}}
    for key in LABELS:
        state['sources'][key] = {'label': LABELS[key], 'items': {}, 'held': None}
    for row in rows:
        url = row.get('page_url', '')
        host = urllib.parse.urlsplit(url).hostname
        key = {'dlpsgame.com': 'dlps', 'romsfun.com': 'romsfun'}.get(host)
        if key:
            previous = releases.get('pages', {}).get(url)
            state['sources'][key]['items'][url] = {'name': row['name'], 'status': 'labelled' if previous else 'pending',
                                                 'checked_at': previous.get('checked_at') if previous else None,
                                                 'links': len(previous.get('links', [])) if previous else 0}
        if host == 'arabicps4games.github.io' and re.fullmatch(r'/indexps4page\d+\.html', urllib.parse.urlsplit(url).path):
            state['sources']['arabic']['items'][url] = {'status': 'pending'}
    state['sources']['arabic']['items']['https://arabicps4games.github.io/indexallps4.html'] = {'status': 'pending', 'priority': 0}
    # Public access was tested before enabling the full run; do not rotate runners to bypass denial.
    state['sources']['romsfun']['held'] = {'at': now(), 'reason': 'Public game and download pages returned HTTP 403 during source audit.'}
    state['availability_holds'] = {'1fichier.com': 'Existing public checks returned access restrictions; file status remains unknown.',
                                  'filecrypt.cc': 'Excluded by catalogue preference.',
                                  'filecrypt.co': 'Container visibility does not confirm the underlying files.'}
    return state


def source_counts(source):
    counts = collections.Counter(v.get('status', 'pending') for v in source['items'].values())
    return {'total': len(source['items']), 'processed': len(source['items']) - counts['pending'],
            'pending': counts['pending'], 'labelled': counts['labelled'],
            'review': counts['review'] + counts['error'], 'no_links': counts['no_links'] + counts['not_ps4'],
            'source_missing': counts['source_missing'], 'statuses': dict(counts), 'held': source.get('held')}


def runnable_count(state):
    return sum(source_counts(s)['pending'] for s in state['sources'].values() if not s.get('held'))


class Indexer:
    def __init__(self, root=ROOT, limit=100, minutes=20):
        self.root, self.limit = root, limit
        self.deadline = time.monotonic() + minutes * 60
        self.rows = load(root / 'ps4_games_expanded.json', [])
        self.releases = load(root / 'release-metadata.json', {'pages': {}})
        self.super = load(root / 'superpsx-catalog.json', {'records': [], 'checked': {}})
        self.additional = load(root / 'additional-catalog.json', {'records': []})
        self.statuses = load(root / 'link-status.json', {'version': 1, 'links': {}})
        self.review = load(root / 'source-review.json', {'games': {}, 'note': 'Unresolved source destinations are not confirmed downloads.'})
        self.state = load(root / 'index-state.json', initial_state(self.rows, self.releases, self.super, self.statuses))
        self.lock = threading.RLock()
        self.attempts = collections.Counter()
        self.base_rows = copy.deepcopy(self.rows) + copy.deepcopy(self.super['records']) + copy.deepcopy(self.additional['records'])
        for row in self.base_rows:
            links = self.releases['pages'].get(row.get('page_url'), {}).get('links', [])
            row.setdefault('download_links', {}).setdefault('other', []).extend(e['url'] for e in links)
        self.enqueue_checks(self.base_rows)
    def enqueue_checks(self, rows):
        for url, name in check_candidates(rows).items():
            if host_family(url) == 'mediafire.com':
                old = self.statuses['links'].get(url)
                self.state['sources']['mediafire']['items'].setdefault(url, {'name': name, 'status': 'checked' if old else 'pending'})
    def checkpoint(self):
        with self.lock:
            atomic(self.root / 'index-state.json', json.dumps(self.state, ensure_ascii=True, separators=(',', ':')) + '\n')
    def pending(self, key):
        items = self.state['sources'][key]['items']
        return [u for u in sorted(items, key=lambda u: (items[u].get('priority', 1), u)) if items[u].get('status') == 'pending'][:self.limit]
    def persist_source(self, key):
        if key == 'dlps':
            write_pair(self.root, 'release-metadata', self.releases, 'releaseMetadata')
        elif key == 'superpsx':
            write_pair(self.root, 'superpsx-catalog', self.super, 'superpsxCatalog')
        elif key in ('arabic', 'linklists'):
            write_pair(self.root, 'additional-catalog', self.additional, 'additionalCatalog')
            atomic(self.root / 'source-review.json', json.dumps(self.review, ensure_ascii=True, separators=(',', ':')) + '\n')
        elif key == 'mediafire':
            write_pair(self.root, 'link-status', self.statuses, 'linkStatuses')
    def mark(self, key, url, status, **extra):
        with self.lock:
            # Publish data to disk before acknowledging its source item in the checkpoint.
            self.persist_source(key)
            self.state['sources'][key]['items'][url].update(status=status, checked_at=now(), **extra)
            self.attempts[key] += 1
            print(json.dumps({'source': key, 'url': url, 'status': status, **extra}), flush=True)
            self.checkpoint()
    def hold(self, key, reason):
        with self.lock:
            self.persist_source(key)
            self.state['sources'][key]['held'] = {'at': now(), 'reason': reason}
            self.checkpoint()
        print(json.dumps({'source': key, 'held': reason}), flush=True)
    def process(self, key):
        if self.state['sources'][key].get('held'):
            return
        if key != 'superpsx' and not self.pending(key):
            return
        try:
            if key == 'mediafire':
                return self.check_mediafire()
            sites = {'dlps': 'https://dlpsgame.com/', 'superpsx': 'https://www.superpsx.com/', 'arabic': 'https://arabicps4games.github.io/', 'linklists': 'https://justpaste.it/'}
            reader = Reader(sites[key], 3 if key == 'dlps' else 2)
            reader.start()
            if key == 'superpsx' and not self.state['sources'][key].get('discovered_at'):
                # Inspect every post, including opaque slugs; PS4 identity is checked in the article.
                found = discover(reader, all_posts=True)
                items = dict(self.state['sources'][key]['items'])
                existing = {r['page_url']: r for r in self.super['records']}
                for url, modified in found.items():
                    old = self.super['checked'].get(url)
                    record = existing.get(url)
                    items.setdefault(url, {'status': ('labelled' if record else 'no_links') if old else 'pending',
                                          'checked_at': old.get('checked_at') if old else None,
                                          'name': record['name'] if record else '', 'links': len(record['release_links']) if record else 0,
                                          'priority': 0 if 'ps4' in url.lower() else 1})
                with self.lock:
                    self.state['sources'][key]['items'] = items
                    self.state['sources'][key]['discovered_at'] = now()
                    self.super['discovered_candidates'] = len(found)
                    self.checkpoint()
            for url in self.pending(key):
                if time.monotonic() >= self.deadline:
                    break
                try:
                    body = reader.get(url)
                    if key == 'dlps':
                        entries = supplement(body, url, parse_source(body, url))
                        if entries:
                            self.releases['pages'][url] = {'checked_at': now(), 'links': entries}
                        labelled = sum(bool(e.get('kind')) for e in entries)
                        status = 'labelled' if labelled else ('review' if entries else 'no_links')
                        self.mark(key, url, status, links=len(entries), unlabelled=sum(not e.get('kind') for e in entries))
                    elif key == 'superpsx':
                        self.process_super(body, url, reader)
                    elif key == 'arabic':
                        self.process_arabic(body, url)
                    elif key == 'linklists':
                        self.process_linklist(body, url)
                except Missing as error:
                    self.mark(key, url, 'source_missing', reason=str(error))
                except PageError as error:
                    self.mark(key, url, 'review', reason=str(error))
                except Held:
                    raise
                except (ValueError, KeyError, RecursionError) as error:
                    self.mark(key, url, 'error', reason=type(error).__name__ + ': ' + str(error)[:180])
        except Exception as error:
            self.hold(key, type(error).__name__ + ': ' + str(error)[:240])
    def process_super(self, body, url, reader):
        record = article(body, url)
        root, content = content_node(body)
        if not record:
            title = next((clean(n.text()) for n in root.walk() if n.tag == 'h1'), '')
            if not re.search(r'\bPS4\b', title, re.I):
                return self.mark('superpsx', url, 'not_ps4')
            record = {'name': title, 'page_url': url, 'source': 'SuperPSX', 'download_pages': []}
        entries, source_errors = [], []
        for page in record['download_pages']:
            try:
                table = reader.get(page)
                entries.extend(supplement(table, page, parse_downloads(table, page)))
            except Missing as error:
                source_errors.append({'url': page, 'reason': str(error)})
        entries.extend(supplement(body, url, []))
        record.update(release_links=entries, download_links={'other': list(dict.fromkeys(e['url'] for e in entries))}, checked_at=now())
        records = {r['page_url']: r for r in self.super['records']}
        if entries:
            records[url] = record
        self.super['records'] = list(records.values())
        self.super['checked'][url] = {'checked_at': now(), 'links': len(entries)}
        self.mark('superpsx', url, 'labelled' if any(e.get('kind') for e in entries) and not source_errors else 'review',
                  name=record['name'], links=len(entries), source_errors=source_errors, unlabelled=sum(not e.get('kind') for e in entries))
    def process_arabic(self, body, url):
        figures = arabic_figures(body, url)
        new_records = {}
        direct = 0
        for figure in figures:
            identity = 'arabic-' + hashlib.sha256((figure['name'].casefold() + '|' + '|'.join(sorted(figure['links']))).encode()).hexdigest()[:20]
            entries = [{'url': u, 'evidence': 'Source page', 'unlabelled': True} for u in figure['links'] if downloadable(u)]
            unresolved = [u for u in figure['links'] if not downloadable(u)]
            with self.lock:
                old = self.review['games'].get(identity, {})
            for target in unresolved:
                if urllib.parse.urlsplit(target).hostname == 'justpaste.it' and re.fullmatch(r'/[a-zA-Z0-9]+', urllib.parse.urlsplit(target).path):
                    with self.lock:
                        self.state['sources']['linklists']['items'].setdefault(target, {'status': 'pending', 'name': figure['name'], 'source_page': url})
            if unresolved:
                with self.lock:
                    self.review['games'][identity] = {'name': figure['name'], 'page_url': url,
                        'links': list(dict.fromkeys(old.get('links', []) + unresolved)), 'status': old.get('status', 'unresolved_redirect_or_link_list')}
            if entries:
                direct += len(entries)
                new_records[identity] = {'catalog_id': identity, 'name': figure['name'], 'page_url': url, 'release_links': entries,
                                     'download_links': {'other': [e['url'] for e in entries]}}
        with self.lock:
            records = {r['catalog_id']: r for r in self.additional['records']}
            records.update(new_records)
            self.additional['records'] = list(records.values())
        self.mark('arabic', url, 'review' if figures else 'no_links', named_games=len(figures), links=direct)
    def process_linklist(self, body, url):
        item = self.state['sources']['linklists']['items'][url]
        entries = supplement(body, url, parse_source(body, url))
        if entries:
            identity = 'linklist-' + hashlib.sha256(url.encode()).hexdigest()[:20]
            record = {'catalog_id': identity, 'name': item['name'], 'page_url': url, 'source': 'ArabicPS4Games',
                      'discovered_from': item.get('source_page'), 'release_links': entries,
                      'download_links': {'other': list(dict.fromkeys(e['url'] for e in entries))}}
            with self.lock:
                records = {r['catalog_id']: r for r in self.additional['records']}
                records[identity] = record
                self.additional['records'] = list(records.values())
                for game in self.review['games'].values():
                    if url in game['links']:
                        game['status'] = 'link_list_parsed_other_destinations_may_be_unresolved'
        self.mark('linklists', url, 'labelled' if any(e.get('kind') for e in entries) else 'review', links=len(entries))

    def check_mediafire(self):
        for url in self.pending('mediafire'):
            if time.monotonic() >= self.deadline:
                break
            result = inspect(url)
            result.update(checked_at=now(), source='host page check', game=self.state['sources']['mediafire']['items'][url].get('name', ''))
            self.statuses['links'][url] = merge_result(self.statuses['links'].get(url, {}), result)
            if result['status'] in ('restricted', 'rate_limited') or (result['status'] == 'unknown' and result['reason'].startswith('Network')):
                self.hold('mediafire', result['reason'])
                break
            self.mark('mediafire', url, 'checked', result=result['status'])
            time.sleep(5)
    def save(self):
        current_rows = copy.deepcopy(self.rows) + copy.deepcopy(self.super['records']) + copy.deepcopy(self.additional['records'])
        for row in current_rows:
            links = self.releases['pages'].get(row.get('page_url'), {}).get('links', [])
            row.setdefault('download_links', {}).setdefault('other', []).extend(e['url'] for e in links)
        self.enqueue_checks(current_rows)
        self.state['batch'] += 1
        self.state['updated_at'] = now()
        self.state['last_batch_attempts'] = dict(self.attempts)
        self.state['runnable_remaining'] = runnable_count(self.state)
        self.state['run_url'] = ('https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']) if os.environ.get('GITHUB_RUN_ID') else None
        self.super['records'].sort(key=lambda r: r['name'].casefold())
        self.super['updated_at'] = self.additional['updated_at'] = self.statuses['updated_at'] = now()
        write_pair(self.root, 'release-metadata', self.releases, 'releaseMetadata')
        write_pair(self.root, 'superpsx-catalog', self.super, 'superpsxCatalog')
        write_pair(self.root, 'additional-catalog', self.additional, 'additionalCatalog')
        write_pair(self.root, 'link-status', self.statuses, 'linkStatuses')
        atomic(self.root / 'source-review.json', json.dumps(self.review, ensure_ascii=True, separators=(',', ':')) + '\n')
        self.checkpoint()
        summary = {'updated_at': now(), 'batch': self.state['batch'], 'run_url': self.state['run_url'],
                   'sources': {k: dict(label=s['label'], **source_counts(s)) for k, s in self.state['sources'].items()},
                   'unresolved_named_games': sum(g['status'] == 'unresolved_redirect_or_link_list' for g in self.review['games'].values()), 'availability_holds': self.state.get('availability_holds', {}),
                   'runnable_remaining': self.state['runnable_remaining'], 'last_batch_attempts': dict(self.attempts),
                   'note': 'Processed means a source page was inspected, not that every label or file is verified. Held sources and unresolved redirects remain incomplete.'}
        write_pair(self.root, 'index-progress', summary, 'indexProgress')
        can_continue = self.state['runnable_remaining'] > 0 and sum(self.attempts.values()) > 0
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write('continue=' + str(can_continue).lower() + '\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
                f.write('# Catalogue indexing progress\n\n| Source | Processed | Queue | Needs review | State |\n|---|---:|---:|---:|---|\n')
                for s in summary['sources'].values():
                    f.write('| %s | %s | %s | %s | %s |\n' % (s['label'], s['processed'], s['total'], s['review'], s['held']['reason'] if s['held'] else ('Running' if s['pending'] else 'Pass finished')))
                f.write('\nUnresolved named games: %s. Pending runnable work: %s.\n' % (summary['unresolved_named_games'], summary['runnable_remaining']))
        print(json.dumps(summary, indent=2), flush=True)
        return summary
    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.process, key) for key in ('dlps', 'superpsx', 'arabic', 'linklists', 'mediafire')]
            for future in futures:
                future.result()
        return self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--minutes', type=int, default=20)
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    args = parser.parse_args()
    if not 1 <= args.limit <= 250 or not 1 <= args.minutes <= 30:
        parser.error('limit must be 1–250; minutes must be 1–30')
    Indexer(args.root, args.limit, args.minutes).run()


if __name__ == '__main__':
    main()
