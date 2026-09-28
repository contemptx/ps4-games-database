import base64
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from release_metadata import parse_source, filename_details, is_access_error

SOURCE = 'https://dlpsgame.com/example/'


class ReleaseMetadataTests(unittest.TestCase):
    def test_comment_widget_text_is_not_an_access_error(self):
        self.assertFalse(is_access_error('<title>Game</title><div class="entry-content">Game</div><script>var translation="Too many requests";</script>'))
        self.assertTrue(is_access_error('<title>Too many requests</title><p>Try later</p>'))
        self.assertTrue(is_access_error('<p>Verify you are human</p>'))

    def test_versions_are_scoped_to_release_rows(self):
        body = '''<div class="entry-content"><p>CUSA34255 – EUR (v1.17)</p>
        <p>Game: <a href="https://1fichier.com/?base">1File</a></p>
        <p>Update 1.17 (Fix 5.05/9.00): <a href="https://1fichier.com/?update">1File</a></p>
        <p>DLC (14): <a href="https://1fichier.com/?dlc">1File</a></p>
        <p>CUSA99999 – USA</p><p>Update 1.09: <a href="https://1fichier.com/?other">1File</a></p></div>
        <div id="comments"><p>Update 99.99: <a href="https://1fichier.com/?spam">Spam</a></p></div>'''
        rows = parse_source(body, SOURCE)
        self.assertEqual(len(rows), 4)
        self.assertNotIn('version', rows[0])
        self.assertEqual(rows[1]['version'], '1.17')
        self.assertEqual(rows[1]['firmware'], '5.05/9.00')
        self.assertEqual(rows[2]['kind'], 'dlc')
        self.assertNotIn('version', rows[2])
        self.assertEqual(rows[3]['title_id'], 'CUSA99999')

    def test_public_encoded_labels_and_mirror_details(self):
        data = '<p>CUSA12345 – EUR</p><p>Game: <a href="https://www.mediafire.com/file/abc/Game_CUSA12345_v1.00_[9.00].rar/file">Mirror</a> <a href="https://1fichier.com/?same">Mirror</a></p>'
        encoded = base64.b64encode(data.encode()).decode()
        rows = parse_source('<div class="entry-content"><p><div>Ad</div><div class="secure-data" data-payload="' + encoded + '">Loading</div></div>', SOURCE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['version'], '1.00')
        self.assertEqual(rows[1]['firmware'], '9.00')

    def test_no_version_guesses_or_hidden_filecrypt(self):
        self.assertEqual(filename_details('https://1fichier.com/?v1.23'), {})
        self.assertNotIn('kind', filename_details('https://www.mediafire.com/file/id/Title_v1.00.rar/file'))
        rows = parse_source('<div class="entry-content"><p>Game: <a href="https://filecrypt.cc/Container/X.html">Mirror</a> <a href="https://1fichier.com.evil.test/?x">Fake</a></p></div>', SOURCE)
        self.assertEqual(rows, [])

    def test_conflicting_row_and_filename_version(self):
        rows = parse_source('<div class="entry-content"><p>Update 1.17: <a href="https://www.mediafire.com/file/id/Update_v1.09.rar/file">File</a></p></div>', SOURCE)
        self.assertNotIn('version', rows[0])
        self.assertTrue(rows[0]['conflict'])


if __name__ == '__main__':
    unittest.main()
