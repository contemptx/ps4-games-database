# Release suggestions

The catalogue highlights a suggested base, the latest numbered matching update, and related DLC. These are suggestions from indexed source labels, not package-level compatibility or individual download verification.

- A release family requires a single CUSA title ID, region and source page. Editions and source sections stay separate. Conflicting labels are never recommended. A missing base, ID or region requires manual review.
- Versions are compared numerically within a family. An update must be newer than a known base version. Unknown update versions cannot be ranked. DLC entries are distinct content, so older-numbered DLC is not discarded.
- The console firmware field is optional and saved locally with the preferred host. Without it, firmware is explicitly unchecked. With it, both base and update must meet their respective listed requirements. Missing or ambiguous firmware labels require review.
- A single ordinary firmware label is treated as a stated minimum. A slash-separated list or backport label is treated as stated targets; `7.xx` matches the 7.x family. Explicit `+` means a minimum for that token. Ambiguous ranges, malformed labels and wildcards with `+` are not guessed.
- A higher-firmware base is not assumed usable merely because a lower-firmware backport update is listed. Check the source's instructions for these combinations. Source labels do not establish package signing, installation requirements or DLC entitlement compatibility.
- The default family favors an available preferred host, then a matching update. Version numbers are never compared across different title IDs/editions to pick a family. The per-game selector lets the user choose another family.
- 1fichier is the default preferred host. MediaFire and Pixeldrain follow when it is unavailable, based on earlier host sample tests. This does not verify every file. All links are retained; several links on the same host may be required archive parts. No files are declared identical without evidence.
- Source and release-type filters continue to work. An Updates/DLC filter retains the matching base as recommendation context without displaying that base among the filtered results.

Implementation: `recommendations.js`, shared by all three catalogue pages. No account credentials or API calls are used in the browser.

Run the matching/firmware/filter regression checks with:

```sh
node tests/test_recommendations.cjs
```
