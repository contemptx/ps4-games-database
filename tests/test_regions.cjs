const fs=require('node:fs'), vm=require('node:vm'), path=require('node:path'), assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'), c={URL}; vm.createContext(c);
for(const name of ['regions.js','catalog.js','paging.js','recommendations.js']) vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),c);
const r=c.catalogRegions, plain=x=>JSON.parse(JSON.stringify(x));
assert.deepEqual(plain(r.explicit('US / EU / JP')),['EUR','JPN','USA']);
assert.deepEqual(plain(r.tokens('The_Last_of_US_CUSA12345_English_MULTI5.pkg')),[]);
assert.deepEqual(plain(r.tokens('Game_CUSA12345_[Japan]_v1.00.pkg')),['JPN']);
assert.deepEqual(plain(r.tokens('Game_CUSA12345_[9.00]_JPN.pkg')),['JPN']);
assert.deepEqual(plain(r.tokens('Region: EU')),['EUR']);
assert.deepEqual(plain(r.enrich({title_id:'CUSA12345'},'').regions),[]);
assert.deepEqual(plain(r.enrich({region:'EUR / USA'},'',{filename:'Game_[USA].pkg'}).regions),['USA']);
const mismatch=r.enrich({region:'EUR'},'',{filename:'Game_[USA].pkg'});
assert.equal(mismatch.region_status,'conflict'); assert.equal(mismatch.region,'');
assert.equal(r.matches(mismatch,'USA'),false); assert.equal(r.matches(mismatch,'unknown'),true);
const source='https://dlpsgame.com/region-example/';
c.fileSizes={files:{'https://1fichier.com/?jp':{filename:'Test_[JPN].pkg'}}};
const games=c.gameCatalog.groupGames(c.gameCatalog.prepare([{name:'Regions',page_url:source,release_links:[
    {url:'https://1fichier.com/?base',kind:'base',region:'EUR',title_id:'CUSA12345'},
    {url:'https://1fichier.com/?update',kind:'update',region:'USA',title_id:'CUSA12345'},
    {url:'https://1fichier.com/?jp',kind:'base',title_id:'CUSA34567'},
    {url:'https://1fichier.com/?unknown',kind:'dlc'}]}]));
assert.equal(games[0].total_links,4);
assert.equal(c.catalogPaging.filter(games,'','','base','JPN')[0].total_links,1);
assert.equal(c.catalogPaging.filter(games,'','','update','EUR').length,0);
const update=c.catalogPaging.filter(games,'','','update','USA')[0];
assert.equal(update.recommendationReleases.length,1,'EUR base must not enter USA recommendations');
assert.equal(c.catalogPaging.filter(games,'','','','unknown')[0].total_links,1);
assert.equal(games[0].total_links,4,'Filtering cannot mutate the source catalogue');
assert.equal(r.summary(games).identified_links,3);
console.log('Region evidence, conflicts, title-language false positives and combined filters: PASS');
