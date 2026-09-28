// Keep the catalogue usable as source indexing adds more release links.
var catalogPaging = (function() {
    var page = 0, size = 50;
    function filter(games, text, source) {
        var query = (text || '').trim().toLowerCase();
        return games.filter(function(game) {
            if (source && game.source !== source) return false;
            if (!query) return true;
            if (!game.searchText) {
                var terms = [game.name, game.source];
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
        var matches = filter(games, input.value, source);
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
            (source ? ' from ' + source : '') + (input.value.trim() ? ' matching "' + input.value + '"' : '');
        if (!matches.length) {
            var message = document.createElement('div');
            message.className = 'loading';
            message.textContent = 'No games matched this search.';
            document.getElementById('gamesContainer').appendChild(message);
        }
    }
    return { show: show, filter: filter };
}());
