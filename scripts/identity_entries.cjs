// Build identity inputs from exactly the listings visible in the catalogue.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const c = {URL, releaseMetadata:read('release-metadata.json'), linkStatuses:read('link-status.json'),
    fileSizes:read('file-sizes.json'), igdbMetadata:read('igdb-metadata.json')};
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(root, 'catalog.js'), 'utf8'), c);
const rows = read('ps4_games_expanded.json').concat(read('superpsx-catalog.json').records, read('additional-catalog.json').records);
const games = c.gameCatalog.groupGames(c.gameCatalog.prepare(rows));
process.stdout.write(JSON.stringify(games.map(g => ({name:g.name, aliases:g.aliases, igdb_id:g.igdb_id || null,
    title_ids:[...new Set(g.releases.filter(r => r.metadata.kind === 'base' && !r.metadata.conflict)
        .map(r => r.metadata.title_id).filter(Boolean))], kinds:[...new Set(g.releases.map(r => r.metadata.kind || 'unknown'))]}))));
