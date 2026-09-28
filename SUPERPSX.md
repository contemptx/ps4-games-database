# SuperPSX source

For the full catalogue pass with automatic continuation and publication, use **Process full catalogue** and see [FULL_INDEXING.md](FULL_INDEXING.md). The individual refresh commands below remain manual review tools.


`scripts/superpsx.py` discovers PS4 article candidates from public post sitemaps, verifies a PS4 article heading, follows only its explicitly linked same-site `/dll-…/` pages, and extracts approved download hosts from labelled table rows. It never visits package URLs or uses an account. Premium/CDN credentials must never go in this public repository or its frontend.

Base game, update, DLC, language/mod patch, version, CUSA, region and firmware labels come from the download table. Edition headers are scoped to their table; named language patches are distinct from game updates; missing fields stay unknown. Mirrors share row labels. KeepLinks destinations are labelled as containers and are not automatically resolved. SuperPSX listings keep their own source pages, so similarly named games and different editions are not merged by title.

The browser loads `superpsx-catalog.js`, applies the shared missing-link and Filecrypt.cc filters, and offers a source selector. File availability remains unverified until the existing link checker finds host evidence. New 1fichier/MediaFire links are included in that checker's candidate set.

## Refresh

Run **Index SuperPSX source** in GitHub Actions, or:

```sh
python3 scripts/superpsx.py --limit 100
```

The default is 100 articles, with a maximum of 500 per run. Each article can require additional download-page requests. Requests respect robots rules, stay on the source host, wait at least two seconds, use bounded responses, and stop on restrictions or network failures. The WordPress API is excluded. Cached pages are local to one run; remove `.superpsx-cache` before deliberately rechecking old pages locally.

Review `superpsx-results/report.json`, then import both generated `superpsx-catalog.json` and `superpsx-catalog.js` into the repository together. Subsequent runs prioritise unchecked candidates using the imported manifest. The workflow publishes a reviewable artifact; it does not change the website automatically.

Coverage is partial: sitemap PS4 hints can miss opaque slugs/images, unlabelled formats are skipped, and a bounded batch is not a complete site crawl. Counts are source listings, not distinct game identities. No-links pages are omitted. The report records checked candidates and any stopping reason.
