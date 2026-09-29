const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const c = {URL,gameIdentities:{records:{
    'Game A':{status:'identified',igdb_id:1,canonical_id:1},
    'Game A Gold':{status:'identified',igdb_id:2,canonical_id:1},
    'Game B':{status:'identified',igdb_id:3,canonical_id:3},
    'DLC':{status:'non_game',igdb_id:4,canonical_id:4},
    'Unknown':{status:'review'}
}}};
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../catalog.js'),'utf8'), c);
const games = ['Game A','Game A Gold','Game B','DLC','Unknown','New unmatched listing'].map(name=>({name}));
const result = c.gameCatalog.identityCounts(games);
assert.equal(result.unique,2);
assert.equal(result.duplicateListings,1);
assert.equal(result.other,1);
assert.equal(result.unresolved,2);
assert.equal(result.matched+result.other+result.unresolved,games.length);
assert.equal(c.gameCatalog.identityCounts([{name:'Game A',igdb_id:999}]).unresolved,1,'A changed IGDB match must be reviewed again');
assert.equal(c.gameCatalog.identityCounts([{name:'Game B'}]).unique,1,'Counts reflect currently included listings');
delete c.gameIdentities;
assert.equal(c.gameCatalog.identityCounts(games),null,'Missing identity data must not pretend listings are unique');
console.log('Unique identity counter checks passed.');
