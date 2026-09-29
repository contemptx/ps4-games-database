import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from game_identities import resolve, normalize, root_id


def game(i, name, kind='Main Game', **extra):
    return {'id':i, 'name':name, 'game_type':{'type':kind}, 'platforms':[48], **extra}


class IdentityTests(unittest.TestCase):
    def test_reviewed_identity_requires_the_reviewed_source(self):
        games = {1:game(1,'Same Name',platforms=[7]),2:game(2,'Same Name','Remake')}
        overrides = {'records':{'Same Name':{'igdb_id':1,'source_urls':['https://example.com/old'],
            'reason':'Source is the original', 'reviewed_at':'2026-09-29'}}}
        old = {'name':'Same Name','igdb_id':2,'sources':[{'page_url':'https://example.com/old'}]}
        record = resolve([old],games,overrides)[0]['Same Name']
        self.assertEqual(record['canonical_id'],1)
        self.assertEqual(record['input_igdb_id'],2)
        changed = dict(old,sources=[{'page_url':'https://example.com/remake'}])
        self.assertEqual(resolve([changed],games,overrides)[1]['unresolved_listings'],1)
        self.assertEqual(resolve([old],{2:games[2]},overrides)[1]['unresolved_listings'],1)

    def test_reviewed_local_games_exclusions_and_ambiguity(self):
        names = ['Local Game','Local Alias','Demo','Ambiguous']
        entries = [{'name':n,'sources':[{'page_url':'https://example.com/'+n}]} for n in names]
        rules = {n:{'source_urls':['https://example.com/'+n], 'reviewed_at':'2026-09-29'} for n in names}
        for n in names[:2]:
            rules[n].update(status='identified',canonical_id='local:one-game',canonical_name='One Game',game_type='main_game')
        rules['Demo'].update(status='non_game',game_type='demo')
        rules['Ambiguous'].update(status='review',reason='Sequel number or URL suffix')
        summary = resolve(entries,{}, {'records':rules})[1]
        self.assertEqual(summary['identified_unique_games'],1)
        self.assertEqual(summary['local_unique_games'],1)
        self.assertEqual(summary['duplicate_game_listings'],1)
        self.assertEqual(summary['non_game_listings'],1)
        self.assertEqual(summary['unresolved_listings'],1)

    def test_reviewed_duplicate_ids_and_real_api_dlc_types(self):
        games = {1:game(1,'A'), 2:game(2,'Regional A'), 3:game(3,'Remake','Remake'),
                 4:game(4,'DLC','DLC'), 5:game(5,'Pack','Pack / Addon')}
        entries = [{'name':g['name']} for g in games.values()]
        summary = resolve(entries,games,{'aliases':{'2':1}})[1]
        self.assertEqual(summary['identified_unique_games'],2)
        self.assertEqual(summary['non_game_listings'],2)
        self.assertIsNone(root_id(1,games,{'1':2,'2':1}))

    def test_aliases_editions_and_non_games(self):
        games = {1:game(1,'One Game', alternative_names=[{'name':'Another Name'}]),
                 2:game(2,'One Game: Gold Edition', version_parent=1),
                 3:game(3,'One Game: DLC', 'DLC / Addon'),
                 4:game(4,'Different Game')}
        entries = [{'name':n} for n in ['One Game','Another Name','One Game Gold Edition','One Game DLC','Different Game','Unknown Game']]
        records, summary, review, other = resolve(entries, games)
        self.assertEqual(summary['identified_unique_games'], 2)
        self.assertEqual(summary['duplicate_game_listings'], 2)
        self.assertEqual(summary['unresolved_listings'], 1)
        self.assertEqual(summary['non_game_listings'], 1)

    def test_shared_cusa_is_not_identity(self):
        games = {1:game(1,'Broken Age'), 2:game(2,'8 Bit Armies')}
        entries = [{'name':n,'title_ids':['CUSA01990']} for n in ['Broken Age','8 Bit Armies']]
        self.assertEqual(resolve(entries,games)[1]['identified_unique_games'],2)

    def test_ambiguous_title_and_remakes(self):
        games = {1:game(1,'Same Name', platforms=[7]), 2:game(2,'Same Name','Remake'),
                 3:game(3,'Other Game'), 4:game(4,'Other Game Remastered','Remaster')}
        entries = [{'name':'Same Name'}, {'name':'Same Name PS4','title_ids':['CUSA12345']},
                   {'name':'Other Game'}, {'name':'Other Game Remastered'}]
        summary = resolve(entries,games)[1]
        self.assertEqual(summary['identified_unique_games'],3)
        self.assertEqual(summary['unresolved_listings'],1)

    def test_normalization_and_parent_cycle(self):
        self.assertEqual(normalize("Assassin’s Creed"),normalize('Assassins Creed'))
        self.assertEqual(normalize('Armored Core VI',True),normalize('Armored Core 6',True))
        self.assertNotEqual(normalize('Mega Man X',True),normalize('Mega Man 10',True))
        self.assertEqual(normalize('4×4 World Trophy'),normalize('4x4 World Trophy'))
        self.assertIsNone(root_id(1,{1:game(1,'A',version_parent=2),2:game(2,'B',version_parent=1)}))
        self.assertIsNone(root_id(1,{1:game(1,'A',version_parent=999)}))

    def test_parenthetical_alias_requires_matching_identity(self):
        games = {1:game(1,'Bully',alternative_names=[{'name':'Canis Canem Edit'}]),
                 2:game(2,'Different Game')}
        entries = [{'name':n} for n in ['Bully (Canis Canem Edit)', 'Bully (Different Game)', 'Bully (New Edition)']]
        records, summary, _, _ = resolve(entries, games)
        self.assertEqual(records['Bully (Canis Canem Edit)']['canonical_id'],1)
        self.assertEqual(summary['identified_unique_games'],1)
        self.assertEqual(summary['unresolved_listings'],2)


if __name__ == '__main__':
    unittest.main()
