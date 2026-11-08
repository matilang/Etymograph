# ADR 0003: Link model

Status: Proposed

## Context

Etymology links come from two template syntaxes that appear side by side in the same dump:

- **Classic:** `{{inh|de|gmh|hërze}}`, `{{bor|pl|fr|bijouterie}}`, `{{der|de|ine-pro|*ḱḗr}}`. An
  etymology like "From X, from Y, from Z" is a sequence of such templates.
- **New:** `{{ety|pl|:inh|zlw-opl:serce|tree=+}}` and `{{etymon|de|:der<conj:and>|it:banco|it:banca}}`,
  with keywords (`:inh`, `:bor`, `:der`, …), `code:term` items, inline modifiers (`<id:…>`, `<t:…>`)
  and nested items.

Both syntaxes often describe the same link in one entry: `de:Herz` has
`{{ety|de|:inh|gmh:hërze|tree=1}}` **and** `{{inh|de|gmh|hërze}}`. In a 60,000-line sample of each
file, `ety` is the most frequent etymology template in both de (18,792) and pl (38,497); pl has only
991 classic `inh`.

## Options

- **Types:** keep every template name as its own type (`lbor`, `ubor`, `slbor`, …) vs. map to four
  types and keep the raw name. Four types keep queries and C3 rules simple; the raw name keeps the
  detail. **Map + keep raw.**
- **Direction:** etymon → derived word (the probe's RDF used `ety:from` = older word) vs. derived word
  → etymon. **Derived → etymon**: it reads as "X comes from Y", matches the template (written on
  the derived word's page), and ancestry queries go "forward" (`-[:DERIVED_FROM*]->`).
- **Duplicates:** keep one link per evidence record vs. merge per (source, target, type). **Merge**,
  with an evidence count.
- **Parallel links** (same pair, different types, for example `inh` + `der`): collapse to the
  strongest type vs. keep both. **Keep both, flagged**, because the disagreement is information
  Role 2's rules need.

## Decision

### Types

| Type | Classic templates | `{{ety}}`/`{{etymon}}` keywords |
|---|---|---|
| `inh` | `inh`, `inh+`, `inh-lite` | `:inh` |
| `bor` | `bor`, `bor+`, `lbor`, `slbor`, `obor`, `ubor`, `psm` | `:bor`, `:lbor`, `:slbor`, `:obor`, `:ubor` |
| `der` | `der`, `der+`, `uder`, `der-lite` | `:der`, `:uder` |
| `calque` | `cal`, `calque`, `clq`, `sl`, `semantic loan` | `:calque`, `:clq`, `:sl` |

- The table is the probe's mapping. `TODO(verify)`: the complete keyword list of `{{ety}}` /
  `{{etymon}}` from the pinned `Module:etymon` (or its data module).
- **Decided (2026-11-08):** `psm` (phono-semantic matching) → `bor` and `sl` (semantic loan) →
  `calque`. They are rare and behave like a loan and a calque in every query we plan; the raw
  template name is kept on the link (`template`), so they can still be told apart.
- **Not links:** `cog`, `ncog`, `noncog`, `doublet`, `m`, `l`, `root`, `dercat`, `etydate`, `glossary`
  and similar. They are counted in the extraction statistics but produce no link.
- **Compounds and affixes** (`af`, `affix`, `compound`, `prefix`, `suffix`, `confix`, `blend` and the
  `:af`, `:com`, … keywords) are reserved for `COMPOSED_OF` (ADR 0007) and **not loaded in the MVP**.

### Direction

`(derived word)-[:DERIVED_FROM]->(etymon)`. In the tables: `src_word_id` = derived word,
`dst_word_id` = etymon. This reverses the probe's RDF convention; the RDF export (ADR 0005) follows
this ADR.

### Attributes

| Attribute | Meaning |
|---|---|
| `type` | `inh` / `bor` / `der` / `calque` |
| `source_entry` | `word_id` of the entry whose etymology section produced the link |
| `template` | raw template name as found (`inh+`, `lbor`, `ety`, `etymon`) |
| `keyword` | the `{{ety}}` keyword as written (`:lbor`), null for classic templates |
| `syntax` | `classic` or `ety` |
| `target_lang_raw` | the language code exactly as written (`LL.`, `la-vul`, `gmh`) |
| `target_form` | the target form exactly as written in the template (NFC, every mark kept) |
| `target_sense_id` | the `<id:…>` / `id=` the template asked for, if any |
| `extraction` | `template` (the template names this link explicitly) or `chain` (inferred from "From X, from Y" order) |
| `hop` | 0 for a link from the entry itself; n for the n-th link of a chain or the n-th level of nesting |
| `confidence` | number in [0, 1], below |
| `resolution` | from ADR 0001: `resolved`, `resolved_by_id`, `ambiguous`, `stub` |
| `run_id` | the build run that produced the link (ADR 0006) |

### Chains

- **Classic chain:** within one entry's etymology section, the classic link templates are taken in
  text order T0, T1, T2, …. T0 gives a link entry → T0 target with `hop = 0`,
  `extraction = template`. Each following template gives a link T(i−1) target → T(i) target with
  `hop = i`, `extraction = chain`. Example `de:Herz`: Herz → gmh:hërze (0) → goh:hërza (1) →
  gmw-pro:*hertā (2) → gem-pro:*hertô (3) → ine-pro:*ḱḗr (4).
- **Chain hops vs. ancestor files (`CHAIN_SUPERSEDED`).** Take a chain link (`extraction = chain`)
  whose source word S resolves to an entry (`status = entry`) from a loaded ancestor file, where that
  entry still has at least one `hop = 0` link after filtering. That entry's own `hop = 0` links are
  authoritative for S:
  - if the chain link has the same (src, dst, type) as one of them, the two merge as duplicates
    under the rule below (`evidence_count` + 1; the `template`, hop-0 evidence is the one kept);
  - otherwise the chain link is dropped with reason `CHAIN_SUPERSEDED`, counted in the DQ report.

  If S has no entry, or its entry has no `hop = 0` link, the chain link is kept: it is then the only
  evidence for S's origin. Why: a word's own page is a better witness for its etymology than the
  "from X, from Y" text on a descendant's page, and the probe's wrong long chains were chain hops
  (`sh:umjetnost → … *umъ → de:Künstler`, the `de:Farm` chain mixing two words). Example: in
  `de:Herz`, the chain link `gmh:hërze → goh:hërza` is checked against the `gmh` entry `herze` if
  that file is loaded. Middle and Old High German have few entries (probe: 6% and 20% of referenced
  words), so most German chain hops are still kept.
- **Explicit nesting** in `{{ety}}`/`{{etymon}}` (`code:term<ety:kw<code:term>>`) gives links with
  `extraction = template` and `hop` = nesting depth.
- **Old Polish `{{ety}}` trees** (`tree:"+"` / `tree=1`): the Polish entry names only its first hop
  (`zlw-opl:serce`). The rest of the tree is rendered from other pages and is **not** parsed from the
  expansion text; it comes from the Old Polish, Proto-Slavic, … files themselves (ADR 0006 rule
  "ancestor files contribute their own first hop").
- Templates with an empty term or `-` (sample: `{{inh|de|gmh|-}}` in `de:Bank`) name only a language:
  logged as `NO_TERM`, no link, and they do **not** break the chain.
- `TODO(verify)`: which templates between two link templates should break a classic chain (for
  example `cog`, a sentence boundary in `etymology_text`). The probe found ~5% wrong chain hops,
  coming from "influenced by" links, parallel routes, cognate or descendant mentions and blends;
  phase 1 tests must cover these.

### Confidence

- v1 assigns confidence by extraction class: `template` 0.9, `chain` 0.6. These are **the probe's
  heuristic values, not measured probabilities**: the probe measured 95.0% precision for chain-based
  path hops and 96.3% for explicit `{{ety}}` edges (one rater). `TODO(verify)`: calibrate against the
  golden set in phase 2, or replace the number by the extraction class alone.
- `der` is treated as a weak link by queries and by Role 2's warning rule, independent of
  confidence.

### Duplicates and parallel links

- **Duplicates** (same `src_word_id`, `dst_word_id`, `type`), from the classic and new syntax, from
  several POS entries of one word, or from two files, are merged into **one link**. The kept evidence
  is the first record in this order: `extraction = template` before `chain`; lower `hop`; `syntax =
  ety` before `classic`; then `source_entry`, `template`, `target_form` in code-point order.
  `evidence_count` stores how many records were merged. All evidence records stay in the internal
  `link_evidence` stage file (ADR 0006).
- **Parallel links** (same pair, different `type`) are kept as separate links and both get
  `has_parallel = true`. Queries that count or traverse pairs use `DISTINCT` on the pair (probe trap:
  48 rows instead of 7 for `pl:cegła` without it).
- **Self-loops** (`src = dst` after resolution) are dropped with reason `SELF_LOOP`. **Cycles** are
  kept and reported; Role 2's rule flags them.

## Consequences

- One link per (pair, type) makes Neo4j and RDF counts agree and makes loading idempotent with a
  `link_id` derived from (src, dst, type).
- `target_form` and `target_lang_raw` keep exactly what the source said, even after resolution to a
  different `form` or a full-language `lang`.
- Chain links are recognisable (`extraction = chain`) and can be excluded by any query or rule.

## Evidence

- Probe: template counts inh 3,618 · der 2,911 · bor 2,628 · calque 75 (sample); explicit `{{ety}}`
  edges rare in the probe's 2026-10-25 sample (301 of 6,973) but `ety` is now the most common
  template in de and pl (this ADR's sample).
- Probe: list-argument parser bug (`['fr:abandon<ref:', <TEMPLATE(...)>, '>']`) repaired 1,874 edges;
  the sample shows the same pattern in `pl:abandon` and `de:brutto`. Phase 1 handles it.
- Probe: duplicate (derived, etymon, type) triples within a file: 15,513; 276 links occur in two
  files.

## Open questions

1. `TODO(verify)`: complete `{{ety}}` keyword list; chain-break rules; confidence calibration.
