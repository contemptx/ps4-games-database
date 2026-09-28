#!/usr/bin/env python3
"""Version data script URLs so each published batch bypasses stale browser caches."""
import hashlib
import pathlib
import re
ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ['release-metadata.js', 'superpsx-catalog.js', 'additional-catalog.js', 'link-status.js', 'index-progress.js', 'igdb-metadata.js']
PAGES = ['index.html', 'ps4-games-optimized.html', 'ps4-pwa-optimized.html', 'processing.html']

def stamp(root=ROOT):
    revisions = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()[:16] for name in DATA}
    for name in PAGES:
        page = root / name
        text = page.read_text()
        for filename, revision in revisions.items():
            text = re.sub(r'src="' + re.escape(filename) + r'(?:\?[^"\s]*)?"', 'src="' + filename + '?v=' + revision + '"', text)
        page.write_text(text)

if __name__ == '__main__': stamp()
