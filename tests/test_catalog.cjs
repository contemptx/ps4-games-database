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
result = catalog.prepare([{name:'Ambiguous filename',download_links:{mediafire:['https://www.mediafire.com/file/id/Title_CUSA12345_v1.00_v1.17.rar/file']}}]);
assert.equal(result[0].links[0].release.version,undefined);
console.log('Catalogue release comparison, identity, filtering and filename evidence: PASS');
const imported = {name:'Test',page_url:'https://www.superpsx.com/test-ps4/',release_links:[{url:'https://1fichier.com/?super&af=1',kind:'update',version:'1.08',title_id:'CUSA43772',region:'EUR',firmware:'12.00+',evidence:'Source page'}],download_links:{other:['https://1fichier.com/?super','https://filecrypt.cc/Container/blocked']}};
result = catalog.prepare([imported, imported, {name:'Test',page_url:'https://dlpsgame.com/another-edition/',download_links:{other:['https://1fichier.com/?otheredition']}}]);
assert.equal(result.length,2, 'Separate same-title source listings, deduplicate identical source pages');
assert.equal(result[0].source,'SuperPSX');
assert.equal(result[0].links.length,1);
assert.equal(result[0].links[0].release.version,'1.08');
assert.equal(catalog.describeLink('https://mocha.my/share/id').label,'Mocha');
assert.equal(catalog.describeLink('https://filekeeper.net/id/file.pkg').label,'FileKeeper');
console.log('SuperPSX source identity, metadata, host labels and canonical filtering: PASS');

const sameFile = Object.assign({}, imported, {release_links: [imported.release_links[0], Object.assign({}, imported.release_links[0], {url:'https://1fichier.com/?super&af=2'})]});
result = catalog.prepare([sameFile]);
assert.equal(result[0].links.length,1);
assert(!result[0].links[0].release.conflict, 'Affiliate URLs do not create conflicting release labels');

context.releaseMetadata.pages['https://dlpsgame.com/editions/'] = {links:[
  Object.assign(update('dub1','1.10'), {edition:'English dub'}),
  Object.assign(update('dub2','1.20'), {edition:'Japanese dub'})
]};
result = catalog.prepare([{name:'Editions',page_url:'https://dlpsgame.com/editions/'}]);
assert.equal(result[0].releases.filter(r=>r.newest).length,0, 'Do not recommend updates across distinct editions');
