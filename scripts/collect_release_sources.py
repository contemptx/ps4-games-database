#!/usr/bin/env python3
"""Collect a small sample of public source-page HTML for release-parser review."""
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'release-source-pages'
SAMPLES = ['LEGO 2K Drive Awesome Rivals Edition', '#KILLALLZOMBIES', 'Aca Neo Geo Big Tournament Golf']
OUT.mkdir(exist_ok=True)
rows = json.loads((ROOT / 'ps4_games_expanded.json').read_text())
report = []
for index, name in enumerate(SAMPLES):
    row = next(row for row in rows if row['name'] == name)
    url = row['page_url']
    entry = {'name': name, 'source_url': url}
    request = urllib.request.Request(url, headers={'User-Agent': 'PS4CatalogueMetadata/1.0 (public page labels only)', 'Accept': 'text/html'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            entry['http_status'] = response.status
            if response.headers.get_content_type() != 'text/html':
                raise ValueError('Not an HTML source page')
            body = response.read(2000000)
            filename = str(index) + '.html'
            (OUT / filename).write_bytes(body)
            entry.update(filename=filename, bytes=len(body))
    except Exception as error:
        entry['error'] = type(error).__name__
    report.append(entry)
    print(json.dumps(entry), flush=True)
    time.sleep(5)
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
