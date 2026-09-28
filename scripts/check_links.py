#!/usr/bin/env python3
"""Inspect host landing pages, without downloading files or authenticating."""
import argparse
import collections
import datetime
import html.parser
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOSTS = ('1fichier.com', 'mediafire.com', 'filecrypt.cc', 'filecrypt.co')
MAX_BODY = 256 * 1024


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def host_family(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        return None
    return next((domain for domain in HOSTS if host == domain or host.endswith('.' + domain)), None)


def status_key(url):
    if url.startswith('//'):
        url = 'https:' + url
    if host_family(url) == '1fichier.com':
        match = re.match(r'([a-z0-9]+)', urllib.parse.urlsplit(url).query, re.I)
        if match:
            return 'https://1fichier.com/?' + match[1].lower()
    if host_family(url) == 'mediafire.com':
        match = re.match(r'/file/([a-z0-9]+)(?:/|$)', urllib.parse.urlsplit(url).path, re.I)
        if match:
            return 'https://www.mediafire.com/file/' + match[1]
    return url


class VisibleText(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def classify(url, code, body):
    parser = VisibleText()
    parser.feed(body)
    text = ' '.join(' '.join(parser.parts).lower().split())
    family = host_family(url)
    # Restrictions take priority, even if an error page includes other phrases.
    if code == 429 or '/429.html' in url or 'too many requests' in text:
        return 'rate_limited', 'Host requested fewer requests; file status unknown'
    if code in (401, 403) or any(term in text for term in (
        'professional infrastructure', 'premium status must not be used',
        'access restricted', 'accès restreint', 'use cdn credits',
        'captcha', 'verify you are human', 'checking your browser', 'access denied',
    )):
        return 'restricted', 'Access restriction or challenge; file status unknown'
    if 'site unavailable' in text or 'unable to access this site' in text:
        return 'unknown', 'Network or gateway could not access the host'
    if code not in (200, 404, 410):
        return 'unknown', 'HTTP %s alone does not confirm a deleted file' % code
    if family == '1fichier.com' and 'the requested file does not exist' in text:
        return 'missing', '1fichier explicitly reports that the requested file does not exist'
    if family == 'mediafire.com' and any(term in text for term in (
        'the file you requested has been deleted',
        'the file you requested does not exist',
    )):
        return 'missing', 'MediaFire explicitly reports a missing file'
    if code != 200:
        return 'unknown', 'HTTP %s alone does not confirm a deleted file' % code
    # A reachable Filecrypt container does not prove its underlying files exist.
    if family == 'mediafire.com' and re.search(r'id=["\']downloadButton["\']', body, re.I):
        return 'present', 'Host displays a file download page; file bytes were not verified'
    return 'unknown', 'No definitive file status found in the page'


class HostRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if host_family(newurl) != host_family(req.full_url):
            raise ValueError('Cross-host redirect was not followed')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def inspect(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'PS4CatalogueLinkChecker/1.0 (metadata only)',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en',
    })
    try:
        opener = urllib.request.build_opener(HostRedirects())
        try:
            response = opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            code = response.code
            content_type = response.headers.get_content_type()
            attachment = 'attachment' in response.headers.get('Content-Disposition', '').lower()
            if attachment or content_type not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                return {'status': 'unknown', 'reason': 'File response was closed without reading its contents', 'http_status': code}
            body = response.read(MAX_BODY).decode('utf-8', errors='replace')
            status, reason = classify(response.geturl(), code, body)
            return {'status': status, 'reason': reason, 'http_status': code}
    except Exception as error:
        # DNS, TLS, timeouts and network restrictions never mean "deleted".
        return {'status': 'unknown', 'reason': 'Network check failed: ' + type(error).__name__}


def candidates(rows):
    found = {}
    for row in rows:
        for group in ('mediafire', '1file', 'other'):
            values = (row.get('download_links') or {}).get(group, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, str):
                    continue
                url = status_key(value.strip())
                if host_family(url) and host_family(url) != 'filecrypt.cc':
                    found.setdefault(url, row.get('name', ''))
    return found


def merge_result(previous, result):
    # An inconclusive retry cannot undo evidence from a confirmed missing page.
    if previous.get('status') == 'missing' and result['status'] != 'present':
        return dict(previous, last_attempt=result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'link-check-results')
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or args.interval < 5:
        parser.error('limit must be 1–1000; interval must be at least 5 seconds')
    manifest = json.loads((ROOT / 'link-status.json').read_text())
    rows = json.loads((ROOT / 'ps4_games_expanded.json').read_text())
    release_path = ROOT / 'release-metadata.json'
    if release_path.exists():
        releases = json.loads(release_path.read_text()).get('pages', {})
        for row in rows:
            entries = releases.get(row.get('page_url'), {}).get('links', [])
            row.setdefault('download_links', {}).setdefault('other', []).extend(entry['url'] for entry in entries)
    superpsx_path = ROOT / 'superpsx-catalog.json'
    if superpsx_path.exists():
        rows.extend(json.loads(superpsx_path.read_text()).get('records', []))
    urls = candidates(rows)
    by_host = collections.defaultdict(list)
    for url, game in urls.items():
        by_host[host_family(url)].append((url, game))
    # Prefer unchecked/oldest records, so importing a report lets the next run resume.
    for queue in by_host.values():
        queue.sort(key=lambda pair: manifest['links'].get(pair[0], {}).get('checked_at', ''))
    blocked = set()
    attempts = []
    last_request = {}
    while len(attempts) < args.limit:
        advanced = False
        for host, queue in by_host.items():
            if host in blocked or not queue or len(attempts) >= args.limit:
                continue
            url, game = queue.pop(0)
            if manifest['links'].get(url, {}).get('status') == 'missing':
                advanced = True
                continue
            delay = args.interval - (time.monotonic() - last_request.get(host, 0))
            if delay > 0:
                time.sleep(delay)
            result = inspect(url)
            last_request[host] = time.monotonic()
            result.update(checked_at=now(), source='host page check', game=game)
            attempts.append(dict(url=url, **result))
            manifest['links'][url] = merge_result(manifest['links'].get(url, {}), result)
            print('%s: %s — %s' % (host, result['status'], result['reason']), flush=True)
            if result['status'] in ('rate_limited', 'restricted') or (
                result['status'] == 'unknown' and result['reason'] != 'No definitive file status found in the page'
            ):
                blocked.add(host)
            advanced = True
        if not advanced:
            break
    manifest['updated_at'] = now()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'link-status.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.output / 'link-status.js').write_text('var linkStatuses = ' + json.dumps(manifest, ensure_ascii=True) + ';\n')
    summary = {'attempted': len(attempts), 'results': dict(collections.Counter(item['status'] for item in attempts)),
               'hosts_stopped': sorted(blocked), 'supported_unique_links': len(urls),
               'note': 'Unattempted links remain unchecked. Present means a file page was seen, not a verified download.'}
    (args.output / 'report.json').write_text(json.dumps({'summary': summary, 'attempts': attempts}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
