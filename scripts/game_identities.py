#!/usr/bin/env python3
"""Resolve visible catalogue titles to IGDB identities without merging scraped CUSA collisions."""
import collections
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import subprocess
import unicodedata
from igdb_metadata import API, ROOT

FIELDS = 'name,url,alternative_names.name,platforms,game_type.type,version_parent,version_title'
ROMAN = dict(zip(['ii','iii','iv','vi','vii','viii','ix','xi','xii','xiii'],
                 ['2','3','4','6','7','8','9','11','12','13']))
GAME_TYPES = {'main_game', 'standalone_expansion', 'episode', 'season', 'remake', 'remaster', 'expanded_game', 'port', 'fork'}
NON_GAME_TYPES = {'dlc_addon', 'expansion', 'bundle', 'mod', 'pack', 'update'}


def normalize(value, relaxed=False):
    value = html.unescape(value).casefold()
    value = re.sub(r'\s+(?:ps4|fpkg|pkg)(?:\s+(?:ps4|fpkg|pkg|download))*\s*$', '', value)
    value = value.replace('&', ' and ')
    value = re.sub(r"['’‘`\u200b\ufeff]", '', value)
    value = ''.join(ch for ch in unicodedata.normalize('NFKD', value) if not unicodedata.combining(ch))
    words = re.sub(r'[^\w]+', ' ', value).strip().split()
    if relaxed:
        words = [ROMAN.get(w, w) for w in words]
        return ''.join(words)
    return ' '.join(words)


def root_id(game_id, games):
    seen = set()
    while game_id in games and games[game_id].get('version_parent'):
        if game_id in seen:
            return None
        seen.add(game_id)
        game_id = games[game_id]['version_parent']
    return game_id if game_id in games else None


def game_type(game):
    value = game.get('game_type') or {}
    value = value.get('type', '') if isinstance(value, dict) else ''
    return re.sub(r'[^a-z0-9]+', '_', value.casefold()).strip('_')


def build_indexes(games):
    indexes = [collections.defaultdict(set), collections.defaultdict(set)]
    for game in games.values():
        for name in [game['name']] + [a['name'] for a in game.get('alternative_names', [])]:
            for relaxed in (False, True):
                indexes[int(relaxed)][normalize(name, relaxed)].add(game['id'])
    return indexes


def choose_match(entry, games, indexes):
    if entry.get('igdb_id') in games:
        return entry['igdb_id'], 'Existing unique PS4 title/alias match', []
    candidates = set()
    names = [entry['name']] + entry.get('aliases', [])
    for relaxed in (False, True):
        candidates = set().union(*(indexes[int(relaxed)].get(normalize(n, relaxed), set()) for n in names))
        if not candidates:
            continue
        roots = {root_id(i, games) for i in candidates}
        if len(roots) == 1 and None not in roots:
            chosen = min(candidates, key=lambda i: (i not in roots, i))
            return chosen, 'Unique normalized IGDB title/alias' + (' (spacing/numerals)' if relaxed else ''), []
        ps4 = {i for i in candidates if 48 in games[i].get('platforms', [])}
        roots = {root_id(i, games) for i in ps4}
        if entry.get('title_ids') and len(roots) == 1 and None not in roots:
            return min(ps4), 'Unique PS4 title/alias with catalogue CUSA evidence', []
        # Ambiguity in a stricter match is not resolved by a looser spelling rule.
        break
    return None, 'Ambiguous title' if candidates else 'No title match', sorted(candidates)


def resolve(entries, games):
    indexes = build_indexes(games)
    records, unique, review, non_game = {}, set(), [], []
    for entry in entries:
        matched, method, candidates = choose_match(entry, games, indexes)
        canonical = root_id(matched, games) if matched else None
        if canonical is None:
            result = {'status':'review', 'reason':method, 'candidate_ids':candidates[:20]}
            review.append({'name':entry['name'], **result})
        else:
            kind = game_type(games[canonical])
            status = 'identified' if kind in GAME_TYPES else 'non_game' if kind in NON_GAME_TYPES else 'review'
            result = {'status':status, 'igdb_id':matched, 'canonical_id':canonical,
                      'canonical_name':games[canonical]['name'], 'game_type':kind,
                      'match_method':method, 'url':games[canonical].get('url')}
            if status == 'identified':
                unique.add(canonical)
            elif status == 'non_game':
                non_game.append({'name':entry['name'], **result})
            else:
                result['reason'] = 'Game type needs review'
                review.append({'name':entry['name'], **result})
        records[entry['name']] = result
    summary = {'visible_listings':len(entries), 'identified_unique_games':len(unique),
               'identified_game_listings':sum(r['status'] == 'identified' for r in records.values()),
               'unresolved_listings':len(review), 'non_game_listings':len(non_game),
               'edition_listings':sum(bool(r.get('igdb_id') and r.get('igdb_id') != r.get('canonical_id')) for r in records.values())}
    summary['duplicate_game_listings'] = summary['identified_game_listings'] - len(unique)
    return records, summary, review, non_game


def main(root=ROOT):
    entries = json.loads(subprocess.check_output(['node', str(root / 'scripts/identity_entries.cjs')], text=True))
    api = API()
    platforms = api.query('platforms', 'fields name; where id = (7,8,9,38,46,48); limit 20;')
    if not any(p['id'] == 48 and p['name'] == 'PlayStation 4' for p in platforms):
        raise RuntimeError('Unexpected platform identities; counts preserved')
    print('Fetching identities for ' + ', '.join(p['name'] for p in platforms), flush=True)
    games = {g['id']:g for g in api.all('games', FIELDS, 'platforms = (7,8,9,38,46,48)')}
    # Retain existing matched identities even if a platform flag has changed.
    missing = {e['igdb_id'] for e in entries if e.get('igdb_id')} - games.keys()
    for _ in range(8):
        missing |= {g['version_parent'] for g in games.values() if g.get('version_parent')} - games.keys()
        if not missing:
            break
        before = len(games)
        ids = sorted(missing)
        for start in range(0, len(ids), 100):
            selected = ','.join(map(str, ids[start:start+100]))
            for g in api.query('games', f'fields {FIELDS}; where id = ({selected}); limit 500;'):
                games[g['id']] = g
        if len(games) == before:
            break
        missing = set()
    if len(games) < 1000:
        raise RuntimeError('Incomplete IGDB identity response; counts preserved')
    records, summary, review, non_game = resolve(entries, games)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    output = {'schema_version':1, 'updated_at':stamp, 'source':'IGDB',
              'policy':'Count each identified game once by IGDB ID, following explicit edition version_parent links. Standalone expansions, remakes and remasters remain distinct. DLC, non-standalone expansions, bundles, mods, packs and updates are separate. Unresolved titles are not included in the verified identity count.',
              'input_sha256':hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest(),
              'summary':summary, 'records':records}
    encoded = json.dumps(output, ensure_ascii=False, indent=2)
    (root / 'game-identities.json').write_text(encoded + '\n')
    (root / 'game-identities.js').write_text('var gameIdentities = ' + encoded + ';\n')
    (root / 'identity-review.json').write_text(json.dumps({'updated_at':stamp, 'unresolved':review, 'non_game':non_game}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else 'Invalid identity data; counts were not published')
