# Download file metadata

`Index file sizes` checkpoints into file-sizes.json/js and publishes each batch to Pages.
It operates on exactly the listings included by catalog.js, including release links and all sources.
The first push runs a short three-minute pass, then up to 39 further finite batches run automatically
while work remains. Manual runs resume unchecked links. Access-held hosts stay paused, not retried
on every batch. Unsupported/container links remain explicitly unknown.

Collected: host-reported size in bytes, exact/estimated precision, filename and evidence, explicitly
named checksum fields when returned, timestamp, multipart number inferred from filename (never a
claim that all archive parts exist). No downloaded-file hash calculation or package-content validation.

Supported APIs: VikingFile check-file (POST, public), Pixeldrain file info (GET, public), optional
1fichier file/info.cgi (POST). The latter requires repository Actions secret FICHIER_API_KEY.
Only public metadata fields are retained. No download token requests, private account listings,
file transfers or CDN credit consumption are requested. No username/password login automation.
1fichier and MediaFire's previous public-access restrictions are preserved.

Other supported host landing pages are parsed conservatively for explicit File size labels and
JSON-LD contentSize. Redirects are not followed; responses are bounded; binary/attachment responses
are closed without reading bodies. HTTP errors, CAPTCHA and network failures never prove deletion.
A host restriction stops its queue and is checkpointed. API explicit missing results remain recorded
in file-sizes.json; this pass does not rewrite the separate link availability manifest.

Rounded webpage units are estimates: GB=10^9, GiB=2^30. HTML response Content-Length is NEVER the
file size. Unknown sizes are not zero. Stale/unavailable metadata is not fabricated.

UI includes size beside each host link and a selected-download calculator. Select one mirror,
every required multipart file, the compatible update and desired DLC. Selections survive pagination,
search and sorting in the current page, but not reload. Canonical URLs and matching host-reported
checksum+exact size are deduplicated. Filename+size alone is not treated as proof of identity.
The all-indexed-files aggregate includes mirrors, regions and older releases that cannot be proven
identical. Neither aggregate is installed console space or a complete unique-game library estimate.

Sources: https://vikingfile.com/api ; https://pixeldrain.com/api ;
https://github.com/rclone/rclone/blob/master/backend/fichier/api.go
