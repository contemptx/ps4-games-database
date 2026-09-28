const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../paging.js'),'utf8'),c);
const games=[{name:'One',source:'SuperPSX',links:[{label:'1fichier',release:{kind:'update',version:'1.08',title_id:'CUSA43772'}}]}, {name:'Two',source:'DLPSGame',links:[]}];
assert.equal(c.catalogPaging.filter(games,'CUSA43772','SuperPSX').length,1);
assert.equal(c.catalogPaging.filter(games,'1.08','DLPSGame').length,0);
assert.equal(c.catalogPaging.filter(games,'two','').length,1);
assert.equal(c.catalogPaging.filter(games,'','').length,2);
console.log('Catalogue-wide release search and source filters: PASS');
