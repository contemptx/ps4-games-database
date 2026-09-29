#!/usr/bin/env python3
"""Collect public IGDB evidence for a finite catalogue identity review."""
import json
import pathlib
import subprocess
from igdb_metadata import API, ROOT
from game_identities import FIELDS, PLATFORM_NAMES

def main():
    api = API()
    fields = FIELDS + ',parent_game,first_release_date,summary'
    cache_path = ROOT/'.identity-audit/reference.json'
    previous = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    platforms = previous.get('platforms') or api.all('platforms', 'name', 'id > 0')
    ids = [p['id'] for p in platforms if p['name'] in PLATFORM_NAMES]
    games = {g['id']:g for g in previous.get('games', [])}
    if not games:
        games = {g['id']:g for g in api.all('games', fields, 'platforms = (' + ','.join(map(str,ids)) + ')')}
    print('Collected', len(games), 'reference games', flush=True)
    entries = json.loads(subprocess.check_output(['node', str(ROOT/'scripts/identity_entries.cjs')],text=True))
    requests_path = ROOT/'identity-queries.json'
    requests = json.loads(requests_path.read_text()) if requests_path.exists() else {}
    searches = previous.get('searches', {})
    for index, title in enumerate(requests.get('search', [])):
        if title in searches: continue
        # JSON quoting is compatible with the API's quoted search string.
        rows = api.query('games', f'search {json.dumps(title)}; fields {fields}; limit 50;')
        searches[title] = [g['id'] for g in rows]
        games.update({g['id']:g for g in rows})
        if (index + 1) % 25 == 0: print('Searched', index + 1, 'titles', flush=True)
    missing = set(requests.get('ids', [])) | {e['igdb_id'] for e in entries if e.get('igdb_id')}
    for _ in range(8):
        missing |= {g[k] for g in games.values() for k in ('version_parent','parent_game') if g.get(k)}
        missing -= games.keys()
        if not missing: break
        count = len(games)
        ordered = sorted(missing)
        for start in range(0,len(ordered),100):
            selected = ','.join(map(str,ordered[start:start+100]))
            games.update({g['id']:g for g in api.query('games',f'fields {fields}; where id=({selected}); limit 500;')})
        if len(games) == count: break
        missing = set()
    out = ROOT/'.identity-audit'
    out.mkdir(exist_ok=True)
    (out/'reference.json').write_text(json.dumps({'platforms':platforms,'games':list(games.values()),'searches':searches},ensure_ascii=False))
    (out/'entries.json').write_text(json.dumps(entries,ensure_ascii=False))
    print('Evidence archive contains',len(games),'reference records for',len(entries),'listings',flush=True)

if __name__ == '__main__':
    main()
