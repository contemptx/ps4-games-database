// The same region evidence and visible links as the browser; no host downloads.
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const context = {URL, releaseMetadata:read('release-metadata.json'), linkStatuses:read('link-status.json'),
    fileSizes:read('file-sizes.json'), igdbMetadata:read('igdb-metadata.json'), gameIdentities:read('game-identities.json')};
vm.createContext(context);
for (const file of ['regions.js','catalog.js']) vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'), context);
const rows = read('ps4_games_expanded.json').concat(read('superpsx-catalog.json').records,read('additional-catalog.json').records);
const games = context.gameCatalog.groupGames(context.gameCatalog.prepare(rows));
const identities = context.gameIdentities.records;
const entries = games.map(game => {
    const record = identities[game.name];
    const fresh = record && (game.igdb_id || null) === (record.input_igdb_id || null) &&
        (game.sources || []).some(s => (record.source_urls || []).includes(s.page_url));
    return {name:game.name, canonical_id:fresh && record.status === 'identified' ? record.canonical_id : null,
        canonical_name:fresh ? record.canonical_name : null, identity_status:fresh ? record.status : 'review',
        sources:game.sources, links:game.links.map(link => ({url:context.gameCatalog.statusKey(link.url),
            kind:link.release.conflict ? 'unknown' : link.release.kind || 'unknown',
            title_id:link.release.title_id || null, regions:link.release.regions,
            region_status:link.release.region_status, region_evidence:link.release.region_evidence}))};
});
process.stdout.write(JSON.stringify({summary:context.catalogRegions.summary(games),
    identity_summary:context.gameCatalog.identityCounts(games), entries}));
