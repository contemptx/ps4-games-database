#!/usr/bin/env python3
"""Publish public PS4 metadata only. Credentials are read from Actions secrets."""
import collections
import datetime as dt
import html
import json
import math
import os
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PS4 = 48


def normalize(name):
    name = html.unescape(name).casefold()
    # Remove source packaging suffixes, never edition names or sequel numbers.
    name = re.sub(r'\s+(?:ps4|fpkg|pkg)(?:\s+(?:ps4|fpkg|pkg|download))*\s*$', '', name)
    name = name.replace('&', ' and ')
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', name).strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected API redirect; credentials were not forwarded')


class API:
    def __init__(self):
        self.client_id = os.environ.get('IGDB_CLIENT_ID', '')
        secret = os.environ.get('IGDB_CLIENT_SECRET', '')
        if not self.client_id or not secret:
            raise RuntimeError('Configure IGDB_CLIENT_ID and IGDB_CLIENT_SECRET as GitHub Actions repository secrets')
        self.opener = urllib.request.build_opener(NoRedirect())
        payload = urllib.parse.urlencode({'client_id': self.client_id, 'client_secret': secret,
                                          'grant_type': 'client_credentials'}).encode()
        # Body parameters keep credentials out of URLs and error messages.
        self.token = self.request('https://id.twitch.tv/oauth2/token', payload,
                                 {'Content-Type': 'application/x-www-form-urlencoded'})['access_token']

    def request(self, url, payload, headers):
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
                with self.opener.open(req, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError('IGDB/Twitch request failed: HTTP ' + str(error.code)) from None
            except urllib.error.URLError:
                raise RuntimeError('IGDB/Twitch network request failed') from None
        raise RuntimeError('API retry limit reached')

    def query(self, endpoint, query):
        time.sleep(0.3)  # Below the documented four requests per second.
        data = self.request('https://api.igdb.com/v4/' + endpoint, query.encode(),
                            {'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token,
                             'Content-Type': 'text/plain', 'Accept': 'application/json'})
        if not isinstance(data, list):
            raise RuntimeError('Unexpected IGDB response')
        return data

    def all(self, endpoint, fields, condition):
        result, last = [], 0
        for _ in range(500):
            batch = self.query(endpoint, f'fields {fields}; where ({condition}) & id > {last}; sort id asc; limit 500;')
            if not batch:
                return result
            newest = max(row['id'] for row in batch)
            if newest <= last:
                raise RuntimeError('API pagination did not advance')
            result.extend(batch)
            last = newest
        raise RuntimeError('API pagination exceeded safety limit')


def match_titles(names, games):
    index = collections.defaultdict(dict)
    for game in games:
        for title in [game['name']] + [a['name'] for a in game.get('alternative_names', [])]:
            index[normalize(title)][game['id']] = game
    matches, review = {}, []
    for name in names:
        candidates = index.get(normalize(name), {})
        if len(candidates) == 1:
            matches[name] = next(iter(candidates.values()))
        else:
            review.append({'name': name, 'status': 'ambiguous' if candidates else 'unmatched',
                           'candidate_ids': sorted(candidates)})
    return matches, review


def release_metadata(rows):
    # Partial dates retain their precision; they are sorted at the start of that period.
    candidates = []
    today = dt.datetime.now(dt.timezone.utc).date()
    for row in rows:
        if row.get('platform') != PS4 or not row.get('y'):
            continue
        y, m, d = row['y'], row.get('m'), row.get('d')
        try:
            date = dt.date(y, m or 1, d or 1)
        except (ValueError, TypeError):
            continue
        if date > today:
            continue
        label = str(y) + (f'-{m:02}' if m else '') + (f'-{d:02}' if m and d else '')
        candidates.append((date, label, row.get('release_region')))
    if not candidates:
        return {}
    date, label, region = min(candidates, key=lambda x: (x[0], -len(x[1])))
    return {'release_date': label, 'release_sort': date.isoformat(), 'release_region': region}


def names_from_catalogue(root):
    names = set()
    for filename in ['ps4_games_expanded.json', 'superpsx-catalog.json', 'additional-catalog.json']:
        data = json.loads((root / filename).read_text())
        records = data if isinstance(data, list) else data.get('records', [])
        names.update(r['name'] for r in records if r.get('name'))
    return sorted(names)


def main(root=ROOT):
    api = API()
    games = api.all('games', 'name,url,alternative_names.name', f'platforms = ({PS4})')
    if not games:
        raise RuntimeError('No PS4 games returned; existing metadata preserved')
    matches, review = match_titles(names_from_catalogue(root), games)
    if not matches:
        raise RuntimeError('No catalogue titles matched; existing metadata preserved')
    releases = api.all('release_dates', 'game,platform,y,m,d,release_region', f'platform = {PS4}')
    dates = collections.defaultdict(list)
    for row in releases:
        dates[row['game']].append(row)
    popular = {}
    ids = sorted({g['id'] for g in matches.values()})
    for start in range(0, len(ids), 100):
        selected = ','.join(map(str, ids[start:start + 100]))
        for row in api.all('popularity_primitives', 'game_id,value,calculated_at',
                           f'popularity_type = 1 & game_id = ({selected})'):
            value = row.get('value')
            if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
                old = popular.get(row['game_id'], {})
                if row.get('calculated_at', 0) >= old.get('calculated_at', 0):
                    popular[row['game_id']] = row
    records = {}
    for name, game in matches.items():
        record = {'igdb_id': game['id'], 'name': game['name'],
                  'match_method': 'unique normalized title or alias', **release_metadata(dates[game['id']])}
        url = game.get('url', '')
        if url.startswith('https://www.igdb.com/games/'):
            record['url'] = url
        if game['id'] in popular:
            row = popular[game['id']]
            record.update(popularity=row['value'], popularity_calculated_at=row.get('calculated_at'))
        records[name] = record
    output = {'schema_version': 1, 'source': 'IGDB', 'updated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'popularity_metric': 'IGDB visits', 'release_policy': 'Earliest known PS4 release across regions; partial dates retain precision',
              'summary': {'titles': len(matches) + len(review), 'matched': len(matches), 'review': len(review),
                          'with_dates': sum('release_date' in r for r in records.values()),
                          'with_popularity': sum('popularity' in r for r in records.values())}, 'records': records}
    # Only allowlisted metadata is serialized. Tokens and credentials never enter outputs.
    encoded = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False)
    (root / 'igdb-metadata.json').write_text(encoded + '\n')
    (root / 'igdb-metadata.js').write_text('var igdbMetadata = ' + encoded + ';\n')
    (root / 'igdb-review.json').write_text(json.dumps({'updated_at': output['updated_at'], 'records': review}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(output['summary']))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as error:
        # No response bodies, request headers or tracebacks in Actions logs.
        raise SystemExit(str(error) if isinstance(error, RuntimeError) else 'Invalid API or catalogue data; metadata was not published')
