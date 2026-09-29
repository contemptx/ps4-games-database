const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const c = {URL};
vm.createContext(c);
for (const name of ['recommendations.js', 'paging.js']) vm.runInContext(fs.readFileSync(path.join(root, name), 'utf8'), c);
const advisor = c.catalogRecommendations;
const options = {firmware:'9.00', host:'1fichier.com'};
let id = 0;
function release(kind, version, extra = {}, source = 'Source A') {
    return {metadata:{kind, version, title_id:'CUSA00001', region:'EUR', firmware:'5.05+', source_section:'First release', ...extra},
        page_url:'https://example.org/' + source, source,
        links:[{url:'https://1fichier.com/?test' + (++id), label:'1fichier'}]};
}
const base = release('base', '1.00');
const old = release('update', '1.09');
const latest = release('update', '1.10');
const tooNew = release('update', '1.11', {firmware:'11.00+'});
const missingFirmware = release('update', '1.12', {firmware:null});
const wrongId = release('update', '9.99', {title_id:'CUSA00002'});
const wrongRegion = release('update', '9.99', {region:'USA'});
const wrongSection = release('update', '9.99', {source_section:'Different dump'});
const wrongEdition = release('update', '9.99', {edition:'GOTY'});
const wrongSource = release('update', '9.99', {}, 'Source B');
const conflict = release('update', '9.99', {conflict:true});
const dlcA = release('dlc', '1.00');
const dlcB = release('dlc', '2.00');
const bundle = release('bundle', '9.99');
const game = {name:'Example game', releases:[base, old, latest, tooNew, missingFirmware, wrongId, wrongRegion,
    wrongSection, wrongEdition, wrongSource, conflict, dlcA, dlcB, bundle]};
game.links = game.releases.flatMap(r => r.links);
let result = advisor.analyze(game, options);
assert.equal(result.base, base);
assert.equal(result.update, latest, 'Choose latest numeric version within firmware and exact source family');
assert.equal(result.dlc.length, 2, 'DLC items are separate content, never replace older DLC by highest version');
assert.equal(advisor.analyze(game, {firmware:'', host:options.host}).update, missingFirmware, 'No firmware selection means requirements unchecked');
assert.equal(advisor.analyze(game, {firmware:'banana', host:options.host}).base, null);
assert.equal(advisor.analyze({releases:[release('base','1.00',{title_id:null}), latest]}, options).base, null);
assert.equal(advisor.analyze({releases:[release('base','1.00',{region:null}), latest]}, options).base, null);
assert.equal(advisor.analyze({releases:[release('base','1.00',{firmware:null}), latest]}, options).base, null);
assert.equal(advisor.analyze({releases:[release('base','1.10'), old, latest]}, options).update, null, 'Do not suggest a downgrade');
assert.equal(advisor.analyze({releases:[base, release('update',null)]}, options).update, null);
// Backport target lists and ambiguous ranges must never be treated as a minimum.
assert.equal(advisor.firmwareState({firmware:'5.05/6.72/7.xx', variant:'Backport / fix'}, '9.00'), 'not-listed');
assert.equal(advisor.firmwareState({firmware:'5.05/6.72/7.xx', variant:'Backport / fix'}, '7.55'), 'fits');
assert.equal(advisor.firmwareState({firmware:'5.05', variant:'Backport / fix'}, '9.00'), 'not-listed');
assert.equal(advisor.firmwareState({firmware:'5.05'}, '9.00'), 'fits');
assert.equal(advisor.firmwareState({firmware:'5.05+'}, '5.00'), 'not-listed');
assert.equal(advisor.firmwareState({firmware:'5.05–9.00'}, '9.00'), 'unknown');
assert.equal(advisor.firmwareState({firmware:'6.7'}, '6.72'), 'unknown');
assert.equal(advisor.firmwareState({firmware:'7.xx+'}, '7.55'), 'unknown');
assert.equal(advisor.firmwareState({firmware:'5.05+', conflict:true}, '9.00'), 'unknown');
const backport = release('update', '1.22', {firmware:'5.05/9.00', variant:'Backport / fix'});
assert.equal(advisor.analyze({releases:[release('base','1.00',{firmware:'9.50'}),backport]}, options).base, null,
    'A backport update does not establish that a higher-firmware base is usable');
// Selecting Updates must still pair it with its base, and a source filter must not borrow another source's base.
const filtered = c.catalogPaging.filter([game], '', 'Source A', 'update')[0];
assert.equal(filtered.releases.includes(base), false);
assert.equal(advisor.analyze(filtered, options).update, latest);
assert.equal(advisor.analyze(c.catalogPaging.filter([game], '', 'Source B', 'update')[0], options).base, null);
assert.equal(game.releases.length, 14, 'Filtering does not mutate catalogue releases');
const mirrors = {links:[{url:'https://vikingfile.com/f/abc'}, {url:'https://1fichier.com/?part1'},
    {url:'https://mediafire.com/file/mirror'}, {url:'https://1fichier.com/?part2'}]};
const ordered = advisor.orderedLinks(mirrors, '1fichier.com');
assert.equal(ordered.length, 4, 'Preserve every mirror/part');
assert.equal(ordered[0].url, mirrors.links[1].url);
assert.equal(ordered[1].url, mirrors.links[3].url);
assert.equal(mirrors.links[0].url, 'https://vikingfile.com/f/abc', 'Do not mutate the input');
assert.equal(advisor.suggestedHost({links:[{url:'https://vikingfile.com/f/abc'}]}, options.host), '');
console.log('Release recommendation and filter checks passed.');
