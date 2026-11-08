# EtymoGraph data contract

**Contract version: v1** (status: proposed, phase 0). Owner: Role 1 (@vikaloeldar).

This document fixes the exact shape of the clean data that Role 1 hands over to Role 2 (SHACL,
GraphDB) and Role 3 (Cypher queries, analysis). The decisions behind it are in
[`docs/adr/`](adr/README.md). A change to a column name, type, nullability or meaning is a contract
change: it needs a new contract version and a note in the changelog at the end.

## 1. General rules

- **Files.** Clean tables are produced as Parquet (`data/clean/`) and exported as CSV
  (`data/export/csv/{table}.csv`); RDF as N-Quads (`data/export/nq/{graph}.nq`). `data/` is not in git.
- **CSV format.** UTF-8 without BOM, comma separator, RFC 4180 quoting, `\n` line ends, one header
  row with the column names below, in the order below.
- **Null.** An empty CSV field means null. Strings are never empty when not null (the build turns
  empty strings into null), so the two cannot be confused.
- **Types.** `string`, `int` (64-bit), `float` (64-bit), `bool` (`true` / `false`), `list<string>`
  (a JSON array in CSV, for example `["noun","verb"]`, sorted, no duplicates; a Neo4j list; an
  array in Parquet).
- **Unicode.** All strings are NFC. `form` columns keep every diacritic and letter as written.
- **Order.** Rows are sorted by the primary key, so files are byte-identical for identical input.
- **Enums.** Values outside the listed set are a contract violation.
- **Reserved columns** (ADR 0007) are present with their final name and type and are null in v1.

## 2. `languages`

One row per Wiktionary language code that appears in the data: full languages, etymology-only
languages, and every ancestor or parent they reference. Source: Wiktionary language modules pinned
to the kaikki dump (ADR 0002).

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `code` | string | no | **PK.** Wiktionary code | `la-vul` |
| `name` | string | no | canonical English name | `Vulgar Latin` |
| `wikt_type` | string enum | no | `regular`, `reconstructed`, `appendix-constructed`, `etymology-only` | `etymology-only` |
| `category` | string enum | no | `modern`, `historical`, `proto`, `etymology-only` (derived, ADR 0002; `historical` is heuristic) | `etymology-only` |
| `family_code` | string | yes | FK → `families.code`; null for etymology-only languages and languages without a family | (null) |
| `parent_code` | string | yes | FK → `languages.code`; only for etymology-only languages: the language it is a variety of | `la-cla` |
| `full_code` | string | no | the full language at the end of the parent chain; equals `code` for full languages | `la` |
| `scripts` | list<string> | yes | script codes from the module data | `["Latn"]` |
| `wikidata_qid` | string | yes | Wikidata item | `Q37560` |
| `has_strip_rule` | bool | no | whether a `strip_diacritics` rule applies (own or inherited, ADR 0001) | `false` |
| `glottocode` | string | yes | reserved, null in v1 | |
| `iso639_3` | string | yes | reserved, null in v1 | |
| `run_id` | string | no | FK → `import_runs.run_id` | `r_0a1b2c3d4e5f` |

## 3. `language_ancestors`

Direct ancestor edges only; transitive ancestry is a path query.

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `lang_code` | string | no | **PK part.** FK → `languages.code` | `pl` |
| `ancestor_code` | string | no | **PK part.** FK → `languages.code` | `zlw-mpl` |
| `source` | string enum | no | `explicit` (the language's `ancestors` field) or `family_default` (Wiktionary's default family rule) | `explicit` |
| `ordinal` | int | no | 1-based position in the `ancestors` list; 1 for `family_default` | `1` |
| `run_id` | string | no | | `r_0a1b2c3d4e5f` |

## 4. `families`

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `code` | string | no | **PK.** Wiktionary family code | `zlw-lch` |
| `name` | string | no | | `Lechitic` |
| `parent_code` | string | yes | FK → `families.code` | `zlw` |
| `proto_language_code` | string | yes | the family's `protoLanguage` if set; FK → `languages.code` | (null) |
| `run_id` | string | no | | `r_0a1b2c3d4e5f` |

## 5. `words`

One row per word node: a Wiktionary entry (all its parts of speech), or a stub / ambiguous page node
created by link resolution (ADR 0001). Identity is (`lang`, `key`, `etym_no`).

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `word_id` | string | no | **PK.** `w_` + 16 hex of SHA-256 over `lang \x1f key \x1f etym_no` | `w_3f2a9c0d1e4b5a67` |
| `lang` | string | no | FK → `languages.code`; always a full language (`full_code = code`) | `la` |
| `key` | string | no | entry key: NFC + Wiktionary's `strip_diacritics` rule; only for resolution | `tegula` |
| `etym_no` | int | no | kaikki `etymology_number`; `0` if the page has a single, unnumbered etymology, and for stub and ambiguous page nodes | `0` |
| `form` | string | no | the word as written, every mark kept; reconstructions start with `*` | `tēgula` |
| `is_reconstruction` | bool | no | the term is a reconstruction (`*`) | `false` |
| `status` | string enum | no | `entry` (from a loaded lemma entry), `stub` (no entry found), `ambiguous` (page with several homographs that a link could not choose between) | `entry` |
| `stub_reason` | string enum | yes | only when `status = stub`: `no_entry` (file loaded, no entry) or `no_file` (language file not in the build) | (null) |
| `pos` | list<string> | yes | kaikki `pos` values of the merged entries; null for stubs | `["noun"]` |
| `ety_ids` | list<string> | yes | etymology ids of the entry from `{{ety\|…\|id=}}`, `{{etymon\|…\|id=}}`, `{{etymid}}` | `["bench"]` |
| `gloss` | string | yes | first gloss of the first sense, as in kaikki | `tile, roof-tile` |
| `source_file` | string | yes | language file the entry came from; null for stub/ambiguous | `la` |
| `ipa` | string | yes | reserved (ADR 0007), null in v1 | |
| `ipa_source` | string enum | yes | reserved: `wiktionary`, `epitran`, `wikidata`; null in v1 | |
| `run_id` | string | no | | `r_0a1b2c3d4e5f` |

Constraints: (`lang`, `key`, `etym_no`) is unique. `stub_reason` is non-null iff `status = stub`.
For `status ∈ {stub, ambiguous}`, `etym_no = 0`.

Examples (illustrative, not measured output):

| word_id | lang | key | etym_no | form | status |
|---|---|---|---|---|---|
| `w_…` | `de` | `Bank` | 1 | `Bank` | `entry` |
| `w_…` | `de` | `Bank` | 2 | `Bank` | `entry` |
| `w_…` | `pl` | `cegła` | 0 | `cegła` | `entry` |
| `w_…` | `sla-pro` | `*sьrdьce` | 0 | `*sь̑rdьce` | `stub` (if `sla-pro` not loaded) |

## 6. `links`

One row per (derived word, etymon, type) after merging duplicates (ADR 0003). Direction: `src` is
the derived word, `dst` the etymon.

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `link_id` | string | no | **PK.** `l_` + 16 hex of SHA-256 over `src_word_id \x1f dst_word_id \x1f type` | `l_9b1e04c2aa7d3f10` |
| `src_word_id` | string | no | FK → `words.word_id`; the derived word | `w_…` (`pl:cegła`) |
| `dst_word_id` | string | no | FK → `words.word_id`; the etymon | `w_…` (`zlw-opl:cegła`) |
| `type` | string enum | no | `inh`, `bor`, `der`, `calque` | `inh` |
| `source_entry` | string | no | FK → `words.word_id`; entry whose etymology produced the kept evidence | `w_…` (`pl:cegła`) |
| `template` | string | no | raw template name | `etymon` |
| `keyword` | string | yes | `{{ety}}`/`{{etymon}}` keyword as written; null for classic templates | `:inh` |
| `syntax` | string enum | no | `classic` or `ety` | `ety` |
| `target_lang_raw` | string | no | language code as written in the template | `zlw-opl` |
| `target_form` | string | no | target form as written (NFC) | `cegła` |
| `target_sense_id` | string | yes | `<id:…>` or `id=` the template asked for | `brick` |
| `extraction` | string enum | no | `template` or `chain` | `template` |
| `hop` | int | no | 0 = link from the entry itself; n = n-th chain link or nesting level | `0` |
| `confidence` | float | no | v1: `template` 0.9, `chain` 0.6 (heuristic, ADR 0003) | `0.9` |
| `resolution` | string enum | no | `resolved`, `resolved_by_id`, `ambiguous`, `stub` | `resolved_by_id` |
| `evidence_count` | int | no | number of evidence records merged into this link (≥ 1) | `2` |
| `has_parallel` | bool | no | another link with the same (src, dst) and a different type exists | `false` |
| `pron_dist` | float | yes | reserved (ADR 0007), null in v1 | |
| `pron_dist_method` | string | yes | reserved, null in v1 | |
| `run_id` | string | no | | `r_0a1b2c3d4e5f` |

Constraints: (`src_word_id`, `dst_word_id`, `type`) is unique; `src_word_id ≠ dst_word_id`;
`resolution` agrees with the `status` of `dst_word_id` (`stub` ↔ `stub`, `ambiguous` ↔ `ambiguous`,
`resolved*` ↔ `entry`).

## 7. `import_runs`

One row per build run. It contains no timestamps, so it is deterministic like the other tables;
timings live in the run record `data/runs/{run_id}.json`, and the Neo4j loader adds `loaded_at` to the
`ImportRun` node at load time.

| Column | Type | Null | Description | Example |
|---|---|---|---|---|
| `run_id` | string | no | **PK.** `r_` + 12 hex (ADR 0006) | `r_0a1b2c3d4e5f` |
| `contract_version` | string | no | this document's version | `v1` |
| `pipeline_commit` | string | no | git commit of the pipeline code (full SHA) | |
| `pipeline_dirty` | bool | no | working tree had uncommitted changes | `false` |
| `config_sha256` | string | no | SHA-256 of the effective config | |
| `target_languages` | list<string> | no | | `["de","pl"]` |
| `ancestor_files` | list<string> | no | | `["gem-pro","gmh",…]` |
| `manifest_sha256` | string | no | SHA-256 of `data/raw/manifest.json` | |
| `dump_date` | string | yes | enwiktionary dump date of the kaikki files (`YYYY-MM-DD`), from the kaikki page footer (ADR 0006) | `2026-10-01` |
| `wiktextract_version` | string | yes | wiktextract commits from the kaikki page footer (ADR 0006) | `19f9a30 6f96ddf` |
| `n_languages`, `n_words`, `n_links` | int | no | row counts of this run | |

## 8. N-Quads layout

Full rationale in [ADR 0005](adr/0005-rdf-export-layout.md).

- Vocabulary `ety:` = `https://matilang.github.io/Etymograph/ns/ety#`; data `etyd:` =
  `https://matilang.github.io/Etymograph/id/` (decided, ADR 0005).
- One file per named graph, lines sorted: `{code}.nq` for each language file
  (graph `etyd:graph/{code}`) and `languages.nq` (graph `etyd:graph/languages`). Nothing in the
  default graph.
- A language-file graph holds every link whose `source_entry` comes from that file, plus the full
  description of every word such a link touches, plus the file's words without links.
- `etyd:graph/languages` holds languages, families, ancestor and variety edges, and import runs.

| Resource | IRI | Class |
|---|---|---|
| word | `etyd:word/{word_id}` | `ety:Word` (+ `ety:Reconstruction` if `is_reconstruction`) |
| link | `etyd:link/{link_id}` | `ety:Link` |
| language | `etyd:lang/{code}` | `ety:Language` |
| family | `etyd:family/{code}` | `ety:Family` |
| run | `etyd:run/{run_id}` | `ety:ImportRun` |

| Column | Predicate | Object |
|---|---|---|
| words.form / key / etym_no | `ety:form` / `ety:key` / `ety:etymNo` | `xsd:string` / `xsd:string` / `xsd:integer` |
| words.lang | `ety:inLanguage` | language IRI |
| words.status / stub_reason | `ety:status` / `ety:stubReason` | `xsd:string` |
| words.pos, ety_ids (each value) | `ety:pos`, `ety:etyId` | `xsd:string` |
| words.gloss / source_file | `ety:gloss` / `ety:sourceFile` | `xsd:string` / language IRI |
| link, direct | `ety:derivedFrom` **and** one of `ety:inh`, `ety:bor`, `ety:der`, `ety:calque` (word → word) | word IRI |
| links.src / dst | `ety:source` / `ety:target` (on the link) | word IRI |
| links.type | `ety:linkType` | `xsd:string` |
| links.source_entry | `ety:sourceEntry` | word IRI |
| links.template / keyword / syntax | `ety:template` / `ety:keyword` / `ety:syntax` | `xsd:string` |
| links.target_lang_raw / target_form / target_sense_id | `ety:targetLangRaw` / `ety:targetForm` / `ety:targetSenseId` | `xsd:string` |
| links.extraction / resolution | `ety:extraction` / `ety:resolution` | `xsd:string` |
| links.hop / evidence_count | `ety:hop` / `ety:evidenceCount` | `xsd:integer` |
| links.confidence | `ety:confidence` | `xsd:decimal` |
| links.has_parallel | `ety:hasParallel` | `xsd:boolean` |
| languages.code / name / wikt_type / category | `ety:code` / `ety:name` / `ety:wiktType` / `ety:category` | `xsd:string` |
| languages.family_code | `ety:family` | family IRI |
| languages.parent_code | `ety:variantOf` | language IRI |
| language_ancestors | `ety:hasAncestor` (lang → ancestor) | language IRI |
| families.parent_code / proto_language_code | `ety:parentFamily` / `ety:protoLanguage` | family / language IRI |
| run_id (every word, link, language) | `ety:runId` | `xsd:string` |
| null columns | no triple | |

- `ety:inh`, `ety:bor`, `ety:der`, `ety:calque` are `rdfs:subPropertyOf ety:derivedFrom` in the
  vocabulary file; the export writes both triples, so no inference is needed.
- Direct `ety:hasAncestor` triples are direct ancestors only; use `ety:hasAncestor+` for transitive.
- `language_ancestors.source` and `ordinal` are not in RDF v1. `TODO(verify)` with Role 2 whether the
  rules need them.

## 9. Reason codes (data-quality report)

Every dropped, flagged or repaired record is counted under one of these codes (ADR 0006,
ADR 0007):

| Kind | Codes |
|---|---|
| drop (record removed) | `NON_LEMMA`, `UNKNOWN_LANG`, `MULTI_LANG_CODE`, `MULTI_TERM`, `NO_TERM`, `EMPTY_TERM`, `MALFORMED_ARG`, `ITEM_WITHOUT_LANG`, `NOT_LINK_KEYWORD`, `SELF_LOOP`, `REVERSED_LANG` (`inh` only), `ANCESTOR_CHAIN_HOP`, `CHAIN_SUPERSEDED`, `NOT_REACHABLE`, `RESERVED_MORPH` |
| warning (link kept) | `REVERSED_LANG_LOAN` (`bor`, `calque`), `REVERSED_LANG_DER` (`der`) |
| repair / merge | `LIST_ARG_REPAIRED`, `ALIAS_CODE_MAPPED`, `MERGED_DUPLICATE` |
| info (nothing removed) | `ETY_SELF_ITEM` (the page's own term inside `{{ety}}`) |

## Changelog

- **v1** (phase 0): initial contract.
- **v1, phase 1 clarification** (no column change): new reason codes `MULTI_TERM`,
  `ITEM_WITHOUT_LANG`, `NOT_LINK_KEYWORD`, `ETY_SELF_ITEM` (ADR 0003); `DOTTED_CODE_MAPPED`
  renamed `ALIAS_CODE_MAPPED` because Wiktionary's alias table also has non-dotted codes
  (ADR 0002). `words.form` of an entry is kaikki's canonical headword when it has the same key as
  the page title, otherwise the page title (ADR 0001). Base IRI decided (ADR 0005).