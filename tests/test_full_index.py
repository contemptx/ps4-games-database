import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from full_index import Indexer, Held, arabic_figures, supplement, runnable_count, source_counts
from release_metadata import parse_source, download_url, details
from validate_index import validate

class FullIndexTests(unittest.TestCase):
    def test_language_patches_are_not_game_updates(self):
        self.assertEqual(details('English Patch v1.20')['kind'], 'patch')
        self.assertEqual(details('Backport Patch')['kind'], 'fix')

    def test_public_redirect_encoding_and_labels(self):
        body = '<div id="articleContent"><p>CUSA12345 – EUR</p><p>Update v1.58 (9.00+) : <a href="https://justpaste.it/redirect/example/https%3A%2F%2F1fichier.com%2F%3Ftest%26amp%3Baf%3D1">1File</a></p></div>'
        entries = parse_source(body, 'https://justpaste.it/example')
        self.assertEqual(entries[0]['url'], 'https://1fichier.com/?test&af=1')
        self.assertEqual(entries[0]['version'], '1.58')
        self.assertEqual(entries[0]['title_id'], 'CUSA12345')
        self.assertEqual(download_url('https://justpaste.it/test', 'https://evil.test/redirect/test/a'), 'https://evil.test/redirect/test/a')
    def test_unknown_rows_retained_without_guessing(self):
        result = supplement('<div class="entry-content"><a href="https://1fichier.com/?abc">Mirror</a><a href="https://filecrypt.cc/Container/a">Excluded</a></div>', 'https://dlpsgame.com/test/', [])
        self.assertEqual(len(result), 1)
        self.assertNotIn('kind', result[0])
        self.assertTrue(result[0]['unlabelled'])
    def test_named_arabic_figures_ignore_navigation(self):
        rows = arabic_figures('<nav><a href="https://ouo.io/nav">Menu</a></nav><figure><h2>A Game</h2><a href="https://ouo.io/id">https://ouo.io/id</a></figure>', 'https://arabicps4games.github.io/indexallps4.html')
        self.assertEqual(rows[0]['name'], 'A Game')
        self.assertEqual(rows[0]['links'], ['https://ouo.io/id'])
    def test_arabic_flip_card_layout(self):
        rows = arabic_figures('<div class="inside-page__container"><font color="black"><font color="white">GRIP</font><a href="https://ouo.io/id">Download</a></font></div>', 'https://arabicps4games.github.io/indexps4page100.html')
        self.assertEqual(rows[0]['name'], 'GRIP')
        self.assertEqual(rows[0]['links'], ['https://ouo.io/id'])

    def seed(self, root):
        (root/'ps4_games_expanded.json').write_text(json.dumps([{'name':'Example','page_url':'https://dlpsgame.com/example/','download_links':{}}]))
        (root/'release-metadata.json').write_text('{"pages":{}}')
        (root/'superpsx-catalog.json').write_text('{"records":[],"checked":{}}')
        (root/'link-status.json').write_text('{"version":1,"links":{}}')
    def test_checkpoint_saves_data_before_completed_state_and_resumes(self):
        class FakeReader:
            def __init__(self,*a): pass
            def start(self): pass
            def get(self,url): return '<div class="entry-content"><p>CUSA12345 – EUR</p><p>Update v1.10 : <a href="https://1fichier.com/?new">File</a></p></div>'
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.seed(root)
            index=Indexer(root,2,1)
            with patch('full_index.Reader',FakeReader): index.process('dlps')
            state=json.loads((root/'index-state.json').read_text())
            data=json.loads((root/'release-metadata.json').read_text())
            self.assertEqual(state['sources']['dlps']['items']['https://dlpsgame.com/example/']['status'],'labelled')
            self.assertEqual(data['pages']['https://dlpsgame.com/example/']['links'][0]['version'],'1.10')
            resumed=Indexer(root,2,1)
            self.assertEqual(resumed.pending('dlps'),[])
            resumed.save();validate(root)
    def test_access_hold_leaves_queue_pending_and_does_not_retry(self):
        class FakeReader:
            calls=0
            def __init__(self,*a): pass
            def start(self): FakeReader.calls+=1;raise Held('HTTP 403')
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.seed(root)
            index=Indexer(root,2,1)
            with patch('full_index.Reader',FakeReader):
                index.process('dlps');index.process('dlps')
            self.assertEqual(FakeReader.calls,1)
            self.assertEqual(source_counts(index.state['sources']['dlps'])['pending'],1)
            self.assertTrue(index.state['sources']['dlps']['held'])
    def test_new_link_checks_added_before_continuation_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.seed(root)
            index=Indexer(root,2,1)
            index.releases['pages']['https://dlpsgame.com/example/']={'links':[{'url':'https://www.mediafire.com/file/newid/name.pkg/file'}]}
            index.save()
            self.assertIn('https://www.mediafire.com/file/newid',index.state['sources']['mediafire']['items'])

if __name__ == '__main__': unittest.main()
