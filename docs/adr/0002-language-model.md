# ADR 0002: Language model

Status: Proposed

## Context

Every word and every link names a language code. The C3 rules (Role 2) need, per language: a name,
a type, a family and its ancestors, for example "an `inh` link must point to an ancestor language".
Etymologies also use **etymology-only codes** such as `la-vul` (Vulgar Latin), `la-med` (Medieval
Latin) or `zlw-mpl` (Middle Polish), which have no entries of their own, and legacy **dotted codes**
such as `LL.` and `ML.`.

## Options

1. **Glottolog languoids as the key.** Rejected: in the probe only 71.1% of codes joined (76% of the
   misses are proto-languages), and Glottolog does not model historical stages as ancestors, so 100%
   of inherited links failed its ancestor check.
2. **ISO 639-3.** Joins 72.9% of codes; no proto-languages, no ancestry. Rejected as a key.
3. **Wiktionary's own language data** (`Module:languages/data/*`, `Module:etymology_languages/data`,
   `Module:families/data`), pinned to the kaikki dump. 99.7% of distinct codes join in the probe
   (the rest are parser artefacts), and 98.7% of inherited links pass its ancestor check. **Chosen.**

## Decision

### Codes and fields

- The **Wiktionary code is the primary key** of a language. Glottolog and ISO are optional
  enrichment, not used in the MVP.
- Fields are parsed from the module tables (field positions verified in the module data):

| Field | Source in the module table | Example |
|---|---|---|
| `code` | table key `m["…"]` | `pl`, `la-vul`, `gem-pro` |
| `name` | positional 1 | `Polish` |
| `wikidata_qid` | positional 2 (number → `Q…`) | `809` → `Q809` |
| `family_code` | positional 3 in language modules | `zlw-lch` |
| `parent_code` | positional 3 in `etymology_languages` (the full or etymology-only language it is a variety of) | `la-vul` → `la-cla` → `la` |
| `scripts` | positional 4 (comma list) | `Latn, Cyrl, Glag, Arab` |
| `ancestors` | `ancestors = "…"` (comma list) | `pl` → `zlw-mpl`, `de` → `de-ear` |
| `wikt_type` | `type = "…"`; absent → `regular`; etymology-only module → `etymology-only` | `reconstructed` |
| `strip_diacritics` | see ADR 0001 | `sh`, `sla-pro`, `la` |

- In the module data there are 296 `type = "reconstructed"` and 31 `type = "appendix-constructed"`
  entries, and 10,224 tables in total across languages, etymology-only languages and families.
- Families (`Module:families/data`) give `name`, parent family (positional 3) and an optional
  `protoLanguage` (45 families set it, for example `gmw-hgm` → `goh`).

### Type

- `wikt_type` is stored verbatim: `regular`, `reconstructed`, `appendix-constructed`,
  `etymology-only`.
- `category` is derived for queries and reports:
  - `proto` if `wikt_type = reconstructed`;
  - `etymology-only` if it comes from `Module:etymology_languages/data`;
  - `historical` if it is not `proto` and is a direct or transitive ancestor (below) of another
    `regular` language;
  - `modern` otherwise.
- `historical` is a **heuristic**: Wiktionary has no historical flag (probe: its own heuristic was
  name-based). `TODO(verify)`: list the languages the rule classifies differently from a name-based
  rule ("Old", "Middle", "Ancient", "Proto-") and review them by hand in phase 1.

### Ancestors

- **Explicit:** the `ancestors` list of the language.
- **Default family rule** (Wiktionary's): if a language has no explicit ancestors, its ancestor is
  its family's `protoLanguage`, or else `<family>-pro` if that code exists. A language that is itself
  the proto-language of its family uses the parent family instead. Example: `gem-pro` (family `gem`,
  no explicit ancestors) → family `gem` has parent `ine` → `ine-pro`.
- `language_ancestors` stores **direct** ancestor edges only, each with `source` = `explicit` or
  `family_default`. Transitive ancestry is a path query (`HAS_ANCESTOR*`, `ety:hasAncestor+`),
  which is what the C3/C5 work wants to demonstrate; the probe's transitive table (26,755 rows) is
  not stored.
- The probe re-implemented the default rule and checked it on 8 languages only.
  `TODO(verify)`: compare our ancestor sets with Wiktionary's `getAncestors` for all languages that
  appear in de/pl links (for example via the ancestor lists shown on Wiktionary language category
  pages) in phase 1.

### Etymology-only codes

- Etymology-only languages are `Language` rows with `wikt_type = etymology-only` and a
  `parent_code`. The parent chain ends at a full language: `la-vul` → `la-cla` → `la`;
  `la-med` → `la`; `zlw-mpl` → `pl`; `de-ear` → `de`.
- Their own `ancestors` are kept (`la-med` → `la-lat`, `zlw-mpl` → `zlw-opl`, `de-ear` → `gmh`).
  This is what makes the chains `pl` → `zlw-mpl` → `zlw-opl` and `de` → `de-ear` → `gmh` work: in the
  module data, `pl`'s explicit ancestor is `zlw-mpl`, not `zlw-opl`.
- The parent relation is stored separately from ancestry (`parent_code`, Neo4j `VARIANT_OF`, RDF
  `ety:variantOf`), because a variety is not a descendant of its parent. The ancestor check accepts
  a source language that is an ancestor **or** a variety of an ancestor. The probe's 18 false
  positives (`la-vul ← la` 16, `la-eme ← la` 2) came from not making this distinction.
- **Words** live in the **full** language: a link to `la-vul:*fōrmāticus` targets a Latin word,
  because Wiktionary files such terms under Latin. The code as written is kept on the link
  (`target_lang_raw`, ADR 0003), so nothing is lost for the language-level graph.
- `TODO(verify)`: whether Wiktionary's `getAncestors` for an etymology-only language without
  `ancestors` falls back to its parent's ancestors.

### Dotted legacy codes

- `LL.`, `ML.`, `NL.`, `VL.`, `EL.`, `CL.`, `RL.` are mapped to `la-lat`, `la-med`, `la-new`,
  `la-vul`, `la-ecc`, `la-cla`, `la-ren` (the probe's table). The sample has them in real data, for
  example `{{bor|de|LL.|ōvālis}}` in `de:oval` and `{{ety|pl|:der|NL.:gallium}}` in `pl:gal`.
- They are **not** in the module tables we parsed. `TODO(verify)`: find where Wiktionary defines
  them (an alias table in the pinned modules) and generate the map from there; until then the map is
  a small reviewed table in the code, with a unit test per entry.

### Unknown codes

- A code that matches nothing after the dotted map is logged with reason code `UNKNOWN_LANG` and its
  link is dropped. Comma lists such as `ru,uk` (sample: `{{der|de|ru,uk|О́льга}}` in `de:Olga`) are
  logged as `MULTI_LANG_CODE` and dropped in the MVP. `TODO(verify)`: the share of such links in de
  and pl; if it is material, split them into one link per code in phase 1.

## Consequences

- Language codes in our data are exactly Wiktionary's, so a reader can look any code up on
  Wiktionary.
- C3 rules can be written against `HAS_ANCESTOR` plus `VARIANT_OF` without special cases.
- We depend on parsing Lua tables. The probe parsed them with regular expressions; phase 1 must do
  it more robustly (a small Lua-table reader with tests), because the shared tables
  (`s[...]`, `c.*`) must also be resolved.

## Evidence

- Probe: code join 99.7% (Wiktionary) vs 72.9% (ISO) vs 71.1% (Glottolog); ancestor check 98.7%
  valid with Wiktionary data, 100% "invalid" with Glottolog.
- Module data: `m["pl"]` has `ancestors = "zlw-mpl"`; `m["zlw-mpl"]` (etymology-only, parent `pl`)
  has `ancestors = "zlw-opl"`; `m["de"]` has `ancestors = "de-ear"`; `m["la-vul"]` has parent
  `la-cla`; `m["gem"]` has no `protoLanguage`.

## Open questions

- `TODO(verify)`: default-rule parity with `getAncestors`; etymology-only ancestor fallback; source
  of the dotted codes; the `historical` heuristic; share of comma-list codes.
