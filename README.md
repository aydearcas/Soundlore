# Music Thesaurus — v0.5

Biblioteca de recursos musicales y géneros, preparada para publicarse como web
estática en **GitHub Pages**.

**Publicación manual:** sigue la [guía en español de GitHub Pages](docs/GITHUB_PAGES.md).
Sube el contenido de esta carpeta, incluida `.github/`, a la raíz del repositorio;
en **Settings → Pages → Source**, selecciona **GitHub Actions**.

**Vista previa local** (Python 3.10 o posterior):

```sh
python build/package.py
python -m http.server 8000 --directory dist
```

Abre [localhost:8000](http://localhost:8000/). El empaquetado valida los seis JSON
del visor y crea `dist/`; no requiere paquetes adicionales. Las dependencias de
`requirements.txt` solo son necesarias para reconstruir todos los datos y el mapa
con `python build/package.py --rebuild`.

El flujo de Pages publica el visor y sus datos en la raíz de la URL del sitio.
Los archivos fuente y los scripts se conservan en el repositorio.

---

A library of musical resources organized as a thesaurus (SKOS model, MeSH style), with two connected vocabularies:

1. **Concepts** (musical resources), in 14 facets.
2. **Genres**: all 2,212 MusicBrainz genres, with their relations.

The bridge between them is each genre's **profile**: which resources are characteristic (C), frequent (F) or occasional (O) in it. The **temperature** between genres is computed from that bridge.

## Folder layout

| Path | Contents |
|---|---|
| `concepts/*.txt` | Editable concept sources (one line per concept; indentation sets the hierarchy) |
| `concepts/translations_es.tsv` | Spanish labels and synonyms, kept as an optional translation layer (not used by the build) |
| `genres/core.txt` | Genres in the core set (profiled in more detail) |
| `genres/profiles_*.txt` | Genre → resource profiles (editable source) |
| `sources/musicbrainz_genres.json` | Original MusicBrainz download (genre list + each genre's relations) |
| `build/*.py` | Scripts that validate the sources and generate the JSON |
| `build/concepts.json` | Generated concept thesaurus |
| `build/genres.json` | Generated genre thesaurus |
| `build/temperature.json` | The 25 closest genres for every genre |
| `build/genres_by_concept.json` | Inverted index: which genres use each resource |
| `build/genre_map.json` | 2D coordinates and family of every profiled genre, for the map view |
| `viewer/index.html` | Viewer for browsing the thesaurus (collapsible concept tree, hierarchical paths, genre profiles, prompt drafts, temperature, genre map) |

To rebuild and synchronize the viewer: `python -m pip install -r requirements.txt`,
then `python build/package.py --rebuild` (the map needs `numpy` and `scikit-learn`).
To validate and package the existing viewer only: `python build/package.py`.
`build/package.sh` is a portable Linux/macOS shortcut for the same command.

## Concepts

### Line format

`id | term | synonyms | scope note | prompt terms | relations`

- Prompt terms in brackets (`[Breakdown]`) are structure tags to place in the lyrics; the rest are style terms for a text prompt.
- In relations, `^id` adds an extra broader term (polyhierarchy) and a plain `id` creates a "related" link.

### Tree numbers

Every concept gets a MeSH-style tree number (`DRM.01.13`). Concepts with polyhierarchy get several.

### Facets

| Code | Facet |
|---|---|
| RHY | Rhythm, meter and tempo |
| DRM | Drums and percussion patterns |
| HAR | Harmony and tonality |
| SCL | Scales and modes |
| MEL | Melody and motif |
| FRM | Form and structure |
| TEX | Texture and counterpoint |
| VOC | Voice and vocal technique |
| INS | Instrumentation |
| TEC | Instrumental techniques |
| PRD | Production and sound |
| DYN | Dynamics and articulation |
| LYR | Lyrics and prosody |
| MOO | Mood and character |

### Prompt adherence

- `prompt_adherence_expected` (high/medium/low) is an **untested estimate**, per facet with a few exceptions, of how reliably AI music generators follow each term. Timbre and production terms usually work; meter, counterpoint and modulation are usually ignored.
- `prompt_adherence_tested` is left empty for your own test results.

### Provenance

The concept taxonomy is original work. The form facet closely follows the musical form terms of LCGFT (Library of Congress), and the instrument facet those of LCMPT.

The automatic crosswalk to Library of Congress identifiers **has not been done**: id.loc.gov showed a bot-verification check that should not be bypassed. It remains pending, as a manual mapping or from an environment with access.

## Genres

- **Source:** MusicBrainz (CC0 data), downloaded on 2026-10-10 through its public API (list) and each genre's page (relations).
- **Relations kept:**
  - subgenre of / subgenres (equivalent to BT/NT)
  - fusion of / fusion genres
  - influenced by / influenced
  - Wikidata, area of origin, and links to other databases (RateYourMusic, Discogs, AllMusic)
- **Profiles:** all 2,186 musical MusicBrainz genres have a profile.
  - **Core (713, high confidence):** profiled in more detail. Priority on rock, metal and electronic music.
  - **Rest (1,473):** lighter profiles, usually inherited from the parent genre plus their own traits (`profiles_10` to `profiles_13`). Medium confidence with at least 6 resources (1,066), low with fewer (407). Low-confidence profiles are mostly little-documented regional traditions.
  - **Non-musical (26):** audio drama, ASMR, stand-up comedy, nature sounds… Marked `= NONMUSICAL`, with no profile.

### Profile syntax

`genre = C … | F … | O …`

- `@other genre` inherits another genre's profile.
- `genre += …` adds resources to an existing profile.
- `genre = NONMUSICAL` marks an entry that is not music.
- If a profile has characteristic (C) resources of its own, inherited ones drop one level (C→F, F→O), so subgenres don't carry the parent's generic traits as characteristic.

The profiles are based on general musical knowledge. They should be reviewed, especially for the genres you know best.

## Temperature

Temperature from 0 to 100 between two genres:

- **Profile affinity (70%):** cosine similarity between profiles. Each resource is weighted by its level (C = 3, F = 2, O = 1) and its rarity (IDF), so sharing a rare resource like a *blast beat* counts far more than sharing a common one like 4/4.
- **Proximity in the MusicBrainz tree (30%):**
  - Each subgenre or fusion step counts 1; each influence step, 1.5.
  - 1 step = 0.75; 2 steps = 0.5; 3 = 0.25; 4 or more = 0.
- **Genres without a profile** (only the non-musical ones): tree proximity only, with a 15% discount. Marked `graph only`.

### Scale

| Value | Level |
|---|---|
| ≥ 80 | Scorching |
| 60–79 | Hot |
| 40–59 | Warm |
| 20–39 | Cool |
| < 20 | Cold |

Each neighbor lists the shared resources that weigh most, so the temperature can be explained.

`build/verify.py` checks 24 control pairs: 16 that should be close (e.g. synthwave ↔ outrun) and 8 that should be far apart (e.g. black metal ↔ bossa nova).

## Genre map

`build/build_map.py` places every profiled genre on a 2D map with t-SNE (cosine distance between the IDF-weighted profile vectors), so genres sit close together when their resource profiles are similar. Distances on the map are only approximate: the exact closeness between two genres is the temperature.

Each genre is assigned to one of 8 families (plus "Classical, traditional & other") by walking up the MusicBrainz tree to an anchor genre; genres without an anchor take the majority family of their hottest neighbors. Families are for coloring only.

In the viewer: zoom with the wheel or the + / − buttons, drag to move, click a genre to see its 10 hottest neighbors (lines colored by temperature), click a family in the legend to isolate it, and type in the search box to find a genre.

## Next steps

- Review concepts and profiles (expert validation).
- Test the prompt terms and fill in `prompt_adherence_tested`.
- Strengthen the 407 low-confidence profiles.
- Crosswalks to LCGFT/LCMPT and Wikidata.

## Future work

Viewer:
- **Neighborhood graph**: the selected genre in the center with its neighbors placed by temperature, to navigate from one genre to the next.
- **Genre comparator**: two profiles side by side, with shared and exclusive resources.
- **Concept × genre family matrix**: heat map showing which families each resource concentrates in.
- **Prompt builder**: start from a genre, add or remove resources, and get the style text and structure tags ready to copy, with a warning for low-adherence terms.
- **Genre fusion**: pick two genres and get a combined set of resources for a blend.
- **Facet pages**: a short descriptive article for each of the 14 facets; facet names in the menu become clickable and open that page.
- **Mobile layout**: adapt the viewer and the visualizations above to phone screens.
- **Review mode**: mark profiles and concepts as reviewed / doubtful / wrong, add notes and test results, stored persistently and fed back into the source files.

Data:
- **Audio samples per concept**: short generated examples for each resource. Needs dedicated hosting for the audio files.
- **Corpus layer**: MusicBrainz artists and recordings linked to genres and instruments, for listening examples, empirical validation of temperature through tag co-occurrence, and an instrument crosswalk.
- **Song examples** with timestamps.
