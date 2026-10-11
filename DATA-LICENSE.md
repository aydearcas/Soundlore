# Licenses of the code and the data

Soundlore has different licenses for its code and its data, following its main source, MusicBrainz.

| Part | License |
|---|---|
| Code: build scripts (`build/`, `work/**/*.py`) and the site's HTML and JavaScript (`viewer/*.html`) | [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html) (AGPL-3.0) |
| Soundlore's own data: concepts, identifiers, definitions, scope notes, facet descriptions, Wikidata links, genre profiles, temperature, map, instrument layer, SKOS export | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| Data taken from MusicBrainz core and from Wikidata: genres and their relations, instruments, artist names, types, areas, dates, Wikidata items, sitelinks and genres | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), as published by MusicBrainz and Wikidata |
| Artist–genre links from MusicBrainz genre votes and everything derived from them: `sources/musicbrainz/artist_genres_extract.jsonl.gz`, `viewer/artists.json`, `viewer/artist_neighbors.json` | [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/), as published by [MusicBrainz](https://musicbrainz.org/doc/About/Data_License): attribution, non-commercial, share-alike |

Wikipedia articles are only linked, never copied. The fonts (Bricolage Grotesque, Instrument Sans, IBM Plex Mono) are loaded from Google Fonts under the SIL Open Font License; three.js is loaded from cdnjs under the MIT license.

Credits: General Orchestrator aydearcas; built with the help of the AI assistants Claude (Anthropic) and ChatGPT (OpenAI). See `viewer/about.html#provenance`. The code license text is in `LICENSE`.
