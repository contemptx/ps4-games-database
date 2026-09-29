(function() {
    var data, page=0, pageSize=75;
    var $=function(id){return document.getElementById(id);};
    var number=function(n){return Number(n || 0).toLocaleString('en-US');};
    function textCell(row,value){var td=document.createElement('td');td.textContent=value;row.appendChild(td);return td;}
    function render(){
        var scope=$('scope').value, query=$('search').value.trim().toLowerCase(), market=$('market').value;
        $('market').disabled=scope==='outside';
        var rows=(scope==='outside'?data.outside_reference:data.reference).filter(function(row){
            if(scope==='gaps' && row.catalogued || scope==='matched' && !row.catalogued)return false;
            if(query && (row.name+' '+(row.listings || []).join(' ')).toLowerCase().indexOf(query)===-1)return false;
            return scope==='outside' || !market || row.reference_regions.indexOf(market)!==-1;
        });
        var pages=Math.ceil(rows.length/pageSize);page=Math.max(0,Math.min(page,pages-1));
        $('results').textContent='';
        rows.slice(page*pageSize,(page+1)*pageSize).forEach(function(row){
            var tr=document.createElement('tr'), title=textCell(tr,'');
            if(row.url && /^https:\/\/(?:www\.)?igdb\.com\//.test(row.url)){
                var a=document.createElement('a');a.href=row.url;a.textContent=row.name;a.rel='noopener noreferrer';a.target='_blank';title.appendChild(a);
            }else title.textContent=row.name;
            textCell(tr,row.release_date_label || 'Outside reference');
            textCell(tr,(scope==='outside'?row.platforms:row.reference_regions).join(', ') || 'Unknown');
            textCell(tr,scope==='outside'?row.reason:!row.catalogued?'No identity match':row.has_labelled_base?
                'Base labelled'+(row.base_regions.length?' · '+row.base_regions.join(', '):' · region unknown'):'Title matched; base link not identified');
            $('results').appendChild(tr);
        });
        $('resultSummary').textContent=number(rows.length)+' identities'+(scope==='outside'?' need platform/date/type review':' in this view');
        $('page').textContent=pages?'Page '+(page+1)+' of '+pages:'No matches';
        $('previous').disabled=page===0;$('next').disabled=page+1>=pages;
    }
    fetch('catalogue-coverage.json',{cache:'no-store'}).then(function(response){if(!response.ok)throw new Error('Report unavailable');return response.json();}).then(function(report){
        data=report;var s=data.summary,r=data.regions.summary;
        $('snapshot').textContent='Reference snapshot: '+data.as_of+' · Last refreshed '+data.updated_at.slice(0,16).replace('T',' ')+' UTC';
        [[s.catalogue_unique_identities,'All catalogue identities'],[s.reference_unique_games,'Dated IGDB PS4 / PS VR reference'],
         [s.reference_matches,'Reference identities matched'],[s.reference_gaps,'Unmatched reference identities']].forEach(function(item){
            var card=document.createElement('div');card.className='stat';var strong=document.createElement('strong');strong.textContent=number(item[0]);
            var label=document.createElement('span');label.textContent=item[1];card.appendChild(strong);card.appendChild(label);$('stats').appendChild(card);
        });
        $('platformSummary').textContent=number(s.local_ps4_or_psvr_reference)+' of our identities have a PS4/PS VR reference; '+
            number(s.local_without_ps4_reference)+' need platform/conversion review and '+number(s.local_identities_without_igdb)+
            ' use local identities. '+number(s.matches_with_labelled_base)+' matched reference identities have an explicitly labelled base link.';
        $('regionSummary').textContent=number(r.identified_links)+' of '+number(r.links)+' visible link occurrences have region evidence. '+
            number(r.unknown_links)+' are unknown or conflicting, including '+number(r.conflicting_links)+' contradictions.';
        Object.keys(data.regions.regions).sort().forEach(function(code){
            var row=data.regions.regions[code],tr=document.createElement('tr');textCell(tr,code);textCell(tr,number(row.links));
            textCell(tr,number(row.identities));textCell(tr,number(row.base_identities));
            textCell(tr,number(data.reference.filter(function(item){return item.catalogued && item.base_regions.indexOf(code)!==-1;}).length));$('regions').appendChild(tr);
        });
        var markets={};data.reference.forEach(function(row){row.reference_regions.forEach(function(code){markets[code]=true;});});
        Object.keys(markets).sort().forEach(function(code){var option=document.createElement('option');option.value=code;option.textContent=code;$('market').appendChild(option);});
        $('policy').textContent=data.policy;
        ['scope','search','market'].forEach(function(id){$(id).addEventListener(id==='search'?'input':'change',function(){page=0;render();});});
        $('previous').onclick=function(){page--;render();};$('next').onclick=function(){page++;render();};render();
    }).catch(function(){ $('snapshot').textContent='';$('error').textContent='The latest coverage report is being prepared. Please refresh shortly, or check the reconciliation workflow in GitHub Actions.'; });
}());
