# Prompt for completing the low-confidence genre profiles (v0.8)

Attach three files to the ChatGPT conversation: `soundlore_concepts.tsv`, `musicbrainz_instruments_candidates.tsv`, and one `low_genres_batch_NN.tsv` (one batch per conversation, or per message if the conversation stays focused). Save each answer as `low_genres_batch_NN_chatgpt.tsv`.

---

You are helping complete genre profiles for Soundlore, a thesaurus of musical resources. Each genre profile lists the resources that are **C** (characteristic: defines the genre), **F** (frequent) or **O** (occasional) in it.

Files:
- `soundlore_concepts.tsv`: the closed vocabulary (concept_id, label, facet, entry terms, scope note). Use only these concept_id values, written exactly.
- `musicbrainz_instruments_candidates.tsv`: instruments from MusicBrainz that are not yet in Soundlore (code MB0001…, name, type, broader instrument, other names, description).
- `low_genres_batch_NN.tsv`: 50 genres whose current profile is thin (genre, parent genres, area, current C / F / O resources).

Task: for each genre in the batch, propose the resources missing from its profile, so that a well-described genre ends up with roughly 6 to 15 resources across C, F and O. Cover several facets (rhythm, instruments, voice, form, harmony or scales, production, mood) when they apply.

Rules:
1. Add, do not repeat: never list a concept that is already in the genre's current profile.
2. If a current entry looks wrong for the genre, add a row with level `X` for that concept_id and explain why.
3. Instruments: prefer the most specific concept in `soundlore_concepts.tsv` (e.g. `bodhran` rather than `frame_drum`). If the genre's defining instrument is not in the vocabulary but is in `musicbrainz_instruments_candidates.tsv`, use its MB code (e.g. `MB0123`) as concept_id. Use MB codes only for instruments that are C or F in the genre, never for occasional ones. Never invent codes or concept_ids.
4. If the genre is already well described or you do not know it well enough, write a single row with concept_id `NO_CHANGE` and say why.
5. Do not describe a genre by traits of single famous recordings; describe what is typical of the genre.
6. confidence: `high` (well documented and typical), `medium`, `low` (uncertain; flag rather than guess).

Output: only a TSV table, no other text, with this header and one row per proposal:

```
genre	concept_id	level	confidence	rationale
```

- genre: exactly as in the batch file.
- level: C, F, O or X.
- rationale: one short sentence in English.
