const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const context = { URL, linkStatuses: { links: {} }, releaseMetadata: { pages: {} } };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'catalog.js'), 'utf8'), context);
const catalog = context.gameCatalog;
assert.equal(catalog.describeLink('https://filecrypt.cc/Container/abc.html'), null);
assert.equal(catalog.describeLink('https://www.filecrypt.cc/Container/abc.html'), null);
assert(catalog.describeLink('https://filecrypt.co/Container/abc.html'));
assert.equal(catalog.compareVersions('1.10', '1.09'), 1);
const page = 'https://dlpsgame.com/test/';
const update = (id, version, title = 'CUSA12345', region = 'EUR') => ({url:'https://1fichier.com/?'+id, kind:'update', title_id:title, region, version, evidence:'Source page'});
context.releaseMetadata.pages[page] = {links:[
  update('old','1.09'), update('new','1.10'), update('unknown',undefined),
  update('other','9.99','CUSA99999'),
  {url:'https://1fichier.com/?dlc',kind:'dlc',title_id:'CUSA12345',region:'EUR',evidence:'Source page',source_section:'v1.10'},
  {url:'https://filecrypt.cc/Container/hidden.html',kind:'base'}
]};
context.linkStatuses.links['https://1fichier.com/?missing'] = {status:'missing'};
let result = catalog.prepare([{name:'Test',page_url:page,download_links:{'1file':['https://1fichier.com/?new&af=123','https://1fichier.com/?missing']}}]);
assert.equal(result.length,1);
assert.equal(result[0].total_links,5);
assert.equal(result[0].releases.filter(r=>r.newest).length,1);
assert.equal(result[0].releases.find(r=>r.newest).metadata.version,'1.10');
assert(!result[0].releases.find(r=>r.metadata.kind==='dlc').metadata.version);
result = catalog.prepare([{name:'Unknown', download_links:{mediafire:['https://www.mediafire.com/file/id/Title_CUSA12345_v1.00_[9.00].rar/file']}}]);
assert.equal(result[0].links[0].release.version,'1.00');
assert.equal(result[0].links[0].release.kind,undefined);
assert.equal(result[0].links[0].release.firmware,'9.00');
console.log('Catalogue release comparison, identity, filtering and filename evidence: PASS');
