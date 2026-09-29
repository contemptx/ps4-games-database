// File sizes are host-reported metadata, not verification of downloaded bytes.
var catalogSizes = (function() {
    var selected = Object.create(null), panel, totalNode, listingNode;
    function key(url) { return gameCatalog.statusKey(url); }
    function info(url) { return typeof fileSizes === 'object' && fileSizes.files && fileSizes.files[key(url)] || {}; }
    function known(m) { return m.status === 'known' && typeof m.size_bytes === 'number' && isFinite(m.size_bytes) && m.size_bytes >= 0; }
    function format(bytes) {
        var units = ['B','KB','MB','GB','TB','PB'], i=0;
        while (bytes>=1000 && i<units.length-1) { bytes/=1000; i++; }
        return bytes.toLocaleString('en-GB',{maximumFractionDigits:i ? 2 : 0})+' '+units[i];
    }
    function label(url) { var m=info(url); return known(m) ? (m.size_precision==='estimated' ? '≈ ' : '')+format(m.size_bytes) : 'Size unknown'; }
    function identity(url,m) {
        // Never collapse equal filenames/sizes alone, or confuse host IDs with hashes.
        var hashes=m.checksums || {}, algorithms=['sha256','whirlpool','sha1','md5'];
        if (known(m) && m.size_precision==='exact') {
            for(var i=0;i<algorithms.length;i++) if(hashes[algorithms[i]]) return algorithms[i]+':'+hashes[algorithms[i]]+':'+m.size_bytes;
        }
        return key(url);
    }
    function summarize(urls) {
        var seen=Object.create(null), bytes=0, unknown=0, estimated=0, duplicates=0, count=0;
        urls.forEach(function(url) {
            var m=info(url), id=identity(url,m);
            if (seen[id]) { duplicates++; return; }
            seen[id]=true; count++;
            if(known(m)) { bytes+=m.size_bytes; if(m.size_precision==='estimated') estimated++; }
            else unknown++;
        });
        return {bytes:bytes, unknown:unknown, estimated:estimated, duplicates:duplicates, count:count};
    }
    function update() {
        if(!totalNode) return;
        var urls=Object.keys(selected), s=summarize(urls);
        totalNode.textContent='Selected download size: '+(s.estimated ? '≈ ' : '')+format(s.bytes)+' known · '+s.count+' files · '+s.unknown+' sizes unknown'+(s.duplicates ? ' · '+s.duplicates+' duplicate selections excluded' : '');
        listingNode.textContent=urls.map(function(url){return selected[url].game+' — '+(info(url).filename || url)+' — '+label(url);}).join('\n');
    }
    function addSelector(wrapper,link,game) {
        var k=key(link.url), m=info(link.url), labelNode=document.createElement('label'), box=document.createElement('input');
        labelNode.style.cssText='display:inline-block;font-size:12px;margin:4px 10px 4px 0;';
        box.type='checkbox';box.checked=!!selected[k];box.setAttribute('data-size-key',k);
        box.setAttribute('aria-label','Include in size total: '+game.name+' '+link.label+' '+(m.filename || link.url));
        labelNode.title=(m.filename ? m.filename+'\n' : '')+(m.evidence || m.reason || 'Size not yet available')+(m.checked_at ? '\nChecked: '+m.checked_at : '')+(m.part_number ? '\nArchive part '+m.part_number+'; complete part count unverified' : '');
        box.onchange=function() {
            if(box.checked) selected[k]={game:game.name}; else delete selected[k];
            var boxes=document.querySelectorAll('input[data-size-key]');
            for(var i=0;i<boxes.length;i++) if(boxes[i].getAttribute('data-size-key')===k) boxes[i].checked=box.checked;
            update();
        };
        labelNode.appendChild(box);labelNode.appendChild(document.createTextNode(' Add to size total'));wrapper.appendChild(labelNode);
    }
    function init(games) {
        if(panel) return;
        var anchor=document.getElementById('searchInfo');if(!anchor) return;
        panel=document.createElement('details');panel.style.cssText='margin:12px 0;padding:12px;background:#eef4fa;color:#172b4d;border-radius:8px;font-size:13px;';
        var heading=document.createElement('summary'), urls=[], seen=Object.create(null);
        games.forEach(function(g){g.links.forEach(function(l){var k=key(l.url);if(!seen[k]) {seen[k]=true;urls.push(k);}});});
        var s=summarize(urls), n=urls.filter(function(url){return known(info(url));}).length;
        heading.textContent='File sizes: '+n.toLocaleString('en-GB')+' / '+urls.length.toLocaleString('en-GB')+' links known — download-size calculator';
        panel.appendChild(heading);
        var coverage=document.createElement('p');
        coverage.textContent='Known indexed files: '+(s.estimated ? '≈ ' : '')+format(s.bytes)+'. Includes different mirrors, regions and older versions unless identical host-reported checksums confirm a duplicate. This is not the size of one copy of every game.';
        panel.appendChild(coverage);
        totalNode=document.createElement('p');totalNode.style.fontWeight='bold';panel.appendChild(totalNode);
        var note=document.createElement('p');note.textContent='Tick “Add to size total” beside the files you want. Choose one mirror, the appropriate update, and every required archive part. Unknown sizes are excluded, not counted as zero. Totals measure download files, not installed PS4 space. Selection lasts until this page is reloaded.';panel.appendChild(note);
        var clear=document.createElement('button');clear.type='button';clear.textContent='Clear size selection';clear.onclick=function(){selected=Object.create(null);var boxes=document.querySelectorAll('input[data-size-key]');for(var i=0;i<boxes.length;i++)boxes[i].checked=false;update();};panel.appendChild(clear);
        listingNode=document.createElement('pre');listingNode.style.cssText='white-space:pre-wrap;max-height:220px;overflow:auto;font-size:12px;';panel.appendChild(listingNode);
        if(typeof fileSizes==='object' && fileSizes.summary) {
            var status=document.createElement('p'), states=fileSizes.summary.states || {};
            status.textContent='Size pass: '+(states.pending || 0)+' pending · '+(states.held || 0)+' paused for access or adapter review · '+(states.unsupported || 0)+' unsupported/container links. Updated '+(fileSizes.updated_at || 'not yet run')+'.';panel.appendChild(status);
        }
        anchor.parentNode.insertBefore(panel,anchor);update();
    }
    return {init:init,addSelector:addSelector,label:label,summarize:summarize,format:format};
}());
