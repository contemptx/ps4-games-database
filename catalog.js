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
        else if (matchesHost(host, 'vikingfile.com') || matchesHost(host, 'vik1ngfile.site')) label = 'VikingFile';
        else if (matchesHost(host, 'mocha.my')) label = 'Mocha';
        else if (matchesHost(host, 'filekeeper.net')) label = 'FileKeeper';
        else if (matchesHost(host, 'rootz.so')) label = 'Rootz';
        else if (matchesHost(host, 'ranoz.gg')) label = 'Ranoz';
        else if (matchesHost(host, 'pixeldrain.com')) label = 'Pixeldrain';
        else if (matchesHost(host, 'datanodes.to')) label = 'DataNodes';
        else if (matchesHost(host, 'keeplinks.org')) label = 'KeepLinks (container)';
        return { url: url.href, host: host, label: label, group: group };
    }

    function statusKey(value) {
        var url = normalizeUrl(value);
        if (!url) return null;
        if (matchesHost(url.hostname, 'vikingfile.com') || matchesHost(url.hostname, 'vik1ngfile.site')) {
            var vikingId = url.pathname.match(/^\/f\/([a-zA-Z0-9]+)\/?$/);
            if (vikingId) return 'https://vikingfile.com/f/' + vikingId[1];
        }
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
        var sizes = typeof fileSizes === 'object' && fileSizes ? fileSizes.files : null;
        return !!(key && ((statuses && statuses[key] && statuses[key].status === 'missing') || (sizes && sizes[key] && sizes[key].status === 'missing')));
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
            var fields = ['kind', 'version', 'title_id', 'region', 'region_status', 'firmware', 'variant', 'edition', 'source_section', 'source_label', 'evidence', 'conflict'];
            var key = fields.map(function(field) { return meta[field] || ''; }).join('|');
            if (!index[key]) {
                index[key] = { metadata: meta, links: [] };
                groups.push(index[key]);
            }
            index[key].links.push(link);
            if (meta.kind === 'update' && meta.title_id && meta.region && meta.version && !meta.conflict) {
                var family = [meta.title_id, meta.region, meta.variant || '', meta.edition || ''].join('|');
                if (!versions[family]) versions[family] = [];
                if (versions[family].indexOf(meta.version) === -1) versions[family].push(meta.version);
            }
        });
        groups.forEach(function(group) {
            var m = group.metadata, family = [m.title_id, m.region, m.variant || '', m.edition || ''].join('|');
            var listed = versions[family] || [];
            group.newest = m.kind === 'update' && !!m.version && !m.conflict && listed.length > 1 && listed.every(function(v) { return compareVersions(m.version, v) >= 0; });
        });
        var order = { base: 0, update: 1, dlc: 2, fix: 3, patch: 4, bundle: 5 };
        groups.sort(function(a, b) {
            var left = a.metadata, right = b.metadata;
            var difference = (order[left.kind] === undefined ? 6 : order[left.kind]) - (order[right.kind] === undefined ? 6 : order[right.kind]);
            if (difference) return difference;
            if (left.title_id === right.title_id && left.region === right.region && left.version && right.version) return compareVersions(right.version, left.version);
            return 0;
        });
        return groups;
    }

    function sourceName(value) {
        var url = normalizeUrl(value);
        if (!url) return 'Unknown source';
        var host = url.hostname.replace(/^www\./, '');
        var names = { 'superpsx.com': 'SuperPSX', 'dlpsgame.com': 'DLPSGame', 'romsfun.com': 'RomsFun', 'arabicps4games.github.io': 'ArabicPS4Games' };
        return names[host] || host;
    }

    function renderLinks(container, game, newTab) {
        var source = document.createElement('div');
        source.className = 'source-label';
        source.textContent = 'Sources: ';
        (game.sources || [{name:game.source, page_url:game.page_url}]).forEach(function(item, index) {
            if (index) source.appendChild(document.createTextNode(' · '));
            var anchor = document.createElement(item.page_url ? 'a' : 'span');
            anchor.textContent = item.name;
            if (item.page_url) { anchor.href = item.page_url; anchor.rel = 'noopener noreferrer'; if (newTab) anchor.target = '_blank'; }
            source.appendChild(anchor);
        });
        container.appendChild(source);
        var recommendations = typeof catalogRecommendations === 'object' ? catalogRecommendations : null;
        var suggested = recommendations ? recommendations.analyze(game) : null;
        if (recommendations) recommendations.renderSummary(container, game, suggested, function() {
            container.textContent = ''; renderLinks(container, game, newTab);
        });
        var names = { base: 'Base game', update: 'Update', dlc: 'DLC', fix: 'Fix', patch: 'Language / mod patch', bundle: 'Combined package' };
        var orderedReleases = game.releases.slice();
        if (recommendations) orderedReleases.sort(function(a, b) { return recommendations.rank(a, suggested) - recommendations.rank(b, suggested); });
        orderedReleases.forEach(function(release) {
            var m = release.metadata, wrapper = document.createElement('div');
            wrapper.className = 'release-group release-' + (names[m.kind] && !m.conflict ? m.kind : 'unknown');
            var heading = document.createElement('div');
            heading.className = 'release-heading';
            var parts = [names[m.kind] || (m.evidence ? 'File — type unspecified' : 'Release details unknown')];
            var dlcCount = m.kind === 'dlc' && (m.source_label || '').match(/\bDLC\s*\((\d+)\)/i);
            if (dlcCount) parts[0] += ' (' + dlcCount[1] + ')';
            if (m.kind === 'patch' && m.source_label) parts.push(m.source_label);
            if (m.version) parts.push('v' + m.version);
            if (m.title_id) parts.push(m.title_id);
            if (m.region) parts.push(m.region);
            else parts.push(m.region_conflict ? 'Region conflict' : 'Region unknown');
            heading.textContent = parts.join(' · ');
            wrapper.appendChild(heading);
            if (release.source) {
                var origin = document.createElement('a');
                origin.className = 'release-detail';
                origin.textContent = release.source;
                origin.href = release.page_url;
                origin.rel = 'noopener noreferrer';
                if (newTab) origin.target = '_blank';
                wrapper.appendChild(origin);
            }
            if (recommendations) recommendations.decorateRelease(wrapper, release, suggested);
            if (release.newest && !recommendations) {
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
            if (m.region_conflict) details.push('Source and filename regions disagree');
            if (m.region_evidence && m.region_evidence.length) {
                var regionEvidence = document.createElement('span');
                regionEvidence.className = 'region-evidence';
                regionEvidence.textContent = m.region_conflict ? 'Review region evidence' : 'Region evidence';
                regionEvidence.title = m.region_evidence.map(function(e) { return e.source + ': ' + e.label; }).join('\n');
                regionEvidence.tabIndex = 0;
                wrapper.appendChild(regionEvidence);
            }
            if (details.length) {
                var note = document.createElement('div');
                note.className = 'release-detail';
                note.textContent = details.join(' · ');
                wrapper.appendChild(note);
            }
            if (m.source_label) wrapper.title = m.source_label;
            if (recommendations) recommendations.renderMirrorNote(wrapper, release, suggested.options.host);
            var hostCounts = Object.create(null);
            var orderedLinks = recommendations ? recommendations.orderedLinks(release, suggested.options.host) : release.links;
            var firstHost = recommendations ? recommendations.suggestedHost(release, suggested.options.host) : '';
            orderedLinks.forEach(function(link) {
                hostCounts[link.label] = (hostCounts[link.label] || 0) + 1;
                var button = document.createElement('a');
                button.setAttribute('href', link.url);
                button.className = 'download-btn btn-' + link.group;
                button.textContent = link.label + ' ' + hostCounts[link.label];
                if (recommendations && recommendations.host(link) === firstHost) {
                    button.className += ' preferred-mirror';
                    button.textContent += ' · Try first';
                }
                if (typeof catalogSizes !== 'undefined') button.textContent += ' · ' + catalogSizes.label(link.url);
                button.title = m.source_label ? m.source_label + '\n' + link.url : link.url;
                if (recommendations && recommendations.host(link) === firstHost) button.title += '\nPreferred host; this individual download may be unverified. Keep all required archive parts.';
                if (newTab) button.target = '_blank';
                button.rel = 'noopener noreferrer';
                wrapper.appendChild(button);
                if (typeof catalogSizes !== 'undefined') catalogSizes.addSelector(wrapper, link, game);
            });
            container.appendChild(wrapper);
        });
    }

    function renderTitle(container, game, newTab) {
        container.textContent = '';
        if (!game.page_url) { container.textContent = game.name; return; }
        var link = document.createElement('a');
        link.href = game.page_url;
        link.textContent = game.name;
        link.style.color = 'inherit';
        link.rel = 'noopener noreferrer';
        if (newTab) link.target = '_blank';
        container.appendChild(link);
    }

    function prepare(records) {
        var games = [], seenPages = Object.create(null);
        records.forEach(function(record) {
            if (!record || typeof record.name !== 'string') return;
            var name = record.name.trim();
            // A scraped URL is not a game title.
            if (!name || /^(?:https?:\/\/|www\.)/i.test(name)) return;
            var recordIdentity = record.catalog_id || record.page_url;
            if (recordIdentity && seenPages[recordIdentity]) return;

            var sourceLinks = record.download_links || {};
            var downloadLinks = { mediafire: [], '1file': [], other: [] };
            var destinations = [];
            var seen = Object.create(null);
            var pages = typeof releaseMetadata === 'object' && releaseMetadata ? releaseMetadata.pages || {} : {};
            var sourcePage = pages[record.page_url];
            var entries = Array.isArray(record.release_links) ? record.release_links : (sourcePage && Array.isArray(sourcePage.links) ? sourcePage.links : []);
            var metadata = Object.create(null), values = [];
            entries.forEach(function(entry) {
                var key = statusKey(entry.url);
                if (!key) return;
                var identityFields = ['kind', 'version', 'title_id', 'region', 'firmware', 'variant', 'edition', 'conflict'];
                var previousIdentity = metadata[key] && identityFields.map(function(field) { return metadata[key][field] || ''; }).join('|');
                var currentIdentity = identityFields.map(function(field) { return entry[field] || ''; }).join('|');
                if (metadata[key] && previousIdentity !== currentIdentity) {
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
                    if (typeof catalogRegions === 'object') {
                        var files = typeof fileSizes === 'object' && fileSizes.files || {};
                        link.release = catalogRegions.enrich(link.release, link.url, files[key]);
                    }
                    downloadLinks[link.group].push(link.url);
                    destinations.push(link);
            });

            // Count links the UI renders, rather than trusting scraped totals.
            if (destinations.length === 0) return;
            var pageUrl = normalizeUrl(record.page_url);
            if (recordIdentity) seenPages[recordIdentity] = true;
            games.push({
                name: name,
                source: record.source === 'ArabicPS4Games' ? record.source : sourceName(record.page_url),
                page_url: pageUrl ? pageUrl.href : null,
                download_links: downloadLinks,
                links: destinations,
                releases: releaseGroups(destinations),
                total_links: destinations.length
            });
        });
        return games;
    }


    function groupGames(games) {
        var grouped = [], byName = Object.create(null);
        var records = typeof igdbMetadata === 'object' && igdbMetadata.records || {};
        games.forEach(function(game) {
            // Strip platform/packaging suffixes only; retain editions and sequels.
            var name = game.name.replace(/\s+(?:PS4|FPKG|PKG)(?:\s+(?:PS4|FPKG|PKG|Download))*\s*$/i, '').trim();
            var key = name.toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9\u00c0-\uffff]+/g, ' ').trim();
            var meta = records[game.name] || {};
            var target = byName[key];
            if (target && target.igdb_id && meta.igdb_id && target.igdb_id !== meta.igdb_id) {
                key += '|igdb:' + meta.igdb_id; target = byName[key];
            }
            if (!target) {
                target = {name:name, source:game.source, page_url:game.page_url, sources:[], aliases:[],
                    links:[], releases:[], total_links:0, download_links:{mediafire:[], '1file':[], other:[]}};
                byName[key] = target; grouped.push(target);
            }
            if (meta.igdb_id && !target.igdb_id) { target.igdb_id = meta.igdb_id; target.metadata_name = game.name; }
            target.aliases.push(game.name);
            if (!target.sources.some(function(s) { return s.page_url === game.page_url && s.name === game.source; })) {
                target.sources.push({name:game.source, page_url:game.page_url});
            }
            game.releases.forEach(function(release) {
                var copy = {};
                Object.keys(release).forEach(function(k) { copy[k] = release[k]; });
                copy.source = game.source; copy.page_url = game.page_url;
                target.releases.push(copy);
            });
            target.links = target.links.concat(game.links);
            target.total_links += game.total_links;
            hosts.forEach(function(h) { target.download_links[h] = target.download_links[h].concat(game.download_links[h] || []); });
        });
        return grouped;
    }

    function identityCounts(games) {
        var records = typeof gameIdentities === 'object' && gameIdentities ? gameIdentities.records : null;
        if (!records) return null;
        var ids = Object.create(null), matched = 0, unresolved = 0, other = 0;
        games.forEach(function(game) {
            var record = records[game.name];
            if (!record) { unresolved++; return; }
            var inputId = Object.prototype.hasOwnProperty.call(record, 'input_igdb_id') ? record.input_igdb_id : record.igdb_id;
            if ((Object.prototype.hasOwnProperty.call(record, 'input_igdb_id') && (game.igdb_id || null) !== (inputId || null)) ||
                (!Object.prototype.hasOwnProperty.call(record, 'input_igdb_id') && game.igdb_id && inputId && game.igdb_id !== inputId)) { unresolved++; return; }
            if (record.source_urls && record.source_urls.length && !(game.sources || []).some(function(s) { return record.source_urls.indexOf(s.page_url) !== -1; })) { unresolved++; return; }
            if (record.status === 'identified' && (typeof record.canonical_id === 'number' || /^local:[a-z0-9-]+$/.test(record.canonical_id || ''))) {
                ids[record.canonical_id] = true; matched++;
            } else if (record.status === 'non_game') other++;
            else unresolved++;
        });
        return {unique: Object.keys(ids).length, matched: matched, unresolved: unresolved, other: other,
            duplicateListings: matched - Object.keys(ids).length};
    }

    function updateStatistics(games) {
        if (typeof catalogSizes !== 'undefined') catalogSizes.init(games);
        var links = games.reduce(function(total, game) { return total + game.total_links; }, 0);
        var regionSummary = document.getElementById('regionSummary');
        if (regionSummary && typeof catalogRegions === 'object') {
            var regionCounts = catalogRegions.summary(games);
            regionSummary.textContent = regionCounts.identified_links.toLocaleString('en-US') + ' links have region evidence · ' +
                regionCounts.unknown_links.toLocaleString('en-US') + ' unknown or conflicting. Region labels describe releases, not languages.';
        }
        var gameCount = games.length.toLocaleString('en-US');
        var linkCount = links.toLocaleString('en-US');
        var identities = identityCounts(games);
        document.getElementById('totalGames').textContent = identities ? identities.unique.toLocaleString('en-US') : gameCount;
        var countLabel = document.getElementById('gameCountLabel');
        if (countLabel) countLabel.textContent = identities ? 'Unique games identified' : 'Game listings';
        var identitySummary = document.getElementById('identitySummary');
        if (identitySummary) identitySummary.textContent = identities ?
            gameCount + ' listings · ' + identities.duplicateListings.toLocaleString('en-US') + ' duplicate/edition listings counted once · ' +
            identities.unresolved.toLocaleString('en-US') + ' listings need identity review · ' + identities.other.toLocaleString('en-US') +
            ' collections, add-ons or other entries counted separately. Includes older-console conversions and other-platform identities. Unresolved listings are excluded from the unique count. Remakes/remasters remain distinct.' :
            'Unique-game identities unavailable; showing the listing count.';
        document.getElementById('totalLinks').textContent = linkCount;
        document.getElementById('catalogTotals').textContent = (identities ? identities.unique.toLocaleString('en-US') + ' Unique Games Identified | ' : '') + gameCount + ' Game Listings | ' + linkCount + ' Download Links';
        var sources = Object.create(null);
        games.forEach(function(game) { (game.sources || [{name:game.source}]).forEach(function(s) { sources[s.name] = true; }); });
        var sourceFilter = document.getElementById('sourceFilter');
        if (sourceFilter) {
            var options = sourceFilter.querySelectorAll('option');
            for (var i = 0; i < options.length; i++) {
                if (options[i].value && !sources[options[i].value]) options[i].parentNode.removeChild(options[i]);
            }
        }
        var sourceCount = document.getElementById('totalSources');
        if (sourceCount) sourceCount.textContent = Object.keys(sources).length + ' Sources';
        var coverage = document.getElementById('sourceCoverage');
        if (coverage && typeof superpsxCatalog === 'object') {
            coverage.textContent = 'SuperPSX: ' + superpsxCatalog.records.length + ' listings indexed; coverage is partial. Source labels do not confirm file availability.';
        }
        var indexing = document.getElementById('indexingSummary');
        if (indexing && typeof indexProgress === 'object') {
            var processed = 0, total = 0;
            Object.keys(indexProgress.sources || {}).forEach(function(key) {
                if (key === 'mediafire') return;
                processed += indexProgress.sources[key].processed;
                total += indexProgress.sources[key].total;
            });
            indexing.textContent = 'Full source pass: ' + processed.toLocaleString() + ' / ' + total.toLocaleString() + ' pages processed. Some sources or labels may remain unresolved.';
        }
        var summary = document.getElementById('linkStatusSummary');
        if (summary) {
            var statuses = typeof linkStatuses === 'object' && linkStatuses ? linkStatuses.links || {} : {};
            var missingKeys = Object.create(null);
            Object.keys(statuses).forEach(function(key) { if (statuses[key].status === 'missing') missingKeys[key] = true; });
            if (typeof fileSizes === 'object' && fileSizes.files) Object.keys(fileSizes.files).forEach(function(key) { if (fileSizes.files[key].status === 'missing') missingKeys[key] = true; });
            var missing = Object.keys(missingKeys).length;
            summary.textContent = 'Filecrypt.cc links hidden. ' + missing.toLocaleString('en-US') + ' confirmed missing link' + (missing === 1 ? '' : 's') + ' hidden. Other links may be unchecked.';
        }
    }

    return { statusKey: statusKey, prepare: prepare, groupGames: groupGames, identityCounts: identityCounts, updateStatistics: updateStatistics, describeLink: describeLink, isMissing: isMissing, isExcluded: isExcluded, renderLinks: renderLinks, renderTitle: renderTitle, compareVersions: compareVersions };
}());
