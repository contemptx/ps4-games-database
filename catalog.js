// Shared catalogue rules for the desktop and PS4 browser pages.
var gameCatalog = (function() {
    var hosts = ['mediafire', '1file', 'other'];

    function matchesHost(host, domain) {
        return host === domain || host.slice(-(domain.length + 1)) === '.' + domain;
    }

    function normalizeUrl(value) {
        if (typeof value !== 'string') return null;
        value = value.trim();
        if (value.indexOf('//') === 0) value = 'https:' + value;
        try {
            var url = new URL(value);
            if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
            if (url.username || url.password || !/^[a-z0-9.-]+$/i.test(url.hostname)) return null;
            return url;
        } catch (error) {
            return null;
        }
    }

    function describeLink(value) {
        var url = normalizeUrl(value);
        if (!url) return null;
        var host = url.hostname.toLowerCase();
        var path = url.pathname;
        // These were scraped from menus, help pages and comment-sharing buttons.
        if (matchesHost(host, 'twitter.com') || matchesHost(host, 'x.com') || matchesHost(host, 'facebook.com')) return null;
        if (matchesHost(host, 'dlpsgame.com') && path.replace(/\/$/, '') === '/guide-to-download-at-highest-speed') return null;
        if (matchesHost(host, 'romsfun.com') && !/^\/download\/[^/]+/.test(path)) return null;
        // The original Zippyshare service closed in 2023: https://blog.zippyshare.com/
        if (matchesHost(host, 'zippyshare.com')) return null;

        var label = host.replace(/^www\./, '');
        var group = 'other';
        if (matchesHost(host, 'mediafire.com')) { label = 'MediaFire'; group = 'mediafire'; }
        else if (matchesHost(host, '1fichier.com')) { label = '1fichier'; group = '1file'; }
        else if (matchesHost(host, 'filecrypt.cc') || matchesHost(host, 'filecrypt.co')) label = 'Filecrypt';
        else if (matchesHost(host, 'romsfun.com')) label = 'RomsFun';
        else if (matchesHost(host, 'downloadgameps3.net')) label = 'DownloadGamePS3';
        else if (matchesHost(host, 'mega.nz')) label = 'MEGA';
        else if (matchesHost(host, 'drive.google.com')) label = 'Google Drive';
        else if (matchesHost(host, 'filefactory.com')) label = 'FileFactory';
        else if (matchesHost(host, 'akirabox.com')) label = 'AkiraBox';
        else if (matchesHost(host, 'anotepad.com')) label = 'Link list';
        else if (matchesHost(host, 'bit.ly')) label = 'Short link';
        else if (matchesHost(host, 'vikingfile.com')) label = 'VikingFile';
        return { url: url.href, host: host, label: label, group: group };
    }

    function prepare(records) {
        var games = [];
        records.forEach(function(record) {
            if (!record || typeof record.name !== 'string') return;
            var name = record.name.trim();
            // A scraped URL is not a game title.
            if (!name || /^(?:https?:\/\/|www\.)/i.test(name)) return;

            var sourceLinks = record.download_links || {};
            var downloadLinks = { mediafire: [], '1file': [], other: [] };
            var destinations = [];
            var seen = Object.create(null);
            hosts.forEach(function(host) {
                var links = Array.isArray(sourceLinks[host]) ? sourceLinks[host] : [];
                links.forEach(function(value) {
                    var link = describeLink(value);
                    if (!link || seen[link.url]) return;
                    seen[link.url] = true;
                    downloadLinks[link.group].push(link.url);
                    destinations.push(link);
                });
            });

            // Count links the UI renders, rather than trusting scraped totals.
            if (destinations.length === 0) return;
            var pageUrl = normalizeUrl(record.page_url);
            games.push({
                name: name,
                page_url: pageUrl ? pageUrl.href : null,
                download_links: downloadLinks,
                links: destinations,
                total_links: destinations.length
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

    return { prepare: prepare, updateStatistics: updateStatistics, describeLink: describeLink };
}());
