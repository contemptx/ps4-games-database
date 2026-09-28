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
        if (isExcluded(url.href)) return null;
        if (isMissing(url.href)) return null;
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

    function statusKey(value) {
        var url = normalizeUrl(value);
        if (!url) return null;
        // Affiliate parameters do not change a 1fichier file's identity.
        if (matchesHost(url.hostname, '1fichier.com')) {
            var id = url.search.match(/^\?([a-z0-9]+)/i);
            if (id) return 'https://1fichier.com/?' + id[1].toLowerCase();
        }
        if (matchesHost(url.hostname, 'mediafire.com')) {
            var file = url.pathname.match(/^\/file\/([a-z0-9]+)(?:\/|$)/i);
            if (file) return 'https://www.mediafire.com/file/' + file[1];
        }
        return url.href;
    }

    function isMissing(value) {
        var key = statusKey(value);
        var statuses = typeof linkStatuses === 'object' && linkStatuses ? linkStatuses.links : null;
        return !!(key && statuses && statuses[key] && statuses[key].status === 'missing');
    }

    function isExcluded(value) {
        var url = normalizeUrl(value);
        // Temporary catalogue preference, not evidence that a file was deleted.
        return !!(url && matchesHost(url.hostname.toLowerCase(), 'filecrypt.cc'));
    }

    function filenameDetails(value) {
        var url = normalizeUrl(value);
        if (!url || !matchesHost(url.hostname, 'mediafire.com')) return {};
        var match = url.pathname.match(/^\/file\/[^/]+\/([^/]+)/);
        if (!match) return {};
        var name;
        try { name = decodeURIComponent(match[1]).replace(/_/g, ' '); } catch (error) { return {}; }
        var result = {};
        var version = uniqueToken(name, /\bv(?:ersion)?\s*(\d{1,3}\.\d{1,3}(?:\.\d+)?)/ig);
        var titleId = uniqueToken(name, /\b(CUSA\d{5})\b/ig);
        var firmware = name.match(/\[(\d+\.(?:\d+|xx)(?:[-/+]\d+\.(?:\d+|xx))*\+?)\]/i);
        if (version) result.version = version;
        if (titleId) result.title_id = titleId.toUpperCase();
        if (firmware) result.firmware = firmware[1].replace(/-/g, '/');
        if (/\bBACKPORT\b/i.test(name)) result.variant = 'Backport / fix';
        if (/^Base[ -]/i.test(name)) result.kind = 'base';
        else if (/^Update[ -]/i.test(name)) result.kind = 'update';
        else if (/\bDLC(?:PACK|s)?\b/i.test(name)) result.kind = 'dlc';
        if (Object.keys(result).length) result.evidence = 'URL filename';
        return result;
    }

    function uniqueToken(text, pattern) {
        var match, tokens = [];
        while ((match = pattern.exec(text))) {
            if (tokens.indexOf(match[1]) === -1) tokens.push(match[1]);
        }
        return tokens.length === 1 ? tokens[0] : null;
    }

    function compareVersions(a, b) {
        var left = a.split('.'), right = b.split('.');
        for (var i = 0; i < Math.max(left.length, right.length); i++) {
            var delta = Number(left[i] || 0) - Number(right[i] || 0);
            if (delta) return delta;
        }
        return 0;
    }

    function releaseGroups(links) {
        var groups = [], index = Object.create(null), versions = Object.create(null);
        links.forEach(function(link) {
            var meta = link.release || {};
            var fields = ['kind', 'version', 'title_id', 'region', 'firmware', 'variant', 'source_section', 'source_label', 'evidence', 'conflict'];
            var key = fields.map(function(field) { return meta[field] || ''; }).join('|');
            if (!index[key]) {
                index[key] = { metadata: meta, links: [] };
                groups.push(index[key]);
            }
            index[key].links.push(link);
            if (meta.kind === 'update' && meta.title_id && meta.region && meta.version && !meta.conflict) {
                var family = [meta.title_id, meta.region, meta.variant || ''].join('|');
                if (!versions[family]) versions[family] = [];
                if (versions[family].indexOf(meta.version) === -1) versions[family].push(meta.version);
            }
        });
        groups.forEach(function(group) {
            var m = group.metadata, family = [m.title_id, m.region, m.variant || ''].join('|');
            var listed = versions[family] || [];
            group.newest = m.kind === 'update' && !!m.version && !m.conflict && listed.length > 1 && listed.every(function(v) { return compareVersions(m.version, v) >= 0; });
        });
        var order = { base: 0, update: 1, dlc: 2, fix: 3, bundle: 4 };
        groups.sort(function(a, b) {
            var left = a.metadata, right = b.metadata;
            var difference = (order[left.kind] === undefined ? 5 : order[left.kind]) - (order[right.kind] === undefined ? 5 : order[right.kind]);
            if (difference) return difference;
            if (left.title_id === right.title_id && left.region === right.region && left.version && right.version) return compareVersions(right.version, left.version);
            return 0;
        });
        return groups;
    }

    function renderLinks(container, game, newTab) {
        var names = { base: 'Base game', update: 'Update', dlc: 'DLC', fix: 'Fix', bundle: 'Combined package' };
        game.releases.forEach(function(release) {
            var m = release.metadata, wrapper = document.createElement('div');
            wrapper.className = 'release-group';
            var heading = document.createElement('div');
            heading.className = 'release-heading';
            var parts = [names[m.kind] || (m.evidence ? 'File — type unspecified' : 'Release details unknown')];
            var dlcCount = m.kind === 'dlc' && (m.source_label || '').match(/\bDLC\s*\((\d+)\)/i);
            if (dlcCount) parts[0] += ' (' + dlcCount[1] + ')';
            if (m.version) parts.push('v' + m.version);
            if (m.title_id) parts.push(m.title_id);
            if (m.region) parts.push(m.region);
            heading.textContent = parts.join(' · ');
            wrapper.appendChild(heading);
            if (release.newest) {
                var badge = document.createElement('span');
                badge.className = 'release-latest';
                badge.textContent = 'Highest listed update — check firmware';
                wrapper.appendChild(badge);
            }
            var details = [];
            if (m.firmware) details.push('Firmware: ' + m.firmware);
            if (m.variant) details.push(m.variant);
            if (m.source_section) details.push('Source section: ' + m.source_section);
            if (m.evidence === 'URL filename') details.push('From filename; package contents unverified');
            if (m.conflict) details.push('Conflicting labels — check source page');
            if (details.length) {
                var note = document.createElement('div');
                note.className = 'release-detail';
                note.textContent = details.join(' · ');
                wrapper.appendChild(note);
            }
            if (m.source_label) wrapper.title = m.source_label;
            var hostCounts = Object.create(null);
            release.links.forEach(function(link) {
                hostCounts[link.label] = (hostCounts[link.label] || 0) + 1;
                var button = document.createElement('a');
                button.setAttribute('href', link.url);
                button.className = 'download-btn btn-' + link.group;
                button.textContent = link.label + ' ' + hostCounts[link.label];
                button.title = m.source_label ? m.source_label + '\n' + link.url : link.url;
                if (newTab) button.target = '_blank';
                button.rel = 'noopener noreferrer';
                wrapper.appendChild(button);
            });
            container.appendChild(wrapper);
        });
        if (game.page_url) {
            var pageButton = document.createElement('a');
            pageButton.setAttribute('href', game.page_url);
            pageButton.className = 'download-btn btn-page';
            pageButton.textContent = 'View source page';
            if (newTab) pageButton.target = '_blank';
            pageButton.rel = 'noopener noreferrer';
            container.appendChild(pageButton);
        }
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
            var pages = typeof releaseMetadata === 'object' && releaseMetadata ? releaseMetadata.pages || {} : {};
            var sourcePage = pages[record.page_url];
            var entries = sourcePage && Array.isArray(sourcePage.links) ? sourcePage.links : [];
            var metadata = Object.create(null), values = [];
            entries.forEach(function(entry) {
                var key = statusKey(entry.url);
                if (!key) return;
                if (metadata[key] && JSON.stringify(metadata[key]) !== JSON.stringify(entry)) {
                    // The same file was labelled differently; never guess its type.
                    metadata[key] = { conflict: true, evidence: 'Source page' };
                } else metadata[key] = entry;
                values.push(entry.url);
            });
            hosts.forEach(function(host) {
                values = values.concat(Array.isArray(sourceLinks[host]) ? sourceLinks[host] : []);
            });
            values.forEach(function(value) {
                    var link = describeLink(value);
                    var key = link && statusKey(link.url);
                    if (!link || seen[key]) return;
                    seen[key] = true;
                    link.release = metadata[key] || filenameDetails(link.url);
                    downloadLinks[link.group].push(link.url);
                    destinations.push(link);
            });

            // Count links the UI renders, rather than trusting scraped totals.
            if (destinations.length === 0) return;
            var pageUrl = normalizeUrl(record.page_url);
            games.push({
                name: name,
                page_url: pageUrl ? pageUrl.href : null,
                download_links: downloadLinks,
                links: destinations,
                releases: releaseGroups(destinations),
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
        var summary = document.getElementById('linkStatusSummary');
        if (summary) {
            var statuses = typeof linkStatuses === 'object' && linkStatuses ? linkStatuses.links || {} : {};
            var missing = Object.keys(statuses).filter(function(key) { return statuses[key].status === 'missing'; }).length;
            summary.textContent = 'Filecrypt.cc links hidden. ' + missing.toLocaleString('en-US') + ' confirmed missing link' + (missing === 1 ? '' : 's') + ' hidden. Other links may be unchecked.';
        }
    }

    return { prepare: prepare, updateStatistics: updateStatistics, describeLink: describeLink, isMissing: isMissing, isExcluded: isExcluded, renderLinks: renderLinks, compareVersions: compareVersions };
}());
