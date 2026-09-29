#!/usr/bin/env python3
"""Representative download tests: up to 1 MiB per host, never execute content."""
import concurrent.futures,hashlib,html.parser,json,re,subprocess,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from check_links import VisibleText
from review_availability import mega_handle
ROOT=Path(__file__).resolve().parents[1]
CAP=1024*1024
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
class Anchors(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href') and (a.get('id')=='downloadButton' or a.get('download') is not None):
            self.links.append(a['href'])
def request(url,body=None,headers=None):
    req=urllib.request.Request(url,data=body,headers=headers or {'User-Agent':'PS4CatalogueDownloadTest/1.0'})
    op=urllib.request.build_opener(NoRedirect())
    try:r=op.open(req,timeout=20)
    except urllib.error.HTTPError as e:r=e
    with r:
        return r.code,r.headers,r.read(CAP)
def transfer(url,domains):
    p=urllib.parse.urlsplit(url);h=p.hostname or ''
    if p.scheme!='https' or p.username or p.password or not any(h==d or h.endswith('.'+d) for d in domains):
        return {'result':'unverified','reason':'Download points to a destination outside the tested host'}
    code,headers,body=request(url,headers={'User-Agent':'PS4CatalogueDownloadTest/1.0','Range':'bytes=0-1048575'})
    content=headers.get_content_type()
    if code in (200,206) and body and content not in ('text/html','application/xhtml+xml','application/json','text/plain'):
        total=headers.get('Content-Range','').split('/')[-1]
        length=headers.get('Content-Length','')
        full=(code==200 and length.isdigit() and int(length)==len(body)) or (code==206 and total.isdigit() and int(total)==len(body))
        return {'result':'downloaded','bytes_received':len(body),'complete_file':full,'content_type':content,'sample_sha256':hashlib.sha256(body).hexdigest()}
    return {'result':'unverified','http_status':code,'content_type':content,'reason':'No file bytes verified'}
def test(item):
    host,url=item['host'],item['url']
    out={'host':host,'sample_url':url}
    if host in ('akirabox.com','akirabox.to','vikingfile.com','vik1ngfile.site'):
        return dict(out,result='captcha_blocked',reason='Previously observed browser verification barrier; not retried')
    if host=='1fichier.com':
        return dict(out,result='previously_verified',bytes_received=84065,complete_file=True,reason='CDN API download verified in dedicated test')
    try:
        if host=='pixeldrain.com':
            m=re.fullmatch(r'/u/([A-Za-z0-9]+)',urllib.parse.urlsplit(url).path)
            return dict(out,**transfer('https://pixeldrain.com/api/file/'+m[1],['pixeldrain.com'])) if m else dict(out,result='container')
        if host=='mega.nz':
            handle=mega_handle(url)
            if not handle:return dict(out,result='container',reason='Folder or unsupported link')
            code,headers,raw=request('https://g.api.mega.co.nz/cs',json.dumps([{'a':'g','p':handle,'g':1,'ssl':2}]).encode(),{'Content-Type':'application/json'})
            try:d=json.loads(raw)[0]
            except (ValueError,IndexError,TypeError):d=None
            if isinstance(d,dict) and isinstance(d.get('g'),str):
                return dict(out,**transfer(d['g'],['mega.co.nz','mega.nz']),note='MEGA bytes are encrypted; decryption not tested')
            return dict(out,result='missing' if d==-9 else 'unverified',http_status=code,reason='MEGA did not issue a download URL')
        code,headers,raw=request(url)
        if 300<=code<400:
            location=urllib.parse.urljoin(url,headers.get('Location',''))
            p=urllib.parse.urlsplit(location);h=p.hostname or ''
            if p.scheme=='https' and (h==host or h.endswith('.'+host) or host.endswith('.'+h)):
                code,headers,raw=request(location);url=location
            else:return dict(out,result='redirect',http_status=code,reason='Redirect to another host requires its own download flow')
        content=headers.get_content_type()
        if code in (200,206) and content not in ('text/html','application/xhtml+xml','text/plain','application/json') and raw:
            return dict(out,result='downloaded',bytes_received=len(raw),complete_file=False,content_type=content)
        body=raw.decode('utf-8','replace'); parser=VisibleText();parser.feed(body);text=' '.join(parser.parts).lower()
        if any(x in text for x in ('verify you are human','checking your browser','just a moment','captcha')):
            return dict(out,result='captcha_blocked',http_status=code)
        if code>=400:return dict(out,result='http_error',http_status=code,reason='Status alone does not prove deletion')
        a=Anchors();a.feed(body)
        if a.links:return dict(out,**transfer(urllib.parse.urljoin(url,a.links[0]),[host]))
        return dict(out,result='interactive_or_container',http_status=code,reason='Landing page loaded; no direct file transfer verified')
    except Exception as e:
        return dict(out,result='network_error',error_type=type(e).__name__)
def main():
    candidates=json.loads(subprocess.check_output(['node',str(ROOT/'scripts/size_candidates.cjs')],text=True))
    sizes=json.loads((ROOT/'file-sizes.json').read_text())['files']
    audit=json.loads((ROOT/'availability-review.json').read_text()).get('checked',{}) if (ROOT/'availability-review.json').exists() else {}
    by_host={}
    for item in candidates:
        host=item['host'].removeprefix('www.');item=dict(item,host=host)
        r=sizes.get(item['url'],{})
        if r.get('status')=='missing' or audit.get(item['url'],{}).get('status')=='missing':continue
        priority=(0 if r.get('status')=='known' else 1,r.get('size_bytes',10**20))
        if host=='mega.nz' and not mega_handle(item['url']):priority=(3,0)
        if host not in by_host or priority<by_host[host][0]:by_host[host]=(priority,item)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(test,[x[1] for x in by_host.values()]))
    for r in results:print(json.dumps(r),flush=True)
    (ROOT/'host-download-tests.json').write_text(json.dumps({'scope':'One representative per host; up to 1 MiB per transfer. Not a verdict on every link.','results':results},indent=2))
if __name__=='__main__':main()
