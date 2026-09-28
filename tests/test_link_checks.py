import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('checker', pathlib.Path(__file__).resolve().parents[1] / 'scripts/check_links.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class LinkChecks(unittest.TestCase):
    def test_explicit_missing_message(self):
        for code in (200, 404, 410):
            with self.subTest(code=code):
                self.assertEqual(checker.classify('https://1fichier.com/?abc', code,
                    '<p>The requested file does not exist</p><p>It could be deleted by its owner.</p>')[0], 'missing')

    def test_ambiguous_responses_are_not_missing(self):
        for code, body in [(200, '<h1>Site Unavailable</h1><p>Unable to access this site.</p>'),
                           (404, '<h1>Not Found</h1>'), (500, 'The requested file does not exist'),
                           (200, '<script>The requested file does not exist</script><p>Hello</p>')]:
            with self.subTest(code=code, body=body):
                self.assertEqual(checker.classify('https://1fichier.com/?abc', code, body)[0], 'unknown')

    def test_rate_limits_and_access_blocks_take_priority(self):
        for code, body, expected in [(429, 'The requested file does not exist', 'rate_limited'),
                                      (200, 'Too Many Requests', 'rate_limited'),
                                      (403, 'The requested file does not exist', 'restricted'),
                                      (200, 'Access restricted – professional infrastructure detected', 'restricted'),
                                      (200, 'Please complete the CAPTCHA', 'restricted')]:
            with self.subTest(code=code, body=body):
                self.assertEqual(checker.classify('https://1fichier.com/?abc', code, body)[0], expected)

    def test_mediafire_and_filecrypt_have_separate_evidence(self):
        self.assertEqual(checker.classify('https://www.mediafire.com/file/abc', 200,
            '<h1>The file you requested has been deleted</h1>')[0], 'missing')
        self.assertEqual(checker.classify('https://www.mediafire.com/file/abc', 200,
            '<a id="downloadButton">Download</a>')[0], 'present')
        self.assertEqual(checker.classify('https://filecrypt.cc/Container/abc.html', 200,
            '<h1>Container</h1>')[0], 'unknown')

    def test_affiliate_variants_share_identity(self):
        self.assertEqual(checker.status_key('//1fichier.com/?ABC123?&af=123'), 'https://1fichier.com/?abc123')
        self.assertEqual(checker.status_key('https://www.mediafire.com/file/abc123/File Name.zip/file'), 'https://www.mediafire.com/file/abc123')
        rows = [{'name': 'Game', 'download_links': {'mediafire': [], '1file': [
            'https://1fichier.com/?abc123', 'https://1fichier.com/?abc123&af=456'], 'other': []}}]
        self.assertEqual(len(checker.candidates(rows)), 1)

    def test_unknown_retry_preserves_confirmed_missing(self):
        old = {'status': 'missing', 'source': 'user screenshot'}
        result = checker.merge_result(old, {'status': 'restricted'})
        self.assertEqual(result['status'], 'missing')
        self.assertEqual(result['last_attempt']['status'], 'restricted')
        self.assertEqual(checker.merge_result(old, {'status': 'present'})['status'], 'present')

    def test_host_scope(self):
        self.assertIsNone(checker.host_family('https://1fichier.com.evil.test/?abc'))
        self.assertIsNone(checker.host_family('https://user:password@1fichier.com/?abc'))
        self.assertIsNone(checker.host_family('file:///tmp/example'))


if __name__ == '__main__':
    unittest.main()
