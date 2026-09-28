# Checking file availability

`link-status.json` records observations without deleting source database entries.
`link-status.js` contains the same data for the static pages. Only `missing`
records are hidden. Tracking parameters on 1fichier links share one file identity.

The initial Ultrawings observation comes from the user's 28 September 2026
screenshot: 1fichier explicitly says the requested file does not exist.

## Run a check

Open **Actions → Check download links → Run workflow**. Start with 100 links.
Download the `link-check-results` artifact when it finishes. Alternatively run:

```sh
python3 scripts/check_links.py --limit 100
```

The checker uses public landing pages, not download requests. It requires no
account, API key, or CDN credits. It spaces requests by at least five seconds per
host and stops checking a host when it receives a restriction, rate limit, or
network/gateway error. Ordinary pages without recognized evidence remain
unknown. It does not solve CAPTCHAs or retry through other IPs.

| Status | Meaning |
| --- | --- |
| `missing` | A supported host explicitly reports that the file does not exist. |
| `present` | A MediaFire download page was observed; file contents were not verified. |
| `restricted` | Login/IP restrictions, denied access, or a browser challenge. |
| `rate_limited` | The host asks the client to stop or slow down. |
| `unknown` | Network failure, generic error, unsupported response, or ambiguous result. |

Only 1fichier and MediaFire currently have missing-file detectors. Filecrypt can
be checked for restrictions, but a container loading does not establish whether
its underlying files exist. Other hosts remain unchecked. HTTP 404 alone never
marks a file missing. An HTTP 200 gateway error never marks one present.

## Publish reviewed results

Review `report.json`, then copy **both** generated `link-status.json` and
`link-status.js` into the repository root and commit them together. The normal
Pages deployment publishes the update. The checking workflow has read-only
repository permissions and does not publish or change the database itself.

Future checks prefer unchecked and older entries once their results have been
imported. The report retains timestamps and reasons. Missing entries are skipped
by normal runs; to recheck a restored file, remove its status record from both
status files first. Confirmed-missing records remain hidden during inconclusive
checks, and the original source URLs remain recoverable in the raw database.
