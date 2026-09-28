import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from superpsx import article, parse_downloads, source_url

URL = 'https://www.superpsx.com/dll-testps4/'

class SuperPSXTests(unittest.TestCase):
    def test_article_identity_and_image_button(self):
        body = '<h1>Example PS4</h1><a href="/dll-navigationps4/">Nav</a><div class="entry-content"><a href="/dll-testps4/"><img src="button.png"></a></div>'
        self.assertEqual(article(body, URL)['download_pages'], [URL])
        self.assertIsNone(article(body.replace('Example PS4', 'Example PS3'), URL))
        self.assertIsNone(article('<h1>PS4 Guide</h1><div class="entry-content">No download</div>', URL))
        self.assertFalse(source_url('https://www.superpsx.com.evil.test/dll-test/'))

    def test_release_rows_and_context_reset(self):
        body = '''<a href="https://1fichier.com/?nav">Nav</a><div class="entry-content"><table>
        <tr><td>Version ⇛</td><td>CUSA43772 – EUR by uploader</td></tr>
        <tr><td>Game (12.00+) ⇛</td><td><a href="https://mocha.my/share/base">Mocha</a><a href="https://1fichier.com/?base">OneFile</a><a href="https://filecrypt.cc/Container/base">Filecrypt</a></td></tr>
        <tr><td>Update v1.08 (12.00+) ⇛</td><td><a href="https://filekeeper.net/id/file.pkg">FileK</a></td></tr>
        <tr><td>DLC ⇛</td><td><a href="https://vikingfile.com/f/dlc">Viki</a></td></tr>
        <tr><td>Version ⇛</td><td>Unknown edition</td></tr>
        <tr><td>Update v9.00 ⇛</td><td><a href="https://1fichier.com/?different">OneFile</a></td></tr>
        </table><table><tr><td>Game ⇛</td><td><a href="https://1fichier.com/?newtable">OneFile</a></td></tr></table></div>'''
        links = parse_downloads(body, URL)
        self.assertEqual(len(links), 6)
        self.assertEqual(links[0]['kind'], 'base')
        self.assertEqual(links[0]['firmware'], '12.00+')
        self.assertEqual(links[0]['title_id'], 'CUSA43772')
        self.assertEqual(links[2]['kind'], 'update')
        self.assertEqual(links[2]['version'], '1.08')
        self.assertNotIn('version', links[3])
        self.assertNotIn('title_id', links[4])
        self.assertNotIn('title_id', links[5])
        self.assertTrue(all(x['source_url'] == URL for x in links))

    def test_language_editions_and_bracketed_firmware(self):
        body = '<div class="entry-content"><table><tr><td colspan="2">CUSA44357 – JPN [Modded English Dub]</td></tr></table><table><tr><td>Version</td><td>CUSA44357 – JPN</td></tr><tr><td>English Patch</td><td><a href="https://1fichier.com/?english">OneFile</a></td></tr><tr><td>Game v2.24_[9.00-11.00]</td><td><a href="https://1fichier.com/?base">OneFile</a></td></tr><tr><td>DLC (v2)</td><td><a href="https://1fichier.com/?dlc">OneFile</a></td></tr></table></div>'
        links = parse_downloads(body, URL)
        self.assertEqual(links[0]['kind'], 'patch')
        self.assertIn('English Dub', links[0]['edition'])
        self.assertIn('English Dub', links[0]['source_section'])
        self.assertEqual(links[1]['firmware'], '9.00/11.00')
        self.assertEqual(links[2]['version'], '2')

    def test_game_with_fix_remains_base(self):
        links = parse_downloads('<div class="entry-content"><table><tr><td>Game (v1.01) (Fix 5.05/6.72/7.xx/9.00/11.00/12.00)</td><td><a href="https://1fichier.com/?base">OneFile</a></td></tr></table></div>', URL)
        self.assertEqual(links[0]['kind'], 'base')
        self.assertEqual(links[0]['version'], '1.01')
        self.assertEqual(links[0]['variant'], 'Backport / fix')
        self.assertEqual(links[0]['firmware'], '5.05/6.72/7.xx/9.00/11.00/12.00')

if __name__ == '__main__':
    unittest.main()
