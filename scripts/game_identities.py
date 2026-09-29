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
NON_GAME_TYPES = {'dlc', 'dlc_addon', 'expansion', 'bundle', 'mod', 'pack', 'pack_addon', 'update',
                  'demo', 'prototype', 'utility', 'firmware', 'guide', 'video_experience'}
PLATFORM_NAMES = {'PlayStation', 'PlayStation 2', 'PlayStation 3', 'PlayStation 4',
                  'PlayStation Portable', 'PlayStation Vita', 'PlayStation VR', 'Sega Saturn'}


def normalize(value, relaxed=False):
    value = html.unescape(value).casefold()
    value = re.sub(r'\s+(?:ps4|fpkg|pkg)(?:\s+(?:ps4|fpkg|pkg|download))*\s*$', '', value)
    value = value.replace('&', ' and ').replace('×', 'x')
    value = re.sub(r"['’‘`\u200b\ufeff]", '', value)
    value = ''.join(ch for ch in unicodedata.normalize('NFKD', value) if not unicodedata.combining(ch))
    words = re.sub(r'[^\w]+', ' ', value).strip().split()
    if relaxed:
        words = [ROMAN.get(w, w) for w in words]
        return ''.join(words)
    return ' '.join(words)


def root_id(game_id, games, aliases=None):
    seen = set()
    aliases = aliases or {}
    while game_id in games:
        if game_id in seen:
            return None
        seen.add(game_id)
        parent = aliases.get(str(game_id)) or games[game_id].get('version_parent')
        if not parent:
            return game_id
        game_id = parent
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
    if not candidates:
        # Sources sometimes append a regional alternative title in parentheses.
        # Require BOTH titles to identify the same game; never just discard a suffix.
        for name in names:
            pair = re.fullmatch(r'(.+?)\s*\(([^()]+)\)\s*', name)
            if not pair:
                continue
            for relaxed in (False, True):
                sides = [indexes[int(relaxed)].get(normalize(n, relaxed), set()) for n in pair.groups()]
                roots = [{root_id(i, games) for i in side} for side in sides]
                if all(len(r) == 1 and None not in r for r in roots) and roots[0] == roots[1]:
                    return min(sides[0]), 'Both regional title spellings identify the same game', []
    return None, 'Ambiguous title' if candidates else 'No title match', sorted(candidates)


def source_urls(entry):
    return {s['page_url'] for s in entry.get('sources', []) if s.get('page_url')}


def reviewed_match(entry, overrides, games):
    item = overrides.get('records', {}).get(entry['name'])
    if not item:
        return None
    # A title is not enough to transfer a manual decision to a different page.
    if not source_urls(entry).intersection(item.get('source_urls', [])):
        return {'status':'review', 'reason':'Source changed since the identity review'}
    if item.get('status') in ('review', 'non_game'):
        return {k:item[k] for k in ('status', 'reason', 'game_type', 'evidence', 'reviewed_at') if k in item}
    if item.get('igdb_id'):
        if item['igdb_id'] not in games:
            return {'status':'review', 'reason':'Reviewed IGDB identity unavailable; match not replaced by a guess'}
        return item
    if (item.get('status') == 'identified' and
            re.fullmatch(r'local:[a-z0-9-]+', item.get('canonical_id', '')) and
            item.get('canonical_name') and item.get('game_type') in GAME_TYPES):
        return item
    raise RuntimeError('Invalid reviewed identity for ' + entry['name'])


def resolve(entries, games, overrides=None):
    overrides = overrides or {}
    indexes = build_indexes(games)
    records, unique, review, non_game = {}, set(), [], []
    for entry in entries:
        manual = reviewed_match(entry, overrides, games)
        if manual:
            matched, method, candidates = manual.get('igdb_id'), 'Reviewed: ' + manual.get('reason', ''), []
        else:
            matched, method, candidates = choose_match(entry, games, indexes)
        canonical = root_id(matched, games, overrides.get('aliases')) if matched else None
        if manual and manual.get('status') in ('review', 'non_game'):
            result = dict(manual)
        elif manual and isinstance(manual.get('canonical_id'), str) and manual.get('canonical_id', '').startswith('local:'):
            result = {k:manual[k] for k in ('status','canonical_id','canonical_name','game_type','reason','evidence','reviewed_at') if k in manual}
            result['match_method'] = method
        elif canonical is None:
            result = {'status':'review', 'reason':method, 'candidate_ids':candidates[:20]}
        else:
            kind = game_type(games[canonical])
            status = 'identified' if kind in GAME_TYPES else 'non_game' if kind in NON_GAME_TYPES else 'review'
            result = {'status':status, 'igdb_id':matched, 'canonical_id':canonical,
                      'canonical_name':games[canonical]['name'], 'game_type':kind,
                      'match_method':method, 'url':games[canonical].get('url')}
            if status == 'review':
                result['reason'] = 'Game type needs review'
        result['input_igdb_id'] = entry.get('igdb_id')
        result['source_urls'] = sorted(source_urls(entry))
        if manual:
            result['reviewed_at'] = manual.get('reviewed_at')
            result['evidence'] = manual.get('evidence', [])
        if result['status'] == 'identified':
            unique.add(result['canonical_id'])
        elif result['status'] == 'non_game':
            non_game.append({'name':entry['name'], **result})
        else:
            review.append({'name':entry['name'], **result})
        records[entry['name']] = result
    summary = {'visible_listings':len(entries), 'identified_unique_games':len(unique),
               'identified_game_listings':sum(r['status'] == 'identified' for r in records.values()),
               'unresolved_listings':len(review), 'non_game_listings':len(non_game),
               'reviewed_listings':sum(bool(r.get('reviewed_at')) for r in records.values()),
               'local_unique_games':len({r['canonical_id'] for r in records.values() if r['status'] == 'identified' and isinstance(r.get('canonical_id'),str)}),
               'edition_listings':sum(bool(r.get('igdb_id') and r.get('igdb_id') != r.get('canonical_id')) for r in records.values())}
    summary['duplicate_game_listings'] = summary['identified_game_listings'] - len(unique)
    return records, summary, review, non_game


def main(root=ROOT):
    entries = json.loads(subprocess.check_output(['node', str(root / 'scripts/identity_entries.cjs')], text=True))
    overrides_path = root / 'identity-overrides.json'
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    api = API()
    platforms = [p for p in api.all('platforms', 'name', 'id > 0') if p['name'] in PLATFORM_NAMES]
    if not any(p['id'] == 48 and p['name'] == 'PlayStation 4' for p in platforms):
        raise RuntimeError('Unexpected platform identities; counts preserved')
    print('Fetching identities for ' + ', '.join(p['name'] for p in platforms), flush=True)
    platform_ids = ','.join(str(p['id']) for p in platforms)
    games = {g['id']:g for g in api.all('games', FIELDS, f'platforms = ({platform_ids})')}
    # Retain existing matched identities even if a platform flag has changed.
    missing = {e['igdb_id'] for e in entries if e.get('igdb_id')} - games.keys()
    missing |= {r['igdb_id'] for r in overrides.get('records', {}).values() if r.get('igdb_id')} - games.keys()
    missing |= {int(i) for i in overrides.get('aliases', {})} - games.keys()
    missing |= set(overrides.get('aliases', {}).values()) - games.keys()
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
    records, summary, review, non_game = resolve(entries, games, overrides)
    write_outputs(root, entries, records, summary, review, non_game)


def write_outputs(root, entries, records, summary, review, non_game):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    output = {'schema_version':2, 'updated_at':stamp, 'source':'IGDB and reviewed source identities',
              'policy':'Count identified game identities once, following explicit IGDB edition version_parent links and reviewed duplicate-ID aliases. Standalone expansions, remakes and remasters remain distinct. Source-reviewed games lacking a reliable IGDB match use explicit local identities. DLC, non-standalone expansions, collections, mods, demos, prototypes, utilities and passive video experiences are separate. Ambiguous source titles are excluded pending confirmation. This is a title identity count, not a download availability or package-content guarantee.',
              'input_sha256':hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest(),
              'summary':summary, 'records':records}
    encoded = json.dumps(output, ensure_ascii=False, indent=2)
    (root / 'game-identities.json').write_text(encoded + '\n')
    (root / 'game-identities.js').write_text('var gameIdentities = ' + encoded + ';\n')
    (root / 'identity-review.json').write_text(json.dumps({'updated_at':stamp, 'unresolved':review, 'non_game':non_game}, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Game identity review', '', 'Updated: ' + stamp, '',
             f"**{summary['identified_unique_games']:,} identified unique games** across {summary['visible_listings']:,} visible listings.", '',
             f"{summary['duplicate_game_listings']:,} duplicate/edition listings count once; {summary['non_game_listings']:,} collections, add-ons, demos and other entries are separate; {summary['unresolved_listings']:,} listings remain unresolved.", '',
             output['policy'], '',
             f"{summary['reviewed_listings']:,} listings have a recorded manual review. {summary['local_unique_games']} game identities use source metadata because a reliable IGDB match was unavailable.", '',
             'The remaining entries need a confirmed game title plus a release year, title ID, or package filename. They are excluded from the identified count until then.', '',
             '| Listing | Source | Reason |', '| --- | --- | --- |']
    for item in review:
        name = item['name'].replace('|', '\\|')
        urls = item.get('source_urls', [])
        link = '[Source page](' + urls[0] + ')' if urls else 'Unavailable'
        lines.append('| ' + name + ' | ' + link + ' | ' + item.get('reason', '').replace('|', '\\|') + ' |')
    lines += ['', 'Reviewed decisions and evidence: [identity-overrides.json](identity-overrides.json).',
              'Full classification: [identity-review.json](identity-review.json).', '']
    (root / 'identity-review.md').write_text('\n'.join(lines))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else 'Invalid identity data; counts were not published')
