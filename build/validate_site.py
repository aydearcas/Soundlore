"""Validate the checked-in static viewer without third-party dependencies."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('concepts.json', 'genres.json', 'temperature_viewer.json',
          'genres_by_concept.json', 'idf.json', 'genre_map.json')
LEVELS = ('characteristic', 'frequent', 'occasional')


def validate(site=None):
    site = Path(site) if site else ROOT / 'viewer'
    html = (site / 'index.html').read_text(encoding='utf-8')
    data = {name: json.loads((site / name).read_text(encoding='utf-8')) for name in ASSETS}
    concepts = data['concepts.json']['concepts']
    facets = {f['code'] for f in data['concepts.json']['facets']}
    ids = {c['id'] for c in concepts}
    genres = data['genres.json']
    keys = {g['key'] for g in genres}
    mbids = {g['mbid'] for g in genres}
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    check(len(ids) == len(concepts), 'Duplicate concept IDs')
    check(len(keys) == len(genres) == len(mbids), 'Duplicate genre keys or MusicBrainz IDs')
    for name in ASSETS:
        check(name in html, f'Viewer does not reference {name}')
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
    if errors:
        raise ValueError('\n'.join(errors))
    print(f'Validated: {len(concepts)} concepts, {len(facets)} facets, {len(genres)} genres, {len(mapped)} map points')


if __name__ == '__main__':
    validate()
