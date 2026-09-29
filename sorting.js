var catalogSorting = (function() {
    var labels = { az: 'A–Z', za: 'Z–A', newest: 'PS4 release: newest first', oldest: 'PS4 release: oldest first', popular: 'Popularity: IGDB visits' };
    function metadata(game) {
        var records = typeof igdbMetadata === 'object' && igdbMetadata.records || {};
        return Object.prototype.hasOwnProperty.call(records, game.metadata_name || game.name) ? records[game.metadata_name || game.name] : {};
    }
    function mode() {
        var select = document.getElementById('sortOrder');
        return select ? select.value : 'az';
    }
    function sort(games, order) {
        return games.slice().sort(function(a, b) {
            var am = metadata(a), bm = metadata(b), av, bv;
            if (order === 'popular') { av = am.popularity; bv = bm.popularity; }
            if (order === 'newest' || order === 'oldest') { av = am.release_sort; bv = bm.release_sort; }
            if (order === 'popular' || order === 'newest' || order === 'oldest') {
                var ak = av !== undefined && av !== null, bk = bv !== undefined && bv !== null;
                if (ak !== bk) return ak ? -1 : 1;
                if (ak && av !== bv) return (av < bv ? -1 : 1) * (order === 'oldest' ? 1 : -1);
            }
            return a.name.localeCompare(b.name) * (order === 'za' ? -1 : 1);
        });
    }
    function section(game) {
        if (mode() !== 'az') return labels[mode()] || labels.az;
        var letter = game.name.charAt(0).toUpperCase();
        return /[A-Z]/.test(letter) ? letter : '#';
    }
    function describe(container, game) {
        var m = metadata(game);
        var cover = document.createElement('div');
        cover.className = 'game-cover';
        var fallback = document.createElement('span');
        fallback.className = 'cover-placeholder';
        fallback.textContent = 'PS4';
        cover.appendChild(fallback);
        if (m.cover_url && /^https:\/\/images\.igdb\.com\/igdb\/image\/upload\/t_cover_big\/[A-Za-z0-9_]+\.jpg$/.test(m.cover_url)) {
            var image = document.createElement('img');
            image.src = m.cover_url; image.alt = game.name + ' cover';
            image.loading = 'lazy'; image.decoding = 'async';
            image.width = 264; image.height = 352;
            image.onerror = function() { image.style.display = 'none'; };
            cover.appendChild(image);
        }
        container.insertBefore(cover, container.firstChild);
        var line = document.createElement('div');
        line.className = 'game-metadata';
        line.textContent = m.release_date ? 'PS4 release: ' + m.release_date + ' · ' : 'PS4 release date unknown · ';
        if (m.url && /^https:\/\/www\.igdb\.com\/games\//.test(m.url)) {
            var link = document.createElement('a');
            link.href = m.url; link.textContent = 'IGDB'; link.target = '_blank'; link.rel = 'noopener noreferrer';
            line.appendChild(link);
        } else line.appendChild(document.createTextNode(m.igdb_id ? 'IGDB' : 'No IGDB match'));
        container.appendChild(line);
        var score = document.createElement('div');
        score.className = 'game-rating';
        if (typeof m.rating === 'number' && m.rating_count > 0) {
            score.textContent = '★ ' + (m.rating / 10).toFixed(1) + '/10';
            var count = document.createElement('span');
            count.textContent = 'IGDB users · ' + m.rating_count.toLocaleString() + ' ratings';
            score.appendChild(count);
            score.title = 'IGDB user score across platforms, not a PS4-only score';
        } else {
            score.className += ' unrated';
            score.textContent = 'No IGDB user rating';
        }
        container.appendChild(score);
    }
    function init() {
        var label = document.createElement('label');
        label.className = 'source-filter'; label.htmlFor = 'sortOrder'; label.appendChild(document.createTextNode('Sort '));
        var select = document.createElement('select'); select.id = 'sortOrder';
        var summary = typeof igdbMetadata === 'object' && igdbMetadata.summary || {};
        Object.keys(labels).forEach(function(key) {
            var option = document.createElement('option'); option.value = key; option.textContent = labels[key];
            option.disabled = ((key === 'newest' || key === 'oldest') && !summary.with_dates) || (key === 'popular' && !summary.with_popularity);
            select.appendChild(option);
        });
        select.onchange = function() { searchGames(); };
        label.appendChild(select);
        var info = document.getElementById('searchInfo'); info.parentNode.insertBefore(label, info);
        var note = document.createElement('p'); note.className = 'search-info'; note.id = 'metadataCoverage';
        note.textContent = summary.matched ? 'IGDB matched ' + summary.matched.toLocaleString() + ' catalogue titles. Dates use the earliest known PS4 release across regions. Popularity measures IGDB visits across platforms. Missing metadata sorts last. Refreshed ' + igdbMetadata.updated_at.slice(0, 10) + '.' : 'Release-date and popularity sorting will become available after the IGDB import.';
        info.parentNode.insertBefore(note, info);
    }
    return { sort: sort, mode: mode, section: section, describe: describe, init: init };
}());
