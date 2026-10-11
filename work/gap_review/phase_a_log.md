# Gap review, phase A: structural fixes (2026-10-11)

Source: `sources/ChatGPT/soundlore-revision-lagunas.md`. Phase A changes meaning and structure without growing the thesaurus beyond what the fixes need. Identifiers are kept wherever the concept stays the same; new parts get new identifiers.

## Splits (with `python build/ids.py split`)

| Old entry | Kept | New | Profiles reassigned | Review file |
|---|---|---|---|---|
| Lap steel / resonator guitar | Lap steel guitar (SL000418) | Resonator guitar (SL000820) | none (ambient americana, sacred steel and hapa haole use the lap steel) | `work/splits/2026-10-11_lap_steel.tsv` |
| Cuatro / tres | Cuatro (SL000433) | Tres (SL000821) | son cubano → tres; punto → tres; samba → cavaquinho (the cuatro was a mistake there) | `work/splits/2026-10-11_cuatro.tsv` |

Still to review by you: **son jarocho** (its core instrument is the jarana jarocha, not in Soundlore yet) and **keroncong** (cuk and cak) keep `cuatro` for now.

## Relabeled entries that keep their identifier

- SL000202 *Pelog and slendro* → **Gamelan tuning systems** (slug `gamelan_scales` → `gamelan_tuning`), now a general term with narrower Pelog (SL000822), Slendro (SL000823). The two genre profiles that used it (gamelan, Southeast Asian classical) keep the general term.
- SL000195 *Non-Western and exotic scales* → **Modal and tuning systems** (slug `exotic_scale` → `modal_system`). It now holds only frameworks that go beyond a set of pitches: Maqam, Raga, Gamelan tuning systems. Phrygian dominant, Double harmonic, Hungarian minor and Japanese scales moved to *Scales* (Japanese scales also related to Pentatonic). No profile used the branch itself.
- SL000626 *Leslie speaker* → **Rotary speaker** (entry terms Leslie speaker, rotary), moved from TEC *Keyboard techniques* to PRD *Modulation effects*: it is an effect, not a way of playing.
- SL000618 *Sub-bass* moved from TEC *Bass techniques* to PRD *Recording aesthetic*, next to Bass-heavy mix: a frequency region, not a technique. 18 profiles use it; none needs a change (the concept is the same). Its expected prompt adherence follows the new facet (PRD, high).
- SL000503 *FM synthesis* keeps the method; the instrument is now Yamaha DX7 (SL000852) (alias DX7 and prompt term moved there). Profiles to review: **kankyō ongaku** and **fm synthesis** use `fm_synth`; both are right for the method, and kankyō ongaku could add the DX7.

## Aliases that hid distinct concepts

| Alias | Was under | Now |
|---|---|---|
| portamento | Glissando | Portamento (SL000827), related to Glissando |
| ground bass, basso ostinato | Passacaglia | Ground bass (SL000824), narrower of Ostinato, related to Passacaglia |
| hammer-on, pull-off | Legato (guitar) | Hammer-on (SL000863), Pull-off (SL000864), narrower of Legato (guitar) |
| spiccato | Staccato strings | Spiccato (SL000865), narrower of Staccato strings |
| tape saturation | Analog warmth | Tape saturation (SL000866), under Distortion, related to Analog warmth (prompt term moved too) |
| appoggiatura | Grace note | Appoggiatura (SL000826), under Ornamentation, related to Grace note |
| acciaccatura | Grace note | Acciaccatura (SL000825), narrower of Grace note |
| bodhrán, pandeiro, daf | Frame drum | Bodhrán (SL000853), Pandeiro (SL000854), Daf (SL000856), narrower of Frame drum, with Riq (SL000857), Bendir (SL000858), Tamborim (SL000855) |
| siku (zampoña) | Pan flute | Siku, narrower of Pan flute (added with the MusicBrainz instruments) |
| sousaphone | Tuba | Sousaphone, narrower of Tuba (MusicBrainz) |
| maracas | Shaker | Maracas, narrower of Shaker (MusicBrainz) |
| güira | Güiro | Güira, a different instrument, related to Güiro (MusicBrainz) |
| dobro | Lap steel | Resonator guitar (split above) |
| Cuban tres | Cuatro | Tres (split above) |

Profiles to review for the frame drums (they keep `frame_drum`, which is still correct): samba (pandeiro, tamborim), celtic and irish folk (bodhrán), forró, plena, muiñeira, tammurriata, tarantella and others listed by `grep -w frame_drum genres/*.txt`.

## Overlapping definitions

- Melisma (device), Melismatic singing (style) and Vocal runs (fast ornamental passages) stay separate; scope notes now say which is which, and Vocal runs has Melisma as a second broader term.
- Glissando and Portamento: glissando is a sweep through the pitches between two notes (continuous or as a rapid scale); portamento is an expressive glide that connects one note to the next.

## Instruments of the gap review (area 4.13), checked against MusicBrainz

Added (29), all with MusicBrainz MBIDs except Pandeiro, which MusicBrainz lacks: bass clarinet, viola da gamba, Hardanger fiddle, sarangi, sarod, santur, santoor, pipa, yangqin, bansuri, dizi, suona, sheng, gayageum, đàn bầu, đàn tranh, tanpura, udu, shekere, agogô, pandeiro, bodhrán, berimbau (under Musical bow), cimbalom, hammered dulcimer (broader of santur, santoor, yangqin and cimbalom, following MusicBrainz), Appalachian dulcimer, jaw harp, musical bow, ocarina.
Structure from MusicBrainz: Steel guitar (new) is broader of Pedal steel, Lap steel and Resonator guitar; Gayageum and Đàn tranh are related to Guzheng (MusicBrainz files them as subtypes; Soundlore keeps them as siblings).
Deferred (6): English horn, contrabassoon, alto flute, bass flute, viola d'amore, ruan. Orchestral or ensemble variants that rarely tell genres apart.

## Not done in phase A

- Meter / Time signature: the alias stays until phase B decides where Time signature goes (row in the batch 1 table).
- 570 → 614 concepts without a `related` link: relations are added with each batch, not in bulk.
- Timbre and interactive or audiovisual music wait for your decisions.
