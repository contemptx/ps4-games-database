#!/usr/bin/env python3
"""Compare reviewed identities with a dated IGDB PS4/PS VR reference, not a Sony census."""
import argparse
import calendar
import collections
import datetime as dt
import json
import pathlib
import re
import subprocess
from game_identities import game_type, root_id
from igdb_metadata import API, ROOT

PLATFORMS = {48, 165}  # PS4 and original PS VR; excludes PS5/PS VR2.
BASE_TYPES = {'main_game', 'standalone_expansion', 'remake', 'remaster', 'expanded_game', 'port'}
FIELDS = 'name,url,platforms,game_type.type,game_status.status,version_parent'
REGIONS = {'north_america':'USA', 'europe':'EUR', 'japan':'JPN', 'asia':'ASIA', 'korea':'KOR',
           'china':'CHN', 'australia':'AUS', 'new_zealand':'NZL', 'worldwide':'WORLD', 'brazil':'BRA'}
POLICY = ('IGDB reference identities with a PS4 or original PS VR release dated on or before the snapshot date. '
          'Main games, standalone expansions, ports, remakes, remasters and expanded games are included. '
          'Explicit edition parents and reviewed duplicate-ID aliases count once. DLC, updates, bundles, '
          'episodes, seasons, mods and forks are excluded. Future, undated and explicitly unreleased records '
          'are excluded; partial dates qualify only after the end of their stated period. This is a '
          'third-party reference, not Sony\'s official total. An unmatched ID is a candidate gap, not proof '
          'that a game is missing. Regional variants do not increase the unique-title count.')


def normal(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).casefold()).strip('_')


def unreleased(value):
    return any(word in normal(value) for word in ('cancel', 'alpha', 'beta', 'early_access', 'rumor', 'rumour', 'unreleased'))


def release_day(row, today):
    """Use PS4/PS VR-specific dates, never a game's earlier PC/PS2 release date."""
    if row.get('platform') not in PLATFORMS or unreleased((row.get('status') or {}).get('name', '')):
        return None
    year, month, day = row.get('y'), row.get('m'), row.get('d')
    if not year or year < 2013 or 'tbd' in str(row.get('human', '')).lower():
        return None
    try:
        # Conservatively use the end of a month/year when precision is incomplete.
        month = month or 12
        day = day or calendar.monthrange(year, month)[1]
        date = dt.date(year, month, day)
    except (ValueError, TypeError):
        return None
    return date.isoformat() if date <= today else None


def fetch_reference(api, identities, aliases):
    platforms = api.all('platforms', 'name', 'id > 0')
    names = {p['id']:p['name'] for p in platforms}
    if names.get(48) != 'PlayStation 4' or names.get(165) != 'PlayStation VR':
        raise RuntimeError('Unexpected PS4/PS VR platform IDs; reference preserved')
    games = {g['id']:g for g in api.all('games', FIELDS, 'platforms = (48,165)')}
    releases = api.all('release_dates', 'game,platform,y,m,d,human,date,release_region.region,status.name', 'platform = (48,165)')
    if len(games) < 1000 or len(releases) < 1000:
        raise RuntimeError('Incomplete IGDB reference; previous report preserved')
    print('Fetched', len(games), 'PS4/PS VR records and', len(releases), 'release dates', flush=True)
    wanted = {r['game'] for r in releases}
    wanted |= {r['canonical_id'] for r in identities['records'].values()
               if r['status'] == 'identified' and isinstance(r.get('canonical_id'), int)}
    wanted |= {int(k) for k in aliases} | set(aliases.values())
    for _ in range(10):
        wanted |= {g['version_parent'] for g in games.values() if g.get('version_parent')}
        missing = sorted(wanted - games.keys())
        if not missing:
            break
        previous = len(games)
        for start in range(0, len(missing), 100):
            selected = ','.join(map(str, missing[start:start + 100]))
            games.update({g['id']:g for g in api.query('games', f'fields {FIELDS}; where id = ({selected}); limit 500;')})
        if len(games) == previous:
            break
    return {'platforms':platforms, 'games':list(games.values()), 'release_dates':releases,
            'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()}


def reconcile(reference, entries, aliases, today):
    games = {g['id']:g for g in reference['games']}
    platform_names = {p['id']:p['name'] for p in reference.get('platforms', [])}
    local = collections.defaultdict(list)
    for entry in entries:
        if entry.get('canonical_id') is not None:
            local[entry['canonical_id']].append(entry)
    dated = collections.defaultdict(list)
    for row in reference['release_dates']:
        day = release_day(row, today)
        if day:
            dated[row['game']].append((day, row))
    eligible, ps4_roots = {}, set()
    excluded = collections.Counter()
    ps4_ids = {g['id'] for g in games.values() if PLATFORMS.intersection(g.get('platforms', []))}
    ps4_ids |= {r['game'] for r in reference['release_dates'] if r.get('platform') in PLATFORMS}
    for game_id in sorted(ps4_ids):
        game = games.get(game_id, {})
        canonical = root_id(game_id, games, aliases)
        if canonical is None:
            excluded['unresolved_edition_parent'] += 1
            continue
        ps4_roots.add(canonical)
        parent = games[canonical]
        # A season/DLC carrying a base-game parent must not supply a base release date.
        if game_type(game) not in BASE_TYPES or game_type(parent) not in BASE_TYPES:
            excluded['out_of_scope_type'] += 1
            continue
        if unreleased((game.get('game_status') or {}).get('status', '')):
            excluded['unreleased_status'] += 1
            continue
        if game_id not in dated:
            excluded['future_undated_or_unreleased_date'] += 1
            continue
        row = eligible.setdefault(canonical, {'canonical_id':canonical, 'name':parent['name'],
            'url':parent.get('url'), 'game_type':game_type(parent), 'reference_ids':[],
            'reference_regions':set(), 'first_ps4_release':None})
        row['reference_ids'].append(game_id)
        for day, release in dated[game_id]:
            if not row['first_ps4_release'] or day < row['first_ps4_release']:
                row['first_ps4_release'] = day
                row['release_date_label'] = str(release['y']) + (f"-{release['m']:02}" if release.get('m') else '') + (f"-{release['d']:02}" if release.get('m') and release.get('d') else '')
            value = normal((release.get('release_region') or {}).get('region', ''))
            if value:
                row['reference_regions'].add(REGIONS.get(value, value.upper()))
    for key, row in eligible.items():
        row['reference_regions'] = sorted(row['reference_regions'])
        listings = local.get(key, [])
        row['catalogued'] = bool(listings)
        row['listings'] = [e['name'] for e in listings]
        row['package_regions'] = sorted({r for e in listings for link in e['links'] for r in link['regions']})
        row['base_regions'] = sorted({r for e in listings for link in e['links'] if link['kind'] == 'base' for r in link['regions']})
        row['has_labelled_base'] = any(link['kind'] == 'base' for e in listings for link in e['links'])
    outside = []
    for key, listings in local.items():
        if key in eligible:
            continue
        game = games.get(key, {})
        if isinstance(key, str):
            reason = 'Local identity without an IGDB match'
        elif key not in ps4_roots:
            reason = 'No PS4/PS VR reference match; platform/conversion review needed'
        else:
            reason = 'PS4/PS VR reference exists but type/date/status is outside this benchmark'
        outside.append({'canonical_id':key, 'name':listings[0].get('canonical_name') or game.get('name') or listings[0]['name'],
            'reason':reason, 'url':game.get('url'), 'platforms':[platform_names.get(p, str(p)) for p in game.get('platforms', [])],
            'listings':[e['name'] for e in listings]})
    rows = sorted(eligible.values(), key=lambda r:r['name'].casefold())
    matched = sum(r['catalogued'] for r in rows)
    summary = {'catalogue_unique_identities':len(local), 'reference_unique_games':len(rows),
        'reference_matches':matched, 'reference_gaps':len(rows)-matched,
        'matches_with_labelled_base':sum(r['catalogued'] and r['has_labelled_base'] for r in rows),
        'local_ps4_or_psvr_reference':len(set(local) & ps4_roots),
        'local_without_ps4_reference':sum(isinstance(k,int) and k not in ps4_roots for k in local),
        'local_identities_without_igdb':sum(isinstance(k,str) for k in local),
        'local_outside_dated_benchmark':len(outside), 'excluded_reference_records':dict(excluded)}
    assert summary['reference_matches'] + summary['local_outside_dated_benchmark'] == len(local)
    return {'as_of':today.isoformat(), 'reference_fetched_at':reference.get('fetched_at'), 'policy':POLICY,
        'summary':summary, 'reference':rows, 'outside_reference':sorted(outside,key=lambda r:r['name'].casefold())}


def region_report(data):
    by_region, links_by_url = {}, collections.defaultdict(list)
    conflicts, unknown = [], []
    for entry in data['entries']:
        for link in entry['links']:
            links_by_url[link['url']].append(link)
            for code in link['regions']:
                row = by_region.setdefault(code, {'links':set(), 'listings':set(), 'identities':set(), 'base_identities':set()})
                row['links'].add(link['url']); row['listings'].add(entry['name'])
                if entry.get('canonical_id') is not None:
                    row['identities'].add(entry['canonical_id'])
                    if link['kind'] == 'base': row['base_identities'].add(entry['canonical_id'])
            if not link['regions']:
                item = {'listing':entry['name'], 'canonical_id':entry.get('canonical_id'),
                        'sources':entry.get('sources', []), **link}
                (conflicts if link['region_status'] == 'conflict' else unknown).append(item)
    regions = {code:{k:len(v) for k,v in row.items()} for code,row in sorted(by_region.items())}
    distinct_known = sum(any(link['regions'] for link in links) for links in links_by_url.values())
    return {'summary':{**data['summary'], 'distinct_links':len(links_by_url),
            'distinct_links_with_region_evidence':distinct_known}, 'regions':regions,
        'note':'Regions are source/filename claims about individual releases, not language or licensing verification. '
               'Counts per region overlap; a game or file can have more than one label. Base counts require an explicit base label. '
               'Unknown/conflicting regions remain visible and never imply worldwide availability.',
        'review':{'conflicts':conflicts, 'unknown':unknown}}


def publish(root, report, regions, identity_summary):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    report.update(updated_at=stamp, regions={k:v for k,v in regions.items() if k != 'review'}, identity_summary=identity_summary,
        sony={'published_lower_bound':4000, 'historical_date':'2020-11-09',
            'historical_url':'https://blog.playstation.com/2020/11/09/ps5-the-ultimate-faq/',
            'current_url':'https://www.playstation.com/en-us/support/games/ps5-backward-compatibility-games/',
            'note':'Sony publishes 4,000+, not an exact current worldwide unique-title census. Do not use 4,000 as a completeness denominator.'})
    (root/'catalogue-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (root/'region-review.json').write_text(json.dumps({'updated_at':stamp, **regions['review']},ensure_ascii=False,indent=2)+'\n')
    s=report['summary']; r=regions['summary']
    lines=['# PS4 catalogue coverage', '', 'Snapshot: '+report['as_of'], '',
        '**Sony publishes “4,000+” PS4 games, not an exact current total.** The same lower-bound wording appeared in the '
        '[November 2020 PS5 FAQ](https://blog.playstation.com/2020/11/09/ps5-the-ultimate-faq/) and is still on '
        '[PlayStation Support](https://www.playstation.com/en-us/support/games/ps5-backward-compatibility-games/). '
        'It cannot establish catalogue completeness.', '',
        '| Measure | Unique identities |', '| --- | ---: |',
        f"| All identified catalogue games (includes conversions/other platforms) | {s['catalogue_unique_identities']:,} |",
        f"| Dated IGDB PS4/PS VR reference | {s['reference_unique_games']:,} |",
        f"| Matched in our catalogue | {s['reference_matches']:,} |",
        f"| Matched with an explicitly labelled base link | {s['matches_with_labelled_base']:,} |",
        f"| Unmatched reference IDs — candidate gaps | {s['reference_gaps']:,} |",
        f"| Catalogue identities outside this dated reference | {s['local_outside_dated_benchmark']:,} |", '',
        POLICY, '', 'A matching title does not prove a working download or a licensed/native package. '
        'Legacy conversions can share identities with official reissues. Delisted records are retained when their dated release qualifies. '
        'This covers all publishers, not only Sony-published games.', '',
        '## Package regions', '',
        f"{r['identified_links']:,} of {r['links']:,} visible link occurrences have region evidence; "
        f"{r['unknown_links']:,} are unknown/conflicting, including {r['conflicting_links']:,} contradictions.", '',
        '| Region | Distinct links | Unique identities | With labelled base |', '| --- | ---: | ---: | ---: |']
    for code,row in regions['regions'].items():
        lines.append(f"| {code} | {row['links']:,} | {row['identities']:,} | {row['base_identities']:,} |")
    lines += ['', regions['note'], '',
        'Reference release regions from IGDB describe market release history and are kept separate from package regions. '
        'Worldwide release history is not proof that a particular regional file is available.', '',
        '[Browse and search the reconciliation](https://contemptx.github.io/ps4-games-database/coverage.html). '
        '[Full reference and gaps](catalogue-coverage.json). [Region review queue](region-review.json).', '']
    (root/'catalogue-coverage.md').write_text('\n'.join(lines))
    print(json.dumps({'coverage':s,'regions':r}),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',type=pathlib.Path,help='Use a saved public IGDB reference snapshot')
    parser.add_argument('--save-reference',type=pathlib.Path,help='Save raw public metadata for audit')
    args=parser.parse_args()
    identities=json.loads((ROOT/'game-identities.json').read_text())
    aliases=json.loads((ROOT/'identity-overrides.json').read_text()).get('aliases',{})
    data=json.loads(subprocess.check_output(['node',str(ROOT/'scripts/region_entries.cjs')],text=True))
    reference=json.loads(args.reference.read_text()) if args.reference else fetch_reference(API(),identities,aliases)
    if args.save_reference:
        args.save_reference.parent.mkdir(parents=True,exist_ok=True)
        args.save_reference.write_text(json.dumps(reference,ensure_ascii=False))
    report=reconcile(reference,data['entries'],aliases,dt.datetime.now(dt.timezone.utc).date())
    publish(ROOT,report,region_report(data),data['identity_summary'])


if __name__ == '__main__':
    main()
