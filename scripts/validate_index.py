#!/usr/bin/env python3
"""Validate generated data before an automated catalogue commit."""
import json
import pathlib
import urllib.parse
from full_index import ROOT

PAIRS = {'release-metadata': 'releaseMetadata', 'superpsx-catalog': 'superpsxCatalog',
         'additional-catalog': 'additionalCatalog', 'link-status': 'linkStatuses', 'index-progress': 'indexProgress'}


def validate(root=ROOT):
    data = {}
    for name, variable in PAIRS.items():
        raw = (root / (name + '.json')).read_text().rstrip()
        data[name] = json.loads(raw)
        if (root / (name + '.js')).read_text() != 'var ' + variable + ' = ' + raw + ';\n':
            raise ValueError('JSON/JavaScript pair mismatch: ' + name)
    for name in ('superpsx-catalog', 'additional-catalog'):
        seen = set()
        for r in data[name]['records']:
            identity = r.get('catalog_id') or r['page_url']
            if identity in seen or not isinstance(r['name'], str) or not r['name'].strip():
                raise ValueError('Duplicate or invalid source record')
            seen.add(identity)
            for entry in r['release_links']:
                check_entry(entry)
    for page in data['release-metadata']['pages'].values():
        for entry in page['links']:
            check_entry(entry)
    state = json.loads((root / 'index-state.json').read_text())
    for key, source in state['sources'].items():
        stats = data['index-progress']['sources'][key]
        if stats['total'] != len(source['items']) or stats['processed'] + stats['pending'] != stats['total']:
            raise ValueError('Coverage counts do not reconcile: ' + key)
    print('Manifest pairs, source identities, link schemes and coverage counts: PASS')


def check_entry(entry):
    p = urllib.parse.urlsplit(entry['url'])
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Invalid source link')
    if (p.hostname == 'filecrypt.cc' or p.hostname.endswith('.filecrypt.cc')):
        raise ValueError('Excluded host was reintroduced')
    if 'kind' in entry and entry['kind'] not in ('base', 'update', 'dlc', 'bundle', 'fix', 'patch'):
        raise ValueError('Unknown release kind')


if __name__ == '__main__':
    validate()
