# PS4 release dates and popularity

The `Refresh IGDB metadata` workflow imports public metadata daily and on demand.
Add repository Actions secrets named `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET`,
then run the workflow. Credentials go only to Twitch's token service and the
resulting token goes only to IGDB. They never appear in generated files or URLs.

The importer bulk-loads IGDB PS4 games and their alternative names, then matches
unique normalized titles. It removes packaging suffixes but retains editions,
sequel numbers and subtitles. Ambiguous and missing matches are recorded in
`igdb-review.json`; no fuzzy matches are silently accepted. PS1/PS2 titles in the
original catalogue will remain unmatched unless IGDB also records a PS4 version.

Release dates are the earliest known, non-future PS4 date across regions, not the
game's first release on another platform or the source article's publication date.
Partial year/month dates retain their precision and sort at the start of their
period. Popularity uses IGDB visits (popularity type 1), across platforms; it is
not a count of downloads, sales or PS4 players. Missing popularity is unknown,
not zero. The site links matched entries to IGDB and states metadata coverage.

All sorting applies before pagination; unknown values sort last. Source and text
filters work with every sort order. Missing data disables unavailable sort modes.
API errors fail the workflow without committing partial data or replacing the
last published metadata. Source indexing and link availability are separate.

References: https://api-docs.igdb.com/#authentication,
https://api-docs.igdb.com/#release-date,
https://api-docs.igdb.com/#how-to-use-popularity-api
