#!/usr/bin/env python3
"""Checkpointed metadata-only size collection. Never request download tokens or file bodies."""
import argparse
import collections
import concurrent.futures
import datetime
import decimal
import email.message
import html
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from check_links import VisibleText

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAX_BODY = 768 * 1024
UA = 'PS4CatalogueFileMetadata/1.0 (metadata only)'
PAGE_HOSTS = {'mediafire.com', 'akirabox.com', 'akirabox.to', 'filekeeper.net', 'rootz.so', 'ranoz.gg', 'datanodes.to', 'filefactory.com', 'mocha.my'}
API_HOSTS = {'vikingfile.com', 'pixeldrain.com', '1fichier.com'}
FILE_NAME = re.compile(r'\.(?:pkg|rar|zip|7z|iso|bin|part\d+|\d{3})$', re.I)

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def family(url):
    host=(urllib.parse.urlsplit(url).hostname or '').lower().removeprefix('www.')
    return 'vikingfile.com' if host=='vik1ngfile.site' else host

def clean_name(value):
    if not isinstance(value,str): return None
    value = html.unescape(value).strip()
    return value[:512] if value and not re.search(r'[\x00-\x1f]',value) else None

def url_name(url):
    for part in reversed(urllib.parse.urlsplit(url).path.split('/')):
        name = clean_name(urllib.parse.unquote(part))
        if name and FILE_NAME.search(name): return name
    return None

def size_number(value):
    if isinstance(value,bool): return None
    if isinstance(value,int) or isinstance(value,str) and re.fullmatch(r'\d+',value):
        n=int(value)
        return n if 0 <= n <= 2**53-1 else None
    return None

def display_size(value):
    """Rounded webpage quantities stay estimates; GB means decimal, GiB binary."""
    if not isinstance(value,str): return None
    m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(bytes?|[KMGT]i?B)\s*',value,re.I)
    if not m: return None
    unit=m[2].upper()
    power=0 if unit.startswith('B') else 'KMGT'.index(unit[0])+1
    n=int(decimal.Decimal(m[1]) * (1024 if 'I' in unit else 1000)**power)
    return {'size_bytes':n,'size_precision':'exact' if power==0 and '.' not in m[1] else 'estimated','size_display':value.strip()} if n<=2**53-1 else None

def multipart(name):
    if not name: return {}
    m=re.search(r'(?i)^(.*)\.part(\d+)\.rar$',name)
    if not m: m=re.search(r'(?i)^(.*\.(?:7z|zip|pkg))\.(\d{3})$',name)
    return {'multipart_group':m[1], 'part_number':int(m[2]), 'multipart_evidence':'filename; total part count unknown'} if m else {}

def from_api(host, data):
    if not isinstance(data,dict): return {'status':'unknown','reason':'Unexpected metadata response'}
    if host=='1fichier.com' and data.get('status')=='KO':
        message=data.get('message','')
        if isinstance(message,str) and re.fullmatch(r'Resource not found #\d+',message,re.I):
            return {'status':'missing','reason':'1fichier API explicitly reports resource not found','evidence':'host API'}
        if isinstance(message,str) and re.fullmatch(r'Resource not allowed #\d+',message,re.I):
            return {'status':'restricted_file','reason':'File access is restricted; not evidence of deletion','evidence':'host API'}
    if host=='vikingfile.com' and data.get('exist') is False:
        return {'status':'missing','reason':'Host API explicitly reports file absent'}
    if host=='pixeldrain.com' and data.get('success') is False and data.get('value')=='not_found':
        return {'status':'missing','reason':'Host API explicitly reports file absent'}
    ok=(data.get('exist') is True if host=='vikingfile.com' else data.get('success') is True if host=='pixeldrain.com' else data.get('status') in (None,'OK') and clean_name(data.get('filename')) is not None and size_number(data.get('size')) is not None)
    if not ok: return {'status':'unknown','reason':'Host did not return successful file metadata','response_schema':{k:type(data.get(k)).__name__ for k in ('status','filename','name','size','checksum')}}
    name=clean_name(data.get('filename') or data.get('name'))
    n=size_number(data.get('size'))
    result={'status':'known' if n is not None else 'unknown','evidence':'host API','size_precision':'exact'}
    if n is not None: result['size_bytes']=n
    if name: result.update(filename=name,filename_evidence='host API',**multipart(name))
    for alg,length in [('sha256',64),('sha1',40),('md5',32),('whirlpool',128)]:
        value=data.get('checksum') if host=='1fichier.com' and alg=='whirlpool' else data.get(alg)
        if isinstance(value,str) and re.fullmatch('[0-9a-fA-F]{'+str(length)+'}',value):
            result.setdefault('checksums',{})[alg]=value.lower()
    return result

def akira_metadata(body,url):
    # Decode inert JSON strings only. Never evaluate the scripts embedded in a host page.
    file_id=urllib.parse.urlsplit(url).path.strip('/').split('/')[0]
    decoder=json.JSONDecoder()
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>',body,re.S):
        try: flight=json.loads(match[1])
        except ValueError: continue
        if not isinstance(flight,list) or len(flight)<2 or not isinstance(flight[1],str): continue
        for start in re.finditer(r'"file"\s*:\s*(?=\{)',flight[1]):
            try: item,_=decoder.raw_decode(flight[1][start.end():])
            except ValueError: continue
            if item.get('id')!=file_id or item.get('kind')!='file': continue
            n=size_number(item.get('size'));name=clean_name(item.get('name'));ext=clean_name(item.get('extension'))
            if n is None or not name: continue
            if ext and not name.lower().endswith('.'+ext.lower()): name+='.'+ext
            return dict(status='known',size_bytes=n,size_precision='exact',filename=name,
                        evidence='host embedded file metadata',filename_evidence='host embedded file metadata',**multipart(name))
    return None

def from_html(body):
    parser=VisibleText(); parser.feed(body)
    lines=[re.sub(r'\s+',' ',p).strip() for p in parser.parts if p.strip()]
    text=' '.join(lines)
    if any(t in text.lower() for t in ('verify you are human','checking your browser','access denied','professional infrastructure','just a moment...')):
        return {'status':'held','reason':'Host challenge or access restriction'}
    if any(t in text.lower() for t in ('site unavailable','unable to access this site')):
        return {'status':'held','reason':'Network gateway unavailable'}
    result={'status':'unknown','reason':'No unambiguous file-size metadata','evidence':'host page'}
    # Explicit File size label, never a random GB token, quota, banner or Content-Length of HTML.
    sizes=[]
    for i,line in enumerate(lines):
        m=re.fullmatch(r'(?i)File\s*size\s*:?\s*(.*)',line)
        if m:
            value=m[1] or (lines[i+1] if i+1<len(lines) else '')
            value=value.lstrip(': ').strip()
            parsed=display_size(value)
            if parsed: sizes.append(parsed)
    if sizes and len({s['size_bytes'] for s in sizes})==1:
        result.update(sizes[0],status='known');result.pop('reason',None)
    # Structured contentSize has explicit semantics. Don't inspect arbitrary JS objects.
    for raw in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',body,re.I|re.S):
        try: obj=json.loads(raw)
        except ValueError: continue
        if isinstance(obj,dict) and obj.get('@type') in ('MediaObject','DigitalDocument','DataDownload','SoftwareApplication'):
            s=display_size(obj.get('contentSize'))
            if s and 'size_bytes' not in result: result.update(s,status='known');result.pop('reason',None)
            n=clean_name(obj.get('name'))
            if n and FILE_NAME.search(n): result.update(filename=n,filename_evidence='host structured metadata',**multipart(n))
    names=[line for line in lines if len(line)<513 and FILE_NAME.search(line) and not line.lower().startswith(('download ','http','www.'))]
    if len(set(names))==1: result.update(filename=names[0],filename_evidence='host page',**multipart(names[0]))
    return result

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class MetadataRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections=3
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old,new=urllib.parse.urlsplit(req.full_url),urllib.parse.urlsplit(newurl)
        allowed=(old.hostname or '').removeprefix('www.')=='akirabox.com' and (new.hostname or '').removeprefix('www.')=='akirabox.to' and old.path==new.path
        if allowed and new.scheme=='https' and not new.username and not new.password:
            return super().redirect_request(req,fp,code,msg,headers,newurl)
        return None

def inspect(url, api_key='', opener=None):
    host=family(url); p=urllib.parse.urlsplit(url)
    headers={'User-Agent':UA,'Accept':'application/json,text/html','Accept-Encoding':'identity'}
    body=None; target=url
    if host=='vikingfile.com':
        m=re.fullmatch(r'/f/([a-zA-Z0-9]+)',p.path.rstrip('/'))
        if not m: return {'status':'unsupported','reason':'Not a single-file URL'}
        target='https://vikingfile.com/api/check-file'; body=urllib.parse.urlencode({'hash':m[1]}).encode(); headers['Content-Type']='application/x-www-form-urlencoded'
    elif host=='pixeldrain.com':
        m=re.fullmatch(r'/u/([a-zA-Z0-9]+)',p.path.rstrip('/'))
        if not m: return {'status':'unsupported','reason':'Not a single-file URL'}
        target='https://pixeldrain.com/api/file/'+m[1]+'/info'
    elif host=='1fichier.com':
        if not api_key: return {'status':'held','reason':'1fichier API key not configured; public access previously restricted'}
        target='https://api.1fichier.com/v1/file/info.cgi';body=json.dumps({'url':url}).encode();headers.update({'Content-Type':'application/json','Authorization':'Bearer '+api_key})
    elif host not in PAGE_HOSTS: return {'status':'unsupported','reason':'No metadata adapter for this host or container'}
    req=urllib.request.Request(target,data=body,headers=headers)
    try:
        op=opener or urllib.request.build_opener(NoRedirect() if host in API_HOSTS else MetadataRedirects())
        try: response=op.open(req,timeout=20)
        except urllib.error.HTTPError as exc: response=exc
        with response:
            code=response.code
            if code==403 and host=='1fichier.com' and response.headers.get_content_type()=='application/json':
                try:
                    result=from_api(host,json.loads(response.read(MAX_BODY).decode('utf-8','replace')))
                    if result['status'] in ('missing','restricted_file'): return result
                except ValueError: pass
                return {'status':'held','reason':'1fichier API access restriction (HTTP 403)'}
            if code in (401,403,429) or code>=500: return {'status':'held','reason':'Host or network restriction (HTTP '+str(code)+')'}
            if 300<=code<400: return {'status':'unknown','reason':'Redirect not followed; no file fetched'}
            kind=response.headers.get_content_type()
            if kind not in ('application/json','text/html','application/xhtml+xml','text/plain'):
                return {'status':'unknown','reason':'Binary response closed without reading body'}
            if 'attachment' in response.headers.get('Content-Disposition','').lower():
                return {'status':'unknown','reason':'Attachment response closed without reading body'}
            raw=response.read(MAX_BODY+1)
            if len(raw)>MAX_BODY: return {'status':'unknown','reason':'Metadata page exceeded size limit'}
            raw=raw.decode('utf-8','replace')
            if host in API_HOSTS:
                try:
                    payload=json.loads(raw)
                    if host=='vikingfile.com' and isinstance(payload,list):
                        matches=[v for v in payload if isinstance(v,dict) and v.get('hash')==m[1]]
                        payload=matches[0] if len(matches)==1 else None
                    return from_api(host,payload)
                except ValueError: return {'status':'held','reason':'Metadata API returned a non-JSON response'}
            if code!=200: return {'status':'unknown','reason':'HTTP error alone does not prove deletion'}
            return (akira_metadata(raw,url) if host in ('akirabox.com','akirabox.to') else None) or from_html(raw)
    except Exception as exc:
        return {'status':'held','reason':'Metadata request failed ('+type(exc).__name__+')'}

def atomic(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(value);tmp.replace(path)

def run(root, limit=3000, minutes=15):
    candidates=json.loads(subprocess.check_output(['node',str(root/'scripts/size_candidates.cjs')],text=True))
    path=root/'file-sizes.json'
    data=json.loads(path.read_text()) if path.exists() else {'schema':1,'files':{},'holds':{}}
    files=data['files']; holds=data.setdefault('holds',{})
    if data.get('adapter_revision',1)<2:
        # Revisit only results affected by verified parser fixes, preserving valid data.
        for url,value in list(files.items()):
            if family(url) in ('vikingfile.com','akirabox.com','akirabox.to') and value.get('status')=='unknown': files.pop(url)
        data['adapter_revision']=2
    if data.get('adapter_revision',1)<3:
        for url,value in list(files.items()):
            if family(url)=='1fichier.com' and value.get('status')=='unknown': files.pop(url)
        data['adapter_revision']=3
    if data.get('adapter_revision',1)<4:
        for url,value in list(files.items()):
            if family(url)=='1fichier.com' and value.get('status')=='unknown': files.pop(url)
        if 'adapter needs review' in holds.get('1fichier.com',{}).get('reason',''): holds.pop('1fichier.com')
        data['adapter_revision']=4
    keys={c['url'] for c in candidates}
    data['files']=files={k:v for k,v in files.items() if k in keys}
    queues=collections.defaultdict(list); api_key=os.environ.get('FICHIER_API_KEY','')
    for item in candidates:
        url=item['url']; host=family(url)
        if files.get(url,{}).get('status'): continue
        name=url_name(url)
        if name: files.setdefault(url,{}).update(filename=name,filename_evidence='URL filename',**multipart(name))
        if host not in PAGE_HOSTS|API_HOSTS:
            files[url]={'status':'unsupported','reason':'Metadata adapter unavailable; container or unsupported host'}
            if name: files[url].update(filename=name,filename_evidence='URL filename',**multipart(name))
        else: queues[host].append(url)
    if not api_key: holds.setdefault('1fichier.com',{'reason':'API key not configured; public access previously restricted','at':now()})
    elif holds.get('1fichier.com',{}).get('reason','').startswith('API key not configured'): holds.pop('1fichier.com')
    # Previous access restrictions stay paused instead of retrying every batch.
    holds.setdefault('mediafire.com',{'reason':'Prior metadata pass hit network restriction','at':now()})
    priority_path=root/'file-size-priority.json'
    priority=set(json.loads(priority_path.read_text())) if priority_path.exists() else set()
    for urls in queues.values(): urls.sort(key=lambda u: u not in priority)
    deadline=time.monotonic()+minutes*60
    host_budget=max(1,limit//max(1,len([h for h in queues if h not in holds])))
    def worker(host,urls):
        results={}; hold=None; unresolved=0
        if host in holds: return host,results,hold
        for url in urls[:host_budget]:
            if time.monotonic()>=deadline: break
            value=inspect(url,api_key=api_key)
            value['checked_at']=now()
            n=url_name(url)
            if n and not value.get('filename'): value.update(filename=n,filename_evidence='URL filename',**multipart(n))
            results[url]=value
            if value['status']=='held':
                hold={'reason':value['reason'],'at':now()};break
            unresolved = unresolved+1 if value['status']=='unknown' else 0
            if unresolved>=3:
                hold={'reason':'Three pages returned no usable metadata; host adapter needs review','at':now()};break
            time.sleep(3)
        return host,results,hold
    attempted=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(worker,h,urls) for h,urls in queues.items()]
        for task in concurrent.futures.as_completed(futures):
            host,results,hold=task.result();files.update(results);attempted+=len(results)
            if hold: holds[host]=hold
            print(json.dumps({'host':host,'attempted':len(results),'known':sum(v['status']=='known' for v in results.values()),'held':bool(hold)}),flush=True)
    states=collections.Counter();by_host={}
    for item in candidates:
        host=family(item['url']);v=files.get(item['url'],{})
        state=v.get('status','held' if host in holds else 'pending')
        states[state]+=1
        by_host.setdefault(host,collections.Counter())[state]+=1
    known=[v for v in files.values() if v.get('status')=='known' and 'size_bytes' in v]
    data.update(updated_at=now(),summary={'unique_urls':len(candidates),'attempted_this_batch':attempted,'states':dict(states),'known_bytes_all_urls':sum(v['size_bytes'] for v in known),'exact_sizes':sum(v.get('size_precision')=='exact' for v in known),'hosts':by_host,'note':'Known bytes include mirrors, regions and older versions; not unique game storage. Checksums are host-reported, not locally verified.'})
    raw=json.dumps(data,ensure_ascii=True,separators=(',',':'))
    atomic(path,raw+'\n');atomic(root/'file-sizes.js','var fileSizes = '+raw+';\n')
    out=os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out,'a') as f:f.write('continue='+str(states['pending']>0 and attempted>0).lower()+'\n')
    print(json.dumps(data['summary'],indent=2))
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--limit',type=int,default=3000);p.add_argument('--minutes',type=int,default=15);a=p.parse_args()
    if not 1<=a.limit<=5000 or not 1<=a.minutes<=20:p.error('limit 1–5000; minutes 1–20')
    run(ROOT,a.limit,a.minutes)
