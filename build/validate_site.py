"""Validate the static site in viewer/ (or a packaged copy) without third-party dependencies.

Checks that every page and data file is there and parses, that every file a page fetches exists,
and that the data files agree with each other (concepts, genres, profiles, temperature, map,
instrument layer, artists). Run: python build/validate_site.py
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('index.html', 'explore.html', 'layers.html', 'thesaurus.html', 'about.html')
ASSETS = ('concepts.json', 'genres.json', 'temperature_viewer.json', 'genres_by_concept.json', 'idf.json',
          'genre_map.json', 'instrument_layer.json', 'stats.json', 'artists.json', 'artist_neighbors.json',
          'artists_stats.json', 'soundlore.jsonld', 'soundlore.ttl')
LEVELS = ('characteristic', 'frequent', 'occasional')


def validate(site=None):
    site = Path(site) if site else ROOT / 'viewer'
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    for name in PAGES + ASSETS:
        check((site / name).is_file(), f'Missing file: {name}')
    if errors:
        raise ValueError('\n'.join(errors))
    # every file a page references (fetch, links to data files) must exist
    for page in PAGES:
        html = (site / page).read_text(encoding='utf-8')
        for ref in set(re.findall(r"['\"]([\w-]+\.(?:json|ttl|jsonld|html))(?:[#?'\"])", html)):
            check((site / ref).is_file(), f'{page} references a missing file: {ref}')
    data = {n: json.loads((site / n).read_text(encoding='utf-8')) for n in ASSETS if n.endswith('.json') or n.endswith('.jsonld')}
    concepts = data['concepts.json']['concepts']
    facets = {f['code'] for f in data['concepts.json']['facets']}
    ids = {c['id'] for c in concepts}
    genres = data['genres.json']
    keys = {g['key'] for g in genres}
    mbids = {g['mbid'] for g in genres}
    check(len(ids) == len(concepts), 'Duplicate concept IDs')
    check(len(keys) == len(genres) == len(mbids), 'Duplicate genre keys or MusicBrainz IDs')
    for c in concepts:
        check(c['facet'] in facets, f"Unknown facet for {c['id']}")
        for relation in ('broader', 'narrower', 'related'):
            check(set(c[relation]) <= ids, f"Unknown concept relation in {c['id']}")
    expected_index = {}
    for g in genres:
        for relation in ('broader', 'narrower', 'fusion_of', 'fusion_genres', 'influenced_by', 'influenced'):
            check(set(g[relation]) <= mbids, f"Unknown genre relation in {g['key']}")
        if not g['profile']:
            continue
        for level in LEVELS:
            for cid in g['profile'][level]:
                check(cid in ids, f'Unknown profile concept: {cid}')
                check(cid in data['idf.json'], f'Missing IDF weight: {cid}')
                row = expected_index.setdefault(cid, {lv: [] for lv in LEVELS})
                row[level].append(g['key'])
    for row in expected_index.values():
        for level in LEVELS:
            row[level].sort()
    check(expected_index == data['genres_by_concept.json'], 'Concept-to-genre index differs from genre profiles')
    for key, neighbors in data['temperature_viewer.json'].items():
        check(key in keys, f'Unknown temperature genre: {key}')
        for name, score, graph_only, distance, shared in neighbors:
            check(name in keys and set(shared) <= ids, f'Invalid neighbor for {key}')
            check(math.isfinite(score) and 0 <= score <= 100, f'Invalid temperature for {key}')
    genre_map = data['genre_map.json']
    mapped = set()
    for key, x, y, family, core in genre_map['points']:
        mapped.add(key)
        check(key in keys, f'Unknown map genre: {key}')
        check(0 <= x <= 1 and 0 <= y <= 1, f'Invalid map coordinates: {key}')
        check(0 <= family < len(genre_map['families']), f'Invalid map family: {key}')
    check(len(mapped) == len(genre_map['points']), 'Duplicate map genres')
    check(mapped == {g['key'] for g in genres if g['profile']}, 'Map does not match profiled genres')
    # instrument layer
    lay = data['instrument_layer.json']
    uids = {c['uid'] for c in concepts}
    check(lay['genres'] == [p[0] for p in genre_map['points']], 'Instrument layer genres differ from the map')
    for it in lay['items']:
        check(it[0] in uids, f'Unknown instrument concept: {it[0]}')
        check(all(0 <= g < len(lay['genres']) for g, w in it[8]), f'Invalid instrument link: {it[0]}')
    # artists
    art = data['artists.json']
    rows = art['artists']
    check(set(art['genres']) <= keys, 'Artists refer to unknown genres')
    check(len({r[0] for r in rows}) == len(rows), 'Duplicate artist MBIDs')
    for r in rows:
        if not all(0 <= g < len(art['genres']) for g, v in r[10]):
            errors.append(f'Invalid genre index in artist {r[0]}'); break
    nb = data['artist_neighbors.json']['neighbors']
    check(len(nb) == len(rows), 'artist_neighbors.json is not parallel to artists.json')
    check(all(0 <= j < len(rows) for row in nb for j in row[0::2]), 'Invalid similar-artist index')
    check(data['artists_stats.json']['artists'] == len(rows), 'artists_stats.json count differs from artists.json')
    size = (site / 'artists.json').stat().st_size
    check(size < 95_000_000, 'artists.json is too large for GitHub (100 MB per file)')
    if errors:
        raise ValueError('\n'.join(errors[:50]))
    print(f'Validated: {len(PAGES)} pages, {len(concepts)} concepts, {len(facets)} facets, {len(genres)} genres, '
          f'{len(mapped)} map points, {len(lay["items"])} instruments, {len(rows):,} artists')


if __name__ == '__main__':
    validate()
