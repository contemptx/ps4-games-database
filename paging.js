// Keep the catalogue usable as source indexing adds more release links.
var catalogPaging = (function() {
    var page = 0, size = 50;
    function filter(games, text, source, kind) {
        var query = (text || '').trim().toLowerCase();
        var candidates = (kind || source) ? games.map(function(game) {
            var releases = (game.releases || []).filter(function(release) {
                if (source && (release.source || game.source) !== source) return false;
                if (!kind) return true;
                var m = release.metadata || {};
                var known = ['base', 'update', 'dlc', 'fix', 'patch', 'bundle'];
                return kind === 'unknown' ? (!m.kind || known.indexOf(m.kind) === -1 || m.conflict) : m.kind === kind && !m.conflict;
            });
            if (!releases.length) return null;
            var copy = {};
            Object.keys(game).forEach(function(key) { copy[key] = game[key]; });
            copy.releases = releases;
            if (source && game.sources) copy.sources = game.sources.filter(function(s) { return s.name === source; });
            copy.links = [];
            releases.forEach(function(release) { copy.links = copy.links.concat(release.links); });
            copy.total_links = copy.links.length;
            copy.searchText = '';
            return copy;
        }).filter(function(game) { return game !== null; }) : games;
        return candidates.filter(function(game) {

            if (!query) return true;
            if (!game.searchText) {
                var terms = [game.name, game.source].concat(game.aliases || []);
                game.links.forEach(function(link) {
                    var m = link.release || {};
                    terms.push(link.label, m.kind, m.version, m.title_id, m.region, m.firmware, m.edition, m.source_label, m.source_section);
                });
                game.searchText = terms.join(' ').toLowerCase();
            }
            return game.searchText.indexOf(query) !== -1;
        });
    }
    function show(games, render, delta) {
        page = delta === 0 ? 0 : page + delta;
        var input = document.getElementById('searchInput');
        var source = document.getElementById('sourceFilter').value || '';
        var releaseFilter = document.getElementById('releaseFilter');
        var kind = releaseFilter ? releaseFilter.value : '';
        var matches = filter(games, input.value, source, kind);
        if (typeof catalogSorting === 'object') matches = catalogSorting.sort(matches, catalogSorting.mode());
        var pages = Math.ceil(matches.length / size);
        page = Math.max(0, Math.min(page, pages - 1));
        var start = page * size, end = Math.min(start + size, matches.length);
        render(matches.slice(start, end));
        document.getElementById('gamesContainer').scrollTop = 0;
        document.getElementById('previousPage').disabled = page === 0;
        document.getElementById('nextPage').disabled = page + 1 >= pages;
        document.getElementById('pageStatus').textContent = pages ? 'Page ' + (page + 1) + ' of ' + pages : 'No matches';
        document.getElementById('searchInfo').textContent = 'Showing ' + (matches.length ? start + 1 : 0) + '–' + end +
            ' of ' + matches.length.toLocaleString() + ' game listing' + (matches.length === 1 ? '' : 's') +
            (source ? ' from ' + source : '') + (kind ? ' · ' + releaseFilter.options[releaseFilter.selectedIndex].text : '') + (input.value.trim() ? ' matching "' + input.value + '"' : '');
        if (!matches.length) {
            var message = document.createElement('div');
            message.className = 'loading';
            message.textContent = 'No games matched this search.';
            document.getElementById('gamesContainer').appendChild(message);
        }
    }
    return { show: show, filter: filter };
}());
