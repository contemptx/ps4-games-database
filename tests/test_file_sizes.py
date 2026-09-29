import sys
import pathlib
import unittest
from email.message import Message
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from file_sizes import display_size, from_api, from_html, inspect, multipart, url_name

class FileSizesTest(unittest.TestCase):
    def test_units_and_false_positives(self):
        self.assertEqual(display_size('2 GiB')['size_bytes'],2147483648)
        self.assertEqual(display_size('2 GB')['size_bytes'],2000000000)
        self.assertEqual(display_size('2048 bytes')['size_precision'],'exact')
        for s in ('Unlimited','2 GB free','-1 GB','NaN MB'): self.assertIsNone(display_size(s))
        self.assertNotIn('size_bytes',from_html('<p>Upload files up to 100 GB</p>'))
        self.assertEqual(from_html('<div>File size:</div><b>12.4 GB</b>')['size_bytes'],12400000000)
        self.assertNotIn('size_bytes',from_html('<p>File size: 1 GB</p><p>File size: 2 GB</p>'))
    def test_host_results(self):
        self.assertEqual(from_api('vikingfile.com',{'exist':True,'size':0,'name':'empty.pkg'})['size_bytes'],0)
        self.assertEqual(from_api('vikingfile.com',{'exist':False})['status'],'missing')
        self.assertEqual(from_api('pixeldrain.com',{'success':False,'value':'not_found'})['status'],'missing')
        self.assertEqual(from_api('1fichier.com',{'status':'KO','size':400})['status'],'unknown')
        d=from_api('pixeldrain.com',{'success':True,'size':1500,'name':'a.part02.rar','sha256':'a'*64,'md5':'not-a-hash','download_url':'secret','token':'secret'})
        self.assertEqual(d['part_number'],2)
        self.assertEqual(d['checksums'],{'sha256':'a'*64})
        self.assertNotIn('token',d);self.assertNotIn('download_url',d)
    def test_names(self):
        self.assertEqual(url_name('https://filekeeper.net/id/Game.pkg'),'Game.pkg')
        self.assertEqual(multipart('game.7z.003')['part_number'],3)
        self.assertEqual(multipart('game_v1.03.pkg'),{})
    def test_missing_key_and_unknown_hosts_never_contacted(self):
        class Never:
            def open(self,*a,**kw):raise AssertionError('Must not call network')
        self.assertEqual(inspect('https://1fichier.com/?abc',opener=Never())['status'],'held')
        self.assertEqual(inspect('https://localhost/file',opener=Never())['status'],'unsupported')
    def test_binary_body_never_read_and_html_length_not_file_size(self):
        class Response:
            code=200
            def __init__(self,ct):self.headers=Message();self.headers['Content-Type']=ct;self.headers['Content-Length']='99999999'
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):
                if self.headers['Content-Type']=='application/octet-stream':raise AssertionError('Read binary file')
                return b'<p>Ordinary page</p>'
        class Opener:
            def __init__(self,ct):self.ct=ct
            def open(self,*a,**kw):return Response(self.ct)
        for ct in ['application/octet-stream','text/html']:
            self.assertNotIn('size_bytes',inspect('https://filekeeper.net/id/file.pkg',opener=Opener(ct)))
    def test_challenge_does_not_mark_deleted(self):
        self.assertEqual(from_html('<p>Verify you are human</p>')['status'],'held')

if __name__=='__main__': unittest.main()
