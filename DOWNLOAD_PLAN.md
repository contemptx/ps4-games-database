# Server download plan

Agreed destination and selection policy, 30 September 2026 (Asia/Manila).

Status: this document records the planned server layout. The bulk-download coordinator and workers have not been deployed. Server addresses, access, available capacity and a combined traffic budget are still needed before bulk transfers. The existing host-test scripts are diagnostics, not a bulk-download service.

## Destination

Use `/mnt/storage/PS4/game` on every participating Ubuntu server. Each unique game has its own folder. Keep that game's selected base, matching updates, DLC and all required archive parts on the same server.

The game folder uses its readable canonical title. Store its reviewed canonical identity in `game.json` and the central queue. Add an identity suffix when different games have the same normalized folder name. Persist assigned folder names so later metadata changes do not create a second copy.

The following paths are relative to `/mnt/storage/PS4/game`. Angle-bracket values and version numbers are illustrative, not real catalogue assignments.

| Content | Path |
| --- | --- |
| Base game | `<Game>/EUR/<CUSA>/Base/` |
| Original update | `<Game>/EUR/<CUSA>/Updates/v1.32/Original/` |
| Update with a 9.00 backport | `<Game>/EUR/<CUSA>/Updates/v1.32/Backport-FW9.00/` |
| DLC | `<Game>/EUR/<CUSA>/DLC/<DLC name and content ID>/` |
| Separate fix, when the source requires one | `<Game>/EUR/<CUSA>/Fixes/<version and variant>/` |
| USA release when selected | `<Game>/USA/<CUSA>/Base/` (same Updates/DLC/Fixes layout) |
| Local game and file manifest | `<Game>/game.json` |

Create only the folders needed by selected files. A region preference does not request duplicate regional copies. Use another region folder when that release is selected or an additional regional release is explicitly required.

CUSA and region identify a candidate family, not proof that arbitrary packages are compatible. The manifest also records edition, source release and the selected base/update pairing. If multiple incompatible editions or dumps with the same CUSA must be retained, insert a stable `Release-<key>` folder beneath the CUSA so each has its own Base/Updates/DLC/Fixes directories.

Keep multipart filenames and numbering intact. Download every required part of the chosen archive; treat a mirror as an alternative only when there is evidence it contains the same file or complete archive set. Different backports or files with the same name must never silently overwrite each other.

Firmware labels belong to the individual file/variant. A shared file compatible with both 9.00 and 11.00 is stored once, with both supported targets recorded in the manifest. An `Original` folder describes the source's unbackported variant; it does not certify compatibility with any particular firmware.

## Selection policy

- Use reviewed unique game identities and prioritise PS4/PS VR reference matches. Unresolved identities and platform/conversion ambiguities need review.
- Accept EUR and USA releases, require evidence for English language availability, and prefer EUR when completeness, compatibility and availability are otherwise equivalent. Other regions remain review candidates rather than being silently excluded from the catalogue.
- Track 9.00 and 11.00 as separate compatibility targets. Preserve source claims separately from package metadata and actual testing. Unknown or conflicting requirements require review; a backport label does not establish universal compatibility.
- Prefer one complete compatible base-game release. Choose the latest compatible update within that release family, and retain distinct matching DLC. Never compare update numbers across different CUSAs/editions as though they were interchangeable.
- Prioritise verified canonical IGDB popularity when available, with missing scores placed after scored games and identified as unranked. The score represents the indexed IGDB popularity metric, not PS4 sales.
- Start with the 1fichier API and aria2 transfer design. Exclude confirmed removed files and the previously excluded Filecrypt links. A CAPTCHA, rate limit, authentication error or challenge is not evidence that a file was deleted.

The catalogue's current source-label suggestions are described in [RECOMMENDATIONS.md](RECOMMENDATIONS.md). This download plan adds stricter validation requirements before spending traffic on unattended transfers.

## Multi-server coordination

Use one shared queue and completed-file record. A worker claims a whole game allocation and receives the highest-priority eligible game that fits its available capacity. Popularity controls assignment order; completion order depends on file size and transfer speed.

Persist the assigned server and per-file progress. Resume interrupted work on that server. Reassignment must first reconcile the old worker's claim and partial files so two servers cannot download the same allocation concurrently. Respect a global API throttle and combined traffic budget, as well as per-server capacity and bandwidth limits.

Keep temporary downloads in `/mnt/storage/PS4/incomplete` and service state in `/mnt/storage/PS4/download-state`, outside the finished game folders. Before writing, verify that the intended storage filesystem is mounted and has the required free-space reserve. Check containment and symlinks for every generated path; source titles and filenames cannot escape the configured roots.

Preserve original source filenames in metadata, sanitise unsafe path characters, and detect name collisions. Validate expected size and supplied checksums where available. Compute a local hash to identify completed bytes, while recording that a locally generated hash alone does not prove correctness. Promote a file to its final folder only after transfer validation. Archive completeness and package compatibility remain separate checks.

The per-game manifest should record canonical identity, assigned server, selected release, title/content IDs, region and language evidence, type, game/update version, firmware requirement and backport variant, source page/public file URL, original and local filenames, archive parts, expected/actual size, hashes, completion and verification status. Store credentials, download tokens and signed URLs only in private runtime storage, never in the repository, public catalogue or game manifests.

## Setup still required

For each server: hostname/IP, SSH user and port, access method, usable space at the destination, and any bandwidth cap. Choose an initial combined traffic limit and free-space reserve, validate a small API transfer from each participating server, then populate the shared queue. Do not assume the previously reported CDN balance is still current.
