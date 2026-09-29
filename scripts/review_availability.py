#!/usr/bin/env python3
"""Finite, checkpointed public-file availability review; never fetch file bodies."""
import collections
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from check_links import inspect as inspect_page
from file_sizes import inspect as inspect_api, NoRedirect, now, size_number

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = {'mediafire.com', 'mega.nz', 'vikingfile.com', 'pixeldrain.com', '1fichier.com'}

def mega_handle(url):
    p = urllib.parse.urlsplit(url)
    m = re.fullmatch(r'/file/([A-Za-z0-9_-]{8})/?', p.path)
    if not m:
        m = re.match(r'^!([A-Za-z0-9_-]{8})!', p.fragment)
    return m[1] if m else None

def mega_result(value):
    # MEGA SDK API_ENOENT only. Access/quota/temporary errors are not deletion.
    if value == -9:
        return {'status':'missing', 'reason':'MEGA API explicitly reports resource does not exist (-9)'}
    if isinstance(value, dict) and size_number(value.get('s')) is not None:
        return {'status':'present', 'reason':'MEGA file metadata exists; download not verified'}
    return {'status':'unknown', 'reason':'MEGA did not confirm file availability'}

def check(url, host):
    if host == 'mediafire.com':
        return inspect_page(url)
    if host != 'mega.nz':
        result = inspect_api(url, api_key=os.environ.get('FICHIER_API_KEY',''))
        status = result['status']
        return {'status': 'present' if status == 'known' else status,
                'reason': result.get('reason', 'Host API returned file metadata; download not verified')}
    handle = mega_handle(url)
    if not handle:
        return {'status':'unsupported','reason':'Folder or unsupported MEGA URL; no deletion inferred'}
    # Official SDK command g without the g=1 flag requests information only.
    req = urllib.request.Request('https://g.api.mega.co.nz/cs',
        data=json.dumps([{'a':'g','p':handle}]).encode(),
        headers={'Content-Type':'application/json','User-Agent':'PS4CatalogueAvailability/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            if response.headers.get_content_type() != 'application/json':
                return {'status':'held','reason':'MEGA returned unexpected content type'}
            raw = response.read(65537)
            if len(raw)>65536: return {'status':'unknown','reason':'Metadata response exceeded limit'}
            value = json.loads(raw)
            return mega_result(value[0] if isinstance(value,list) and len(value)==1 else None)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return {'status':'held','reason':'MEGA metadata request failed; file status unknown'}

def run():
    state_path = ROOT/'availability-review.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'checked':{},'holds':{}}
    links_path = ROOT/'link-status.json'
    manifest = json.loads(links_path.read_text())
    sizes = json.loads((ROOT/'file-sizes.json').read_text())
    # Existing repeated API denial is retained; no retry loop or alternate route.
    if sizes.get('holds',{}).get('1fichier.com'):
        state['holds']['1fichier.com'] = sizes['holds']['1fichier.com']
    candidates = json.loads(subprocess.check_output(['node',str(ROOT/'scripts/size_candidates.cjs')],text=True))
    queues = collections.defaultdict(list)
    cutoff = (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=24)).isoformat()
    recent = 0
    for item in candidates:
        url, host = item['url'], item['host']
        host = host.removeprefix('www.')
        if host == 'vik1ngfile.site': host='vikingfile.com'
        if host not in SUPPORTED: continue
        previous = sizes.get('files',{}).get(url,{})
        if previous.get('status')=='missing' or manifest['links'].get(url,{}).get('status')=='missing': continue
        if host in ('vikingfile.com','pixeldrain.com','1fichier.com') and previous.get('status')=='known' and previous.get('checked_at','')>=cutoff:
            recent += 1; continue
        if url not in state['checked']: queues[host].append(url)
    deadline = time.monotonic() + (120 if os.environ.get('EVENT')=='push' else 840)
    def worker(host, urls):
        results={}; hold=None
        if host in state['holds']: return host,results,hold
        unknowns=0
        for url in urls:
            if time.monotonic() >= deadline: break
            result=check(url,host); result['checked_at']=now(); result['source']='host availability review'
            results[url]=result
            unknowns=unknowns+1 if result['status']=='unknown' else 0
            if result['status'] in ('held','restricted','rate_limited') or unknowns>=3 or result.get('reason','').startswith('Network check failed'):
                hold={'reason':result['reason'],'at':now()}; break
            time.sleep(10 if host=='1fichier.com' else 5)
        return host,results,hold
    attempted=0; found=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for host,results,hold in pool.map(lambda pair:worker(*pair),queues.items()):
            state['checked'].update(results); attempted+=len(results)
            if hold: state['holds'][host]=hold
            for url,result in results.items():
                if result['status']=='missing':
                    manifest['links'][url]=result; found+=1
            print(json.dumps({'host':host,'attempted':len(results),'results':dict(collections.Counter(v['status'] for v in results.values())),'hold':hold}),flush=True)
    pending=sum(sum(url not in state['checked'] for url in urls) for host,urls in queues.items() if host not in state['holds'])
    state.update(updated_at=now(),summary={'attempted_total':len(state['checked']),'attempted_batch':attempted,'new_missing_batch':found,'results':dict(collections.Counter(v['status'] for v in state['checked'].values())),'recent_api_checks_reused':recent,'runnable_remaining':pending})
    manifest['updated_at']=now()
    state_path.write_text(json.dumps(state,separators=(',',':'))+'\n')
    links_path.write_text(json.dumps(manifest,separators=(',',':'))+'\n')
    (ROOT/'link-status.js').write_text('var linkStatuses = '+json.dumps(manifest,separators=(',',':'))+';\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f: f.write('continue='+str(pending>0 and attempted>0).lower()+'\n')
    print(json.dumps(state['summary']))

if __name__=='__main__': run()
