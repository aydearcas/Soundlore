# Prompt for ChatGPT: year of emergence of each genre

Paste the prompt below once, then attach one batch file per message (`genres_batch_01.tsv` … `genres_batch_15.tsv`, 150 genres each) and ask: "Next batch". Save each answer as `genres_batch_NN_chatgpt.tsv` in this folder.

---

I am building Soundlore, a public thesaurus of musical genres (all 2,186 MusicBrainz genres). I need, for each genre, **the year it emerged**, to draw a timeline where genres appear on a map as a slider moves forward in time.

I will send the genres in batches of 150, as a TSV file with these columns: `key` (genre name), `musicbrainz_id`, `wikidata` (Wikidata item, may be empty), `family`, `parent_genres`, `area`.

For every row, give **one row back**, in the same order, as a TSV code block with exactly these columns:

`key	year	precision	basis	source_url	confidence	note`

- `key`: copied exactly as given.
- `year`: the year the genre emerged as a recognizable style: the first recordings, scene or works usually cited for it, or when the name came into use if that is how sources date it. Not the earliest distant precursor. For old traditions, the period when the tradition took its recognizable form (use a negative number for BCE). One integer.
- `precision`: `year` (sources give a year), `decade` (sources say "the 1990s": give the first year of the decade, 1990), `century` (give the first year of the century, e.g. 1801 → write 1800), or `era` (only a rough period is known; give your best middle estimate).
- `basis`: `wikipedia` (stated in the English or Spanish Wikipedia article of the genre), `wikidata` (inception, P571, of the Wikidata item), `other` (another reliable source you can name), or `estimate` (no source states it; inferred from the parent genre, the scene or the instruments).
- `source_url`: the page that states it (Wikipedia article URL, Wikidata item URL or other). Empty for `estimate`. Only give a URL you have actually checked; never build one from the name.
- `confidence`: `high` (a source states it clearly), `medium` (sources disagree within about a decade, or only a decade is known), `low` (estimate).
- `note`: at most 15 words: the event or recordings the year refers to, or why it is an estimate. For example: "Bad Brains and Minor Threat, Washington DC", "named by NME in 1991", "estimate: subgenre of trap, which emerged around 2003".

Rules:
- Do not skip rows and do not add rows. If you know nothing about a genre, still give an estimate with `basis` = `estimate` and `confidence` = `low`.
- A subgenre cannot be older than its parent unless sources say so; if they do, explain it in `note`.
- Do not invent dates or sources. A clearly marked estimate is better than a false precise year.
- Use English for `note`.
- Reply only with the TSV code block for the batch, then one line saying how many rows are `high`, `medium` and `low`.
