// Suggestions use source labels, never a claim that package bytes are compatible.
var catalogRecommendations = (function() {
    var selections = Object.create(null);
    var preferenceKey = 'ps4-release-preferences-v1';
    var defaults = { firmware: '', host: '1fichier.com' };
    var testedHosts = ['1fichier.com', 'mediafire.com', 'pixeldrain.com'];

    function version(value) {
        return /^\d+(?:\.\d+)*$/.test(value || '') ? String(value).split('.').map(Number) : null;
    }
    function compare(a, b) {
        var x = version(a), y = version(b);
        if (!x || !y) return 0;
        for (var i = 0; i < Math.max(x.length, y.length); i++) {
            var difference = (x[i] || 0) - (y[i] || 0);
            if (difference) return difference;
        }
        return 0;
    }
    function normal(value) { return String(value || '').trim().toUpperCase().replace(/\s+/g, ' '); }
    function region(value) {
        var r = normal(value);
        return r === 'EU' ? 'EUR' : r === 'US' ? 'USA' : r;
    }
    function host(link) {
        try { return new URL(link.url).hostname.toLowerCase().replace(/^www\./, ''); }
        catch (error) { return ''; }
    }
    function hostRank(link, preference) {
        var h = host(link);
        if (preference && h === preference) return 0;
        var index = testedHosts.indexOf(h);
        return index < 0 ? 10 : index + 1;
    }
    function orderedLinks(release, preference) {
        return release.links.slice().sort(function(a, b) { return hostRank(a, preference) - hostRank(b, preference); });
    }
    function suggestedHost(release, preference) {
        var links = orderedLinks(release, preference);
        return links.length && hostRank(links[0], preference) < 10 ? host(links[0]) : '';
    }
    function firmwareState(metadata, target) {
        if (!target) return 'unchecked';
        if (!/^\d{1,2}\.\d{2}$/.test(target)) return 'invalid';
        if (metadata.conflict || !metadata.firmware) return 'unknown';
        var label = String(metadata.firmware).trim().toLowerCase();
        var tokens = label.split('/');
        // A slash list/backport label is a list of stated targets, not a minimum.
        var minimum = tokens.length === 1 && !metadata.variant;
        var parsed = tokens.map(function(token) {
            var m = token.trim().match(/^(\d{1,2})\.(\d{2}|xx)(\+)?$/);
            if (!m) return null;
            if (m[2] === 'xx') return !m[3] ? Number(m[1]) === Number(target.split('.')[0]) : null;
            return m[3] || minimum ? compare(target, m[1] + '.' + m[2]) >= 0 : compare(target, m[1] + '.' + m[2]) === 0;
        });
        if (parsed.indexOf(true) !== -1) return 'fits';
        return parsed.indexOf(null) !== -1 ? 'unknown' : 'not-listed';
    }
    function familyKey(release) {
        var m = release.metadata || {};
        if (m.conflict || m.region_conflict || (m.regions && m.regions.length !== 1) || !/^CUSA\d{5}$/.test(normal(m.title_id)) || !region(m.region) || !release.page_url) return null;
        // Keep source sections and editions separate: the same CUSA alone is insufficient.
        return JSON.stringify([normal(m.title_id), region(m.region), normal(m.edition), release.page_url, normal(m.source_section)]);
    }
    function settings() {
        if (typeof document === 'undefined') return {firmware: defaults.firmware, host: defaults.host};
        var firmware = document.getElementById('consoleFirmware'), preference = document.getElementById('preferredHost');
        return {firmware: firmware ? firmware.value.trim() : '', host: preference ? preference.value : defaults.host};
    }
    function savePreferences() {
        var options = settings();
        var input = document.getElementById('consoleFirmware');
        var invalid = options.firmware && !/^\d{1,2}\.\d{2}$/.test(options.firmware);
        input.setAttribute('aria-invalid', invalid ? 'true' : 'false');
        document.getElementById('recommendationHelp').textContent = invalid ?
            'Enter firmware as two decimal places, e.g. 9.00. Suggestions are paused until corrected.' :
            'Blank firmware: requirements unchecked. Suggestions use source labels; all releases remain available.';
        if (!invalid) { try { localStorage.setItem(preferenceKey, JSON.stringify(options)); } catch (error) {} }
    }
    function init() {
        var options = defaults;
        try { options = JSON.parse(localStorage.getItem(preferenceKey)) || defaults; } catch (error) {}
        var input = document.getElementById('consoleFirmware'), preference = document.getElementById('preferredHost');
        if (!input || !preference) return;
        input.value = /^\d{1,2}\.\d{2}$/.test(options.firmware || '') ? options.firmware : '';
        preference.value = testedHosts.indexOf(options.host) !== -1 ? options.host : options.host === '' ? '' : defaults.host;
        savePreferences();
    }
    function gameKey(game) { return JSON.stringify([game.name, game.igdb_id || '']); }
    function eligible(release, options) {
        return !options.firmware || firmwareState(release.metadata, options.firmware) === 'fits';
    }
    function choose(releases, options) {
        return releases.filter(function(r) { return eligible(r, options); }).slice().sort(function(a, b) {
            var x = a.metadata, y = b.metadata;
            if (!!version(x.version) !== !!version(y.version)) return version(x.version) ? -1 : 1;
            var v = compare(y.version, x.version);
            if (v) return v;
            if (!!x.variant !== !!y.variant) return x.variant ? 1 : -1;
            return hostRank(orderedLinks(a, options.host)[0] || {}, options.host) - hostRank(orderedLinks(b, options.host)[0] || {}, options.host);
        })[0] || null;
    }
    function analyze(game, options) {
        options = options || settings();
        var families = [], byKey = Object.create(null);
        var releases = game.recommendationReleases || game.releases || [];
        releases.forEach(function(release) {
            var key = familyKey(release), m = release.metadata || {};
            if (!key || ['base', 'update', 'dlc'].indexOf(m.kind) < 0) return;
            if (!byKey[key]) { byKey[key] = {key: key, base: [], update: [], dlc: []}; families.push(byKey[key]); }
            byKey[key][m.kind].push(release);
        });
        families = families.filter(function(f) { return f.base.length > 0; });
        families.forEach(function(f) {
            f.chosenBase = choose(f.base, options);
            var baseVersion = f.chosenBase && f.chosenBase.metadata.version;
            f.chosenUpdate = f.chosenBase ? choose(f.update.filter(function(r) {
                return version(r.metadata.version) && (!version(baseVersion) || compare(r.metadata.version, baseVersion) > 0);
            }), options) : null;
            f.hostScore = f.chosenBase ? hostRank(orderedLinks(f.chosenBase, options.host)[0] || {}, options.host) : 100;
        });
        // Do not compare update version numbers across different title IDs/editions.
        families.sort(function(a, b) {
            return a.hostScore - b.hostScore || Number(!!b.chosenUpdate) - Number(!!a.chosenUpdate);
        });
        var wanted = selections[gameKey(game)];
        var selected = families.filter(function(f) { return f.key === wanted; })[0] || families[0] || null;
        return {families: families, family: selected, base: selected && selected.chosenBase,
            update: selected && selected.chosenUpdate, dlc: selected && selected.chosenBase ? selected.dlc : [], options: options};
    }
    function rank(release, result) {
        if (release === result.base) return 0;
        if (release === result.update) return 1;
        if (result.dlc.indexOf(release) !== -1) return 2;
        return 3;
    }
    function element(tag, className, text) {
        var e = document.createElement(tag); e.className = className;
        if (text) e.textContent = text;
        return e;
    }
    function renderSummary(container, game, result, refresh) {
        var box = element('div', 'release-plan');
        box.appendChild(element('div', 'release-plan-title', 'Suggested download set'));
        var family = result.family;
        if (!family) {
            box.appendChild(element('p', 'release-plan-note', 'No automatic selection: base-game, title ID or region details are incomplete. Check the source page.'));
            container.appendChild(box); return;
        }
        var label = element('label', 'release-family-label', 'Release family ');
        var select = element('select', 'release-family');
        select.setAttribute('aria-label', 'Release family for ' + game.name);
        result.families.forEach(function(f) {
            var r = f.chosenBase || f.base[0], m = r.metadata;
            var option = document.createElement('option'); option.value = f.key;
            option.textContent = m.title_id + ' · ' + region(m.region) + ' · ' + (r.source || 'Source') +
                (m.edition ? ' · ' + m.edition : '') + (result.families.length > 1 && m.source_section ? ' · ' + m.source_section : '');
            option.selected = f.key === family.key; select.appendChild(option);
        });
        select.addEventListener('change', function() { selections[gameKey(game)] = select.value; refresh();
            var replacement = container.querySelector('.release-family'); if (replacement) replacement.focus(); });
        label.appendChild(select); box.appendChild(label);
        if (!result.base) {
            box.appendChild(element('p', 'release-plan-note', 'No base meets the stated firmware requirements for this family. Missing labels and bases that rely on a separate backport need source-page review.'));
        } else {
            var summary = ['Base' + (result.base.metadata.version ? ' v' + result.base.metadata.version : ' (version unknown)')];
            summary.push(result.update ? 'Update v' + result.update.metadata.version : 'No newer update selected');
            summary.push(result.dlc.length + ' related DLC group' + (result.dlc.length === 1 ? '' : 's'));
            box.appendChild(element('p', 'release-plan-selection', summary.join(' · ')));
            if (family.update.some(function(r) { return !version(r.metadata.version); })) {
                box.appendChild(element('p', 'release-plan-note', 'Some update versions are unknown and cannot be ranked.'));
            }
        }
        var note = result.options.firmware ? 'Firmware checked against the listed labels only.' : 'Choose your console firmware above to check requirements.';
        box.appendChild(element('p', 'release-plan-note', note + ' Same title ID, region and source section; package compatibility is unverified. Check DLC update requirements on the source page.'));
        container.appendChild(box);
    }
    function decorateRelease(wrapper, release, result) {
        var text = '';
        if (release === result.base) text = 'Suggested base';
        else if (release === result.update) text = result.options.firmware ? 'Latest matching update for listed firmware' : 'Latest listed matching update';
        else if (result.dlc.indexOf(release) !== -1) text = 'Related DLC · check requirements';
        if (text) {
            wrapper.className += ' release-suggested';
            wrapper.appendChild(element('span', 'release-recommended', text));
        }
        var state = firmwareState(release.metadata, result.options.firmware);
        if (state !== 'unchecked') {
            var labels = {fits:'Listed firmware fits', 'not-listed':'Firmware does not match stated label', unknown:'Firmware needs review', invalid:'Enter a valid console firmware'};
            wrapper.appendChild(element('span', 'firmware-status firmware-' + state, labels[state]));
        }
    }
    function renderMirrorNote(wrapper, release, preference) {
        if (release.links.length < 2) return;
        wrapper.appendChild(element('p', 'release-detail mirror-note', 'Links grouped by the source. Different hosts may be mirrors; multiple links on one host may be required parts.'));
    }
    return { analyze:analyze, firmwareState:firmwareState, compare:compare, familyKey:familyKey,
        settings:settings, init:init, savePreferences:savePreferences, renderSummary:renderSummary,
        decorateRelease:decorateRelease, orderedLinks:orderedLinks, suggestedHost:suggestedHost,
        host:host, rank:rank, renderMirrorNote:renderMirrorNote };
}());
