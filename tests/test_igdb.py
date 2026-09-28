import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('igdb_metadata', pathlib.Path(__file__).resolve().parents[1] / 'scripts/igdb_metadata.py')
igdb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(igdb)


class MetadataTests(unittest.TestCase):
    def test_editions_sequels_and_ambiguous_aliases(self):
        games = [{'id': 1, 'name': 'Test Game', 'alternative_names': [{'name': 'Shared'}]},
                 {'id': 2, 'name': 'Test Game II', 'alternative_names': [{'name': 'Shared'}]}]
        matches, review = igdb.match_titles(['Test Game PS4 FPKG', 'Test Game II', 'Test Game Deluxe Edition', 'Shared'], games)
        self.assertEqual(matches['Test Game PS4 FPKG']['id'], 1)
        self.assertEqual(matches['Test Game II']['id'], 2)
        self.assertEqual([r['status'] for r in review], ['unmatched', 'ambiguous'])

    def test_platform_date_and_precision(self):
        rows = [{'platform': 6, 'y': 2010, 'm': 1, 'd': 1}, {'platform': 48, 'y': 2016, 'm': 4},
                {'platform': 48, 'y': 2017, 'm': 3, 'd': 12}, {'platform': 48, 'y': 2099}]
        data = igdb.release_metadata(rows)
        self.assertEqual(data['release_date'], '2016-04')
        self.assertEqual(data['release_sort'], '2016-04-01')
        self.assertEqual(igdb.release_metadata([{'platform': 6, 'y': 2012}]), {})

    def test_publication_and_failure_preserve_existing(self):
        class FakeAPI:
            def all(self, endpoint, fields, condition):
                return {'games': [{'id': 123, 'name': 'Example', 'url': 'https://www.igdb.com/games/example'}],
                        'release_dates': [{'game': 123, 'platform': 48, 'y': 2020, 'm': 2, 'd': 3}],
                        'popularity_primitives': [{'game_id': 123, 'value': 0, 'calculated_at': 1}]}[endpoint]
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / 'ps4_games_expanded.json').write_text('[{"name":"Example"},{"name":"Other"}]')
            for name in ['superpsx-catalog.json', 'additional-catalog.json']:
                (root / name).write_text('{"records":[]}')
            with patch.object(igdb, 'API', FakeAPI):
                igdb.main(root)
            before = (root / 'igdb-metadata.json').read_text()
            data = json.loads(before)
            self.assertEqual(data['summary']['matched'], 1)
            self.assertEqual(data['records']['Example']['popularity'], 0)
            self.assertEqual((root / 'igdb-metadata.js').read_text(), 'var igdbMetadata = ' + before.rstrip() + ';\n')
            with patch.object(igdb, 'API', side_effect=RuntimeError('HTTP 401')):
                with self.assertRaises(RuntimeError):
                    igdb.main(root)
            self.assertEqual((root / 'igdb-metadata.json').read_text(), before)


if __name__ == '__main__':
    unittest.main()
