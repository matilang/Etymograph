# ADR 0001: Word identity

Status: Proposed

## Context

A word node must stand for one Wiktionary entry (one word in one language with one origin), and every
etymology link must land on the node of the entry it names. Four things make this hard:

- **Homographs.** German *Bank* "bench" and *Bank* "bank" are different words with different origins,
  on the same page.
- **Link targets name only a form.** A template writes `{{inh|de|gem-pro|*bankiz}}`: a language and a
  form, sometimes a sense id, never an entry number.
- **Forms in links are spelled differently from page titles.** Etymologies write Latin `tēgula`, the
  entry page is `tegula`; Proto-Slavic `*sь̑rdьce` lives at `*sьrdьce`. In the probe, *Herz / serce /
  srce* only connected once this was handled.
- **Reconstructions.** Templates write `*bankiz`; the kaikki entry for that page has `word` = `bankiz`.

**Diacritics policy (project rule).** Diacritics and letters are never removed from the stored word.
*šala* ≠ *sala*, *Bär* ≠ *Bar*, *cegła* ≠ *cegla*. A generic "strip all diacritics" function and
hand-written per-language rules are both forbidden.

## Options

1. **Node per exact (language, form) string** (what the probe did first). Simple, but *Bank* "bench"
   and *Bank* "bank" collapse, and `tēgula` never meets `tegula`.
2. **Node per (language, generic-stripped form).** Connects `tēgula`/`tegula`, but merges *šala* and
   *sala*, *Bär* and *Bar*. Rejected by the diacritics policy.
3. **Node per (language, hand-written per-language key)** (the probe's `node_key`: drop macrons and
   breves for `la*`, five accents for `sla-pro`). Works for the cases it was written for, silently
   wrong for every other language, and duplicates rules Wiktionary already maintains. Rejected.
4. **Node per (language, Wiktionary entry key, etymology number)**, where the key is computed with
   Wiktionary's own per-language rules from its module data. **Chosen.**

## Decision

### Identity

- A word's identity is the triple **(`lang`, `key`, `etym_no`)**.
  - `lang`: the full (non-etymology-only) Wiktionary language code of the entry, see ADR 0002.
  - `key`: the entry key, defined below.
  - `etym_no`: kaikki's `etymology_number` as an integer. kaikki writes it as a **string** (`"1"`,
    `"2"`) and only on pages with more than one etymology section; on all other pages the field is
    absent. Absent means `etym_no = 0`. A page therefore has either one word with `etym_no = 0` or
    words numbered 1..n, never both. `TODO(verify)`: confirm "never both" on the full de and pl
    files in phase 1.
- Several kaikki entries (one per part of speech) with the same triple are **one word**. Their parts
  of speech are collected into a list. In the de sample, 1,553 of 56,417 (word, etymology number)
  groups have more than one POS.
- `word_id` is derived from the triple only (ADR 0006 gives the hash), so it is stable across runs.

### `form` and `key`

- `form`: the word exactly as the source writes it, NFC-normalized, every mark kept. For an entry it
  is kaikki's `word` (plus the reconstruction asterisk, below); for a stub it is the target form as
  written in the template. Used for display, the database and reports.
- `key`: used **only** to resolve a link target to an entry. Computed as:
  1. Unicode NFC; trim surrounding whitespace. Case is kept (Wiktionary titles are case-sensitive).
  2. Apply the language's **`strip_diacritics`** rule from the Wiktionary module data, for the
     script of the term. If the language has no such rule, the key equals the NFC form.
  3. NFC again.
- **Where the rules live (verified in the module data, dump-era copy of 2026-10-25):** each language
  table in `Module:languages/data/2`, `Module:languages/data/3/<letter>`,
  `Module:languages/data/exceptional` and `Module:etymology_languages/data` may carry a
  `strip_diacritics` field. It is either one rule or a table per script (`Latn`, `Cyrl`, …) and each
  rule has `remove_diacritics` (a string of combining marks), optional `remove_exceptions`
  (precomposed letters that must survive) and optional `from`/`to` substitution lists. Some rules
  point into a shared table, for example Latin's `s["itc-Latn-stripdiacritics"]`, and the mark
  constants (`c.macron`, `c.acute`, …) come from `Module:languages/data`. Examples:
  - `sh` (Latn and Cyrl): removes grave, acute, tilde, macron, double grave, inverted breve, with
    exceptions ć, ś, ź (and Cyrillic з́, с́). So `srȁce` → `srce`, and `ć` stays.
  - `sla-pro`: same marks, exception `ś`. So `*sь̑rdьce` → `*sьrdьce`.
  - `zlw-opl`: removes only the ring above. `zlw-mpl`: removes acute, with exceptions ć ń ó ś ź.
  - `de`, `pl`: **no `strip_diacritics` at all**, so `key = form`: `cegła` stays `cegła`.
  - `gmh`: removes circumflex and macron, and maps `ë → e`, `ʒ → z`; `goh` removes circumflex,
    macron and diaeresis. These rules are applied exactly as written, letter mappings included
    (decision below).
- The older field name in Wiktionary was `entry_name`; the pinned copy uses `strip_diacritics`.
  `TODO(verify)`: confirm the field name and the shared tables in the module tar pinned to the kaikki
  dump (ADR 0006).
- **`sort_key` is never used.** It is a different field and does change letters (Polish `sort_key`
  maps `ł` to `l` plus a private-use character).
- The algorithm follows Wiktionary's `Module:languages` implementation: protect `remove_exceptions`,
  decompose, drop the listed combining marks, recompose, then apply `from`/`to`.
  `TODO(verify)`: read the pinned `Module:languages` code for the exact order of these steps
  (exceptions vs. `from`/`to`) before implementing, and copy its test cases.
- **Script selection.** For a per-script rule, the term's script is detected among the scripts the
  language lists (for example `sh`: Latn, Cyrl, Glag, Arab). `TODO(verify)`: compare with
  Wiktionary's `findBestScript` in `Module:scripts` on the sh test set.
- For an etymology-only code (`la-vul`, `zlw-mpl`), use its own `strip_diacritics` if it has one,
  otherwise walk its parents (ADR 0002) to the first code that has one. `TODO(verify)` against
  `Module:languages`.

### Reconstructions

- A term is a **reconstruction** if the source writes it with a leading `*`. Its `form` and `key`
  always carry exactly one leading `*`.
- kaikki entries from reconstruction pages have `word` without the `*` (probe: "Reconstruction
  entries have no `*` prefix"). The extractor adds it for entries of languages whose
  `type = "reconstructed"`. So `berô` (page) and `*berô` (template) become one node.
- Language type alone is not enough: `gmw-pro` is not marked `reconstructed` in the module data
  (the line is commented out), yet its terms are written with `*`. `TODO(verify)`: find the field in
  kaikki that tells a Reconstruction-namespace page apart (for example the page title or a
  `Reconstruction:` prefix), and use it instead of the language type.
- `is_reconstruction` is stored on the word and gives Neo4j the extra label (ADR 0004).

### Sense ids

- Wiktionary marks an etymology section with an id: `{{ety|de|id=bench}}`, `{{etymon|de|id=…}}` or
  `{{etymid|de|bench}}`. A link names it as `gmh:aberelle<id:April>` (inline modifier in `{{ety}}` /
  `{{etymon}}`) or `|id=` in classic templates. Sample of the first 60,000 lines: de has 1,085
  inline `<id:…>` and 1,328 `id=` arguments, pl 4,934 and 5,004.
- A word stores its own ids (`ety_ids`); a link stores the id it asked for (`target_sense_id`).
- Ids are used **only to choose between homographs**. They are not part of identity: most entries
  have none, and making them part of the key would split one word into several nodes.

### Resolving a link target

1. Compute (`lang`, `key`) of the target as above. `lang` is the full language of the code as
   written (ADR 0002 maps `la-vul` → `la`, `LL.` → `la-lat` → `la`).
2. Look up all words with that (`lang`, `key`) built from loaded entries.
3. Outcome, stored on the link as `resolution`:

| Candidates | Rule | `resolution` | Link goes to |
|---|---|---|---|
| 1 | — | `resolved` | that word |
| > 1 | exactly one candidate has `target_sense_id` in its `ety_ids` | `resolved_by_id` | that word |
| > 1 | no id, or the id matches none or several | `ambiguous` | page word (`lang`, `key`, `etym_no = 0`), `status = ambiguous` |
| 0 | language file loaded, no entry | `stub` | stub word (`lang`, `key`, 0), `stub_reason = no_entry` |
| 0 | language file not part of the build | `stub` | stub word (`lang`, `key`, 0), `stub_reason = no_file` |

- A page word for an ambiguous target cannot collide with a real entry, because a page with
  numbered etymologies has no entry with `etym_no = 0`.
- A stub keeps the target form as written as its `form`. If several links write different forms
  for the same stub key, the stub's `form` is the smallest of them in code-point order (so the
  build is deterministic); each link still keeps its own `target_form`.
- Rejected for ambiguous targets: linking to **all** candidates (creates false paths through the
  wrong homograph, exactly the *Bank* case) and picking `etym_no = 1` (wrong for every link that
  meant the second etymology).

## Consequences

- *Bank* "bench" and *Bank* "bank" are two nodes; `tēgula` resolves to `la:tegula`; `cegła` keeps
  both form and key `cegła`; *šala* and *sala* stay different nodes.
- Link resolution depends on which language files are loaded. Adding a language can turn stubs into
  entries; ADR 0006 re-resolves all links on each build, which is cheap.
- Ambiguous page words are real nodes. Queries that need precision filter on `status = 'entry'`.
- **Keys follow Wiktionary's `strip_diacritics` rules exactly, including letter mappings** such as
  `gmh` `ë → e` and `ʒ → z`. A key only serves to find the page, so it must be spelled the way
  Wiktionary spells the page title. `form` always keeps every letter and mark: `gmh:hërze` has key
  `herze` and form `hërze`. The project rule "letters are never changed" applies to the stored word
  (`form`); the modern MVP languages' rules do not change letters anyway (`de` and `pl` have none).

## Evidence

- Probe: Latin entry coverage of referenced words 44% → 74% once macrons were removed; *Herz / serce
  / srce* connected only after Proto-Slavic accents were removed.
- Probe: the word graph is "a forest of small trees" because "nodes are exact (language, term)
  strings".
- Sample: `{"word": "Bank", "etymology_number": "1", …}` with `{{ety|de|id=bench}}`, and a second
  entry with `"etymology_number": "2"` and `{{etymon|de|id=institution|:der<conj:and>|it:banco|it:banca}}`.
- Sample: `{{etymon|pl|:inh|zlw-opl:cegła<id:brick>|id=brick|tree=1}}` in `pl:cegła`.

## Open questions

1. **Resolved (review of phase 0):** keys follow Wiktionary's `strip_diacritics` rules exactly,
   letter mappings included (`gmh` `ë → e`), because they only serve to find the page; `form` always
   keeps every letter and mark. See Consequences.
2. `TODO(verify)`: exact algorithm order in `Module:languages`, script detection, etymology-only
   fallback, the Reconstruction-page indicator in kaikki.
3. `TODO(verify)`: share of `<id:…>` targets that match an `ety_ids` value (measured in phase 1).
