// Package-region evidence only. Languages and a CUSA number do not establish region.
var catalogRegions = (function() {
    var labels = {USA:'USA / North America', EUR:'Europe', JPN:'Japan', ASIA:'Asia',
        KOR:'Korea', CHN:'China', AUS:'Australia', NZL:'New Zealand', UK:'United Kingdom',
        WORLD:'Worldwide'};
    var aliases = {US:'USA', USA:'USA', 'NORTH AMERICA':'USA', 'NORTH AMERICAN':'USA', 'UNITED STATES':'USA',
        EU:'EUR', EUR:'EUR', EUROPE:'EUR', EUROPEAN:'EUR', JP:'JPN', JPN:'JPN', JAPAN:'JPN',
        ASIA:'ASIA', ASIAN:'ASIA', KR:'KOR', KOR:'KOR', KOREA:'KOR', 'SOUTH KOREA':'KOR',
        CN:'CHN', CHN:'CHN', CHINA:'CHN', AU:'AUS', AUS:'AUS', AUSTRALIA:'AUS',
        NZ:'NZL', NZL:'NZL', 'NEW ZEALAND':'NZL', UK:'UK', 'UNITED KINGDOM':'UK',
        WORLD:'WORLD', WORLDWIDE:'WORLD'};

    function explicit(value) {
        var parts = String(value || '').toUpperCase().replace(/_/g, ' ').split(/\s*[,/|+&;]\s*/);
        var result = [];
        parts.forEach(function(part) {
            var code = aliases[part.trim()];
            if (code && result.indexOf(code) === -1) result.push(code);
        });
        return result.sort();
    }
    function tokens(text) {
        text = String(text || '').replace(/_/g, ' ');
        var found = [], match;
        function add(values) { values.forEach(function(x) { if (found.indexOf(x) === -1) found.push(x); }); }
        // Long uppercase codes are release markers. Avoid matching "The Last of Us".
        var codes = /\b(USA|EUR|JPN|ASIA|KOR|CHN|AUS|NZL)\b/g;
        while ((match = codes.exec(text))) add([match[1]]);
        var brackets = /[\[({]([^\])}]+)[\])}]/g;
        while ((match = brackets.exec(text))) add(explicit(match[1]));
        var tagged = /\bRegion\s*[:=-]\s*([a-z /,+&|]+?)(?=\s{2}|[;\]\n()]|$)/ig;
        while ((match = tagged.exec(text))) add(explicit(match[1]));
        return found.sort();
    }
    function filename(url) {
        try {
            var parsed = new URL(url);
            if (!/^(?:www\.)?mediafire\.com$/i.test(parsed.hostname)) return '';
            var match = parsed.pathname.match(/^\/file\/[^/]+\/([^/]+)/);
            return match ? decodeURIComponent(match[1]) : '';
        } catch (error) { return ''; }
    }
    function enrich(metadata, url, file) {
        var result = {}, evidence = [];
        Object.keys(metadata || {}).forEach(function(key) { result[key] = metadata[key]; });
        function add(value, source, structured) {
            var regions = structured ? explicit(value) : tokens(value);
            if (regions.length) evidence.push({source:source, label:String(value).slice(0, 400), regions:regions});
        }
        add(result.region, 'Source region label', true);
        add(result.source_section, 'Source section', false);
        add(result.source_label, 'Source link label', false);
        add(result.filename, 'Source filename', false);
        if (file && file.filename) add(file.filename, file.filename_evidence || 'Indexed host filename', false);
        add(filename(url), 'URL filename', false);
        var regions = evidence.length ? evidence[0].regions.slice() : [];
        evidence.slice(1).forEach(function(item) {
            regions = regions.filter(function(code) { return item.regions.indexOf(code) !== -1; });
        });
        result.region_conflict = evidence.length > 1 && !regions.length;
        result.regions = regions;
        result.region = regions.join(' / ');
        result.region_evidence = evidence;
        result.region_status = result.region_conflict ? 'conflict' : regions.length > 1 ? 'multiple' : regions.length ? 'identified' : 'unknown';
        return result;
    }
    function matches(metadata, region) {
        if (!region) return true;
        var m = metadata || {};
        if (region === 'unknown') return !m.regions || !m.regions.length;
        if (m.region_conflict) return false;
        return (m.regions || explicit(m.region)).indexOf(region) !== -1;
    }
    function summary(games) {
        var total = 0, known = 0, conflicts = 0, knownGames = 0;
        games.forEach(function(game) {
            var hasRegion = false;
            game.links.forEach(function(link) {
                total++;
                if (link.release.region_conflict) conflicts++;
                if ((link.release.regions || []).length) { known++; hasRegion = true; }
            });
            if (hasRegion) knownGames++;
        });
        return {links:total, identified_links:known, unknown_links:total-known, conflicting_links:conflicts,
            listings:games.length, listings_with_region:knownGames};
    }
    return {labels:labels, explicit:explicit, tokens:tokens, enrich:enrich, matches:matches, summary:summary};
}());
