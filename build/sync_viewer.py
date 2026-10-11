"""Copy the generated data files the Soundlore site reads from build/ to viewer/.

Run after the build scripts. The site's pages are all in viewer/: index.html (landing),
explore.html (concepts, genres, artists and map), layers.html, thesaurus.html and about.html.
"""
import os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["concepts.json", "stats.json", "soundlore.ttl", "soundlore.jsonld", "genres.json",
         "temperature_viewer.json", "genres_by_concept.json", "idf.json", "genre_map.json", "instrument_layer.json",
         "artists.json", "artist_neighbors.json", "artists_stats.json"]

# the site folder: viewer/ in the working copy, docs/ in the GitHub repository (served by GitHub Pages)
SITE = "docs" if os.path.isdir(os.path.join(ROOT, "docs")) else "viewer"

if __name__ == "__main__":
    for f in FILES:
        src = os.path.join(ROOT, "build", f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ROOT, SITE, f))
            print("copied", f)
        else:
            print("missing (run the build first):", f)
