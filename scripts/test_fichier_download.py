#!/usr/bin/env python3
"""One small-file API download diagnostic. Never log credentials or signed URLs."""
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAX_BYTES=10*1024*1024
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def main():
    key=os.environ.get('FICHIER_API_KEY','')
    if not key: print(json.dumps({'result':'blocked','reason':'API key unavailable'})); return
    data=json.loads((Path(__file__).resolve().parents[1]/'file-sizes.json').read_text())
    candidates=[(r['size_bytes'],u,r) for u,r in data['files'].items()
                if urllib.parse.urlsplit(u).hostname=='1fichier.com' and r.get('status')=='known'
                and isinstance(r.get('size_bytes'),int) and 0<r['size_bytes']<=MAX_BYTES]
    if not candidates: print(json.dumps({'result':'blocked','reason':'No known small file available'})); return
    size,url,record=min(candidates,key=lambda x:x[0])
    print(json.dumps({'stage':'selected','public_url':url,'expected_bytes':size}),flush=True)
    request=urllib.request.Request('https://api.1fichier.com/v1/download/get_token.cgi',
        data=json.dumps({'url':url,'cdn':1,'single':1}).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'PS4CatalogueDownloadTest/1.0'})
    opener=urllib.request.build_opener(NoRedirect())
    try:
        try: response=opener.open(request,timeout=30)
        except urllib.error.HTTPError as error: response=error
        with response:
            code=response.code
            raw=response.read(65537)
        try: token=json.loads(raw) if len(raw)<=65536 else {}
        except ValueError: token={}
        if not isinstance(token,dict): token={}
        if code!=200 or token.get('status')!='OK' or not isinstance(token.get('url'),str):
            message=token.get('message','')
            message=message if isinstance(message,str) else ''
            categories=[name for name,pattern in [('rate_limit',r'limit|flood|too many'),('cdn_required',r'cdn|professional infrastructure'),('account_access',r'premium|access|allowed|banned|blocked|locked'),('missing_file',r'not found|not exist')] if re.search(pattern,message,re.I)]
            error_id=re.search(r'#(\d+)',message)
            print(json.dumps({'stage':'token','result':'failed','http_status':code,
                'api_status':token.get('status') if token.get('status') in ('OK','KO') else 'unknown',
                'error_code':error_id[1] if error_id else None,'categories':categories,
                'cdn_requested':True}),flush=True)
            return
        parsed=urllib.parse.urlsplit(token['url'])
        host=parsed.hostname or ''
        if parsed.scheme!='https' or parsed.username or parsed.password or not (host=='1fichier.com' or host.endswith('.1fichier.com')):
            print(json.dumps({'stage':'token','result':'blocked','reason':'Unexpected download destination; token not followed'})); return
        print(json.dumps({'stage':'token','result':'success','cdn_requested':True}),flush=True)
        # Separate request, without API authorization. Do not follow redirects.
        request=urllib.request.Request(token['url'],headers={'User-Agent':'PS4CatalogueDownloadTest/1.0'})
        with opener.open(request,timeout=30) as response:
            content_type=response.headers.get_content_type()
            if response.code!=200 or content_type in ('text/html','application/json'):
                print(json.dumps({'stage':'transfer','result':'failed','http_status':response.code,'content_type':content_type})); return
            digest=hashlib.sha256(); count=0; prefix=b''
            while count<=MAX_BYTES:
                chunk=response.read(min(65536,MAX_BYTES+1-count))
                if not chunk: break
                if not prefix: prefix=chunk[:8]
                count+=len(chunk); digest.update(chunk)
            magic='pkg' if prefix.startswith(b'\x7fCNT') else 'rar' if prefix.startswith(b'Rar!') else 'zip' if prefix.startswith(b'PK') else '7z' if prefix.startswith(b'7z\xbc\xaf\x27\x1c') else 'unidentified'
            print(json.dumps({'stage':'transfer','result':'success' if count==size and count<=MAX_BYTES else 'size_mismatch_or_limit',
                'bytes_received':count,'expected_bytes':size,'sha256':digest.hexdigest(),'file_signature':magic,
                'content_type':content_type,'executed':False}),flush=True)
    except Exception as error:
        # Exception messages may contain signed URLs. Emit type/status only.
        print(json.dumps({'result':'failed','error_type':type(error).__name__,'http_status':getattr(error,'code',None)}),flush=True)

if __name__=='__main__': main()
