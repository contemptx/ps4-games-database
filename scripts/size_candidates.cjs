// Reuse the live catalogue's exact inclusion and canonical URL rules.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const c = {URL, releaseMetadata:read('release-metadata.json'), linkStatuses:read('link-status.json')};
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(root,'catalog.js'),'utf8'), c);
const rows = read('ps4_games_expanded.json').concat(read('superpsx-catalog.json').records,read('additional-catalog.json').records);
const links = new Map();
for(const game of c.gameCatalog.prepare(rows)) for(const link of game.links) {
 const key=c.gameCatalog.statusKey(link.url);
 if(!links.has(key)) links.set(key,{url:key,host:link.host});
}
process.stdout.write(JSON.stringify(Array.from(links.values())));
