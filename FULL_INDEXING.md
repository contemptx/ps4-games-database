# Full catalogue processing

The **Process full catalogue** GitHub Actions workflow runs a finite pass through the current source queues. Each successful batch validates and commits its results, dispatches the Pages deployment, and dispatches the next batch while runnable work remains. The default ceiling is 120 batches, with 100 items per source per batch. A batch has a 20-minute collection budget and a 45-minute job timeout. It stops on exhausted queues, no progress, paused sources, validation/push failure or the finite batch ceiling.

GitHub's documented `workflow_dispatch` exception permits explicit continuation with `GITHUB_TOKEN`: https://docs.github.com/en/actions/concepts/security/github_token . A token-authenticated push does not trigger Pages by itself, so the workflow explicitly dispatches `static.yml` after committing. No external account credentials are involved.

## Queues and evidence

- DLPS: all 5,978 distinct source pages from the original catalogue. The existing 102 parsed pages seed the checkpoint.
- SuperPSX: all posts in its current public post sitemaps, including opaque slugs and other platforms. The article heading must establish PS4 before importing its game links. Existing results are retained.
- ArabicPS4Games: its full PS4 index and the known PS4 pagination pages. Named figures remain associated with their links; navigation URLs are not game names. Supported direct hosts can become listings. Advertising shorteners remain unresolved.
- Public JustPaste lists explicitly linked by the Arabic index: source labels are parsed from their article content. A destination visibly encoded in a public redirect href is decoded as data; no third-party script is executed and no challenge is bypassed.
- RomsFun: paused following HTTP 403 responses during the source audit. Existing catalogue links remain, with details unknown.
- MediaFire: public landing-page checks where accessible. Newly discovered links are enqueued before deciding whether to continue. A missing file requires explicit host evidence. Network errors do not mean deleted.

Readers follow robots rules, use one serial request stream per source, wait two or three seconds between source requests (five seconds for host checks), bound response sizes and timeouts, reject off-source redirects, and stop a source on restrictions or network failures. Independent sources can run concurrently. No package contents, account sessions, CAPTCHA workarounds or CDN credits are used.

`index-state.json` holds durable per-item checkpoints. Data is written before the item is marked processed. `index-progress.json` / `.js` provides the public coverage summary shown in `processing.html`. `source-review.json` preserves named entries with unresolved shorteners/link lists. A processed page may still need review; it is not a completeness or file-availability assertion. Known source-page deletion does not delete a file record or mark its download missing.

Source labels distinguish base games, updates, DLC, fixes, bundles and language patches. Unlabelled recognised links are retained as unknown; explicit filename evidence can supplement them. Matching CUSA, region and edition are needed before comparing updates. Filecrypt.cc stays excluded.

Data script URLs are versioned by content on each publication. The progress page also fetches a fresh report every minute while open.

The frontend renders 50 listings at a time and searches the full in-memory catalogue, including versions, CUSA IDs and release labels. Counts describe source listings, not deduplicated game identities across different sites or editions.

## Operation and recovery

Start **Actions → Process full catalogue → Run workflow** on `main`. Existing checkpoints resume automatically. Set `batches_left=1` for a single batch. Do not run the legacy manual collectors concurrently with this publisher.

Cancel the active run to stop the chain. Failed runs upload checkpoint files for seven days; successful checkpoints are already committed to the repository. Git conflicts stop publication rather than overwrite intervening work. Inspect source `held` reasons and unresolved reports before changing a paused source; restrictions are not automatically retried from other runners. A new source pass or retry requires an explicit state reset after the cause is addressed.

Local smoke test in a copy of the data:

```sh
python3 scripts/full_index.py --root /path/to/copy --limit 3 --minutes 5
python3 scripts/validate_index.py
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_catalog.cjs
node tests/test_paging.cjs
```
