# Release labels

For the full catalogue pass with automatic continuation and publication, use **Process full catalogue** and see [FULL_INDEXING.md](FULL_INDEXING.md). The individual refresh commands below remain manual review tools.


Filecrypt.cc is temporarily excluded from the catalogue and legacy redirect pages.
This is a display preference, not a deleted-file status. The source database is retained.
Filecrypt.co is a separate hostname and is not covered by this exclusion.

The catalogue joins `release-metadata.json` / `release-metadata.js` to each game's
source page. Explicit download rows preserve the release type, version, CUSA ID,
region, firmware, and original section/label. Supported direct-host links newly
found in those rows are added; confirmed missing links remain hidden. These labels
describe the source's claims, not verified package contents or working downloads.

The source adapter supports DLPS entry-content paragraphs and its publicly embedded
base64 labels. It does not execute third-party scripts, read comments as release
metadata, follow download buttons, or authenticate. Other page layouts remain
unidentified. Existing MediaFire filenames supply a fallback for explicit version,
CUSA, DLC, and backport markers; v1.00 alone does not imply a base game.

The UI groups links by release and sorts numeric versions (1.10 after 1.09).
"Highest listed update — check firmware" compares updates for the same CUSA,
region, and backport variant. Firmware lists may differ, so this is not a claim
that the newest file suits every console. Base games and DLC are not alternatives
to updates. A version in a section heading is never assigned to every file in it.
Unknown/conflicting labels stay explicit. Older options remain available.

## Refresh

Run **Actions → Refresh release metadata → Run workflow** (default 100 pages,
maximum 500). It prioritizes pages without saved metadata, waits at least three
seconds between pages, checkpoints results, and stops on network/access errors.
Download the `release-metadata-results` artifact and review `report.json` and
the per-page source labels before replacing both root metadata files together.
It does not automatically commit or run on a schedule.

Local equivalent: `python3 scripts/release_metadata.py --limit 100`.
Tests: `python3 -m unittest discover -s tests -v`.
Catalogue grouping tests: `node tests/test_catalog.cjs`.
The separate download-link checker also reads imported release links and skips
the excluded Filecrypt.cc host.

## Accounts

This public static site contains no 1fichier password, API key, login cookie, or
account proxy. Credits and authentication belong to the user's own 1fichier
session. Public source-page metadata refreshes do not consume CDN download credits.
