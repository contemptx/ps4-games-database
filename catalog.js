// Shared catalogue rules for the desktop and PS4 browser pages.
var gameCatalog = (function() {
    var hosts = ['mediafire', '1file', 'other'];

    function prepare(records) {
        var games = [];
        records.forEach(function(record) {
            if (!record || typeof record.name !== 'string') return;
            var name = record.name.trim();
            // A scraped URL is not a game title.
            if (!name || /^(?:https?:\/\/|www\.)/i.test(name)) return;

            var sourceLinks = record.download_links || {};
            var downloadLinks = {};
            var linkCount = 0;
            hosts.forEach(function(host) {
                var links = Array.isArray(sourceLinks[host]) ? sourceLinks[host] : [];
                downloadLinks[host] = links.filter(function(link) {
                    return typeof link === 'string' && /^(?:https?:)?\/\/\S+/i.test(link.trim());
                }).map(function(link) {
                    link = link.trim();
                    return link.indexOf('//') === 0 ? 'https:' + link : link;
                });
                linkCount += downloadLinks[host].length;
            });

            // Count links the UI renders, rather than trusting scraped totals.
            if (linkCount === 0) return;
            games.push({
                name: name,
                page_url: record.page_url,
                download_links: downloadLinks,
                total_links: linkCount
            });
        });
        return games;
    }

    function updateStatistics(games) {
        var links = games.reduce(function(total, game) { return total + game.total_links; }, 0);
        var gameCount = games.length.toLocaleString('en-US');
        var linkCount = links.toLocaleString('en-US');
        document.getElementById('totalGames').textContent = gameCount;
        document.getElementById('totalLinks').textContent = linkCount;
        document.getElementById('catalogTotals').textContent = gameCount + ' Games | ' + linkCount + ' Download Links';
    }

    return { prepare: prepare, updateStatistics: updateStatistics };
}());
