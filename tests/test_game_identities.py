import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from game_identities import resolve, normalize, root_id


def game(i, name, kind='Main Game', **extra):
    return {'id':i, 'name':name, 'game_type':{'type':kind}, 'platforms':[48], **extra}


class IdentityTests(unittest.TestCase):
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
