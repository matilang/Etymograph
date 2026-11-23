# Golden set

Hand-checked German–Polish word pairs with their expected etymology paths, in
[`pairs.yaml`](pairs.yaml). Every entry was looked up by hand on **English Wiktionary**
(the source kaikki extracts), in the page's wikitext, not copied from pipeline output.

It is used to:

- test Role 3's queries, above all the common-ancestor query;
- check pipeline output path by path once real data exists (phase 2);
- calibrate link `confidence` (ADR 0003), using the checked `chain` steps.

## Entry kinds

| `kind` | Tests |
|---|---|
| `pair` | where two words meet, and how each side gets there |
| `homograph` | that homographs (`de:Bank#1` "bench", `de:Bank#2` "bank") are separate nodes, each with its own path |
| `cycle` | that a cycle in the data is kept (ADR 0003) and reported by the cycle warning shape |

A `homograph` entry lists `words`, each with its own `path`; a `cycle` entry lists `words` and
the `links` that form the cycle. Both use `expected_v1` as a sentence instead of
`connected` / `not_connected`.

## Fields of a `pair`

| Field | Meaning |
|---|---|
| `id` | lowercase ASCII, `<german>-<polish>` (for example `kuche-kuchnia`) |
| `relation` | **truth** per en.wiktionary: `related` or `unrelated` |
| `expected_v1` | what the **v1 graph** should return: `connected` or `not_connected` |
| `a`, `b` | the two words |
| `common_ancestor` | nearest word both reach; `null` if unrelated or disputed |
| `path_a`, `path_b` | steps from each word to `common_ancestor`, as `[source, type, target]` |
| `beyond` | optional: how the path continues past the meeting point (used to test long chains) |
| `checked` | where and when it was verified; `(wikitext)` means the Edit view was read |
| `notes` | why the entry is interesting, and why it does or does not connect |

## `relation` and `expected_v1`

The two fields answer different questions: is the pair really related, and can v1 see it?

| `relation` | `expected_v1` | Meaning | If a test fails |
|---|---|---|---|
| `related` | `connected` | normal case | **missing path**: a template not parsed, a resolution failure (recall) |
| `related` | `not_connected` | **known v1 limit** (see below) | it now connects: check it, then update `expected_v1` |
| `unrelated` | `not_connected` | **true negative** | it connects: **false path**, usually a wrong chain step (precision) |
| `unrelated` | `connected` | never valid | — |

## Conventions

- **Words** are `lang:form`, with the Wiktionary language code. Homographs add the
  etymology number: `de:Bank#2`. Codes: [`samples/de-pl-mini/languages.csv`](../../samples/de-pl-mini/languages.csv),
  or Wiktionary's "List of languages" / "List of families" / "List of languages, special".
- **Forms are written exactly as Wiktionary writes them**, with every diacritic and the
  `*` of reconstructions (`sla-pro:*okъnò`). Tests must compare words by
  **(`lang`, `key`)**, not by form: the key applies Wiktionary's `strip_diacritics` rule
  (ADR 0001), so `*okъnò` and `*okъno` are the same word.
- **Words are filed under their full language** (ADR 0002). A template with an
  etymology-only code such as `la-vul` or `la-lat` gives a `la:` word; the original
  code is kept in a comment.
- **Direction** is derived word → etymon, as in the graph (`[pl:kreda, bor, de:Kreide]`).
- **Types** are the four link types: `inh`, `bor`, `der`, `calque`. Template variants map
  onto them (`ubor`, `lbor` → `bor`; `uder` → `der`; `semantic loan` → `calque`); a comment
  may record the raw template. In plain words: `inh` is the same word passed down,
  `bor` taken over sound and all, `der` "comes from it somehow" (route not given),
  `calque` copied by translating the parts (`światopogląd` ← `Weltanschauung`) or by taking
  over a meaning (a semantic loan, as in `devise-cycle`).
- **A word is its own ancestor at zero steps.** For a direct loan the lender is the meeting
  point and its path is empty (`kreide-kreda`: `path_a: []`), as in the query
  `-[:DERIVED_FROM*0..]->`.
- **Meaning does not matter.** The graph links word histories: `kirche-kosciol` (same
  meaning) is unrelated, `konig-ksiadz` (king / priest) is related.

## Known v1 limits

`related` + `not_connected` entries, by cause:

| Cause | Entries | Would connect when |
|---|---|---|
| affix or compound step (`RESERVED_MORPH`, ADR 0007) | `herz-serce`, `konig-ksiadz` (also `fenster-okno` on the Polish side) | `COMPOSED_OF` is loaded |
| ancestor file not loaded: Gothic | `kessel-kociol` | Gothic (`got`) is added |
| ancestor file not loaded: Old Czech | (the path of `pl:kościół` in `kirche-kosciol`) | Old Czech (`zlw-ocs`) is added |
| no link in the source | `bank-bank` | — (Wiktionary names no shared step) |

`herz-serce` also shows a word-identity issue: the two sides name different PIE forms
(`*ḱérd` vs `*ḱḗr` / `*ḱerd-`), which are different nodes.

## Adding an entry

1. Open the word on en.wiktionary.org, click **Edit**, read the Etymology section.
2. Only these become links: `inh`, `bor`, `der`, `calque` and their variants, and the
   keywords in `{{ety}}` / `{{etymon}}` (`:inh`, `:bor`, …). **Not links:** `cog`, `m`,
   `m+`, `l`, `dercat`, `desc` (Descendants lists), references (`<ref>`), "compare …".
3. A template with `-` as the word (`{{inh|de|gmh|-}}`) names only a language: no node, and
   the path continues at the next step.
4. Prose chains ("From X, from Y, from Z") become a chain X → Y → Z.
5. Polish `{{ety|…|tree=1}}` names only the first step; follow it on the ancestors' own
   pages (Old Polish, Proto-Slavic, …).
6. A step that merges two parts (`*sьrdь + *-ьce`, a suffix, a compound) ends the v1 path.
   A step into a language that is not loaded (see `import_runs.ancestor_files`) also ends
   it, at a stub.
7. A page can hold a morphology analysis **and** a link in one template:
   `{{ety|pl|:af|świat|-o-|pogląd|:calque|de:Weltanschauung}}`. The `:af` part is dropped,
   the `:calque` part is still a link. Calques are often recorded only as compounds; then
   there is no link at all.
8. Fill in all fields, set `checked` to `en.wiktionary.org (wikitext), <date>`, and
   explain the case in `notes`.
