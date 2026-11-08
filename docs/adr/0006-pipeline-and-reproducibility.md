# ADR 0006: Pipeline and reproducibility

Status: Proposed

## Context

The pipeline turns about 2–3 GB of kaikki JSONL (de 1,095 MB, pl 898 MB, plus ancestor files) and the
Wiktionary language modules into clean tables, CSV + N-Quads for the team, and a Neo4j database. It
must be re-runnable stage by stage, give byte-identical output for identical input, explain every
dropped record, and accept new languages (`make add-lang CODE=sh`, then French and Romanian) without
schema changes or re-processing the languages already built.

## Options

- **One script per run** (the probe: `fetch → parse → export → validate → aggregate`) vs **pure stages
  over files**. Stages win: each can be tested and re-run alone.
- **Internal format:** JSONL (simple, large, untyped) vs Parquet (typed, compressed, columnar) vs
  SQLite. **Parquet** for internal stages; **CSV + N-Quads** for the handover, because every team
  tool reads them (Neo4j loader, GraphDB, PostgreSQL for the report comparison, pandas).
- **Incremental model:** per-language end-to-end (resolve only the new language) vs per-language
  fetch/extract + global resolve/build. **Global resolve/build**, see `add-lang` below.

## Decision

### Stages and files

| Stage | Reads | Writes |
|---|---|---|
| `fetch` | config, network | `data/raw/kaikki/{code}.jsonl`, `data/raw/wiktionary/<module tar>`, `data/raw/manifest.json` |
| `extract` | one raw file | `data/stage/extract/{code}/entries.parquet`, `link_records.parquet`, `drops.parquet`; `data/stage/extract/languages/*.parquet` from the modules |
| `resolve` | all extract partitions | `data/stage/resolve/words.parquet`, `link_evidence.parquet`, `drops.parquet` |
| `filter` | resolve output | `data/stage/filter/link_evidence.parquet`, `drops.parquet` |
| `build` | filter output + languages | `data/clean/{languages,language_ancestors,families,words,links}.parquet`, `data/clean/dq_report.{md,json}` |
| `export` | clean tables | `data/export/csv/*.csv`, `data/export/nq/{graph}.nq` |
| `load` | export CSVs | Neo4j |

- Each stage reads only the output of the previous stage(s) listed and its config, and can be re-run
  alone. Domain types (`Word`, `Language`, `EtymLink`, `ImportRun`) do no I/O; stages are functions
  from input files to output files.
- `data/raw` is immutable: written once by `fetch`, never edited. A new dump goes to new files with a
  new manifest entry.
- Run records go to `data/runs/{run_id}.json` (timings, timestamps, host, counts). They are the only
  files with timestamps.

### Manifest

One entry per raw input, written by `fetch`:

| Field | Example |
|---|---|
| `source` | `kaikki`, `wiktionary-modules` |
| `code` | `de` (null for the modules) |
| `url` | `https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl` |
| `retrieved_at` | ISO 8601 UTC |
| `last_modified` | HTTP `Last-Modified` (probe: 2026-10-21 for de/pl) |
| `dump_date` | the enwiktionary dump the file was extracted from (probe: 2026-10-01) |
| `wiktextract_version` | as published by kaikki |
| `bytes`, `sha256` | of the stored file |

- The **Wiktionary modules are pinned to the same dump** by taking them from kaikki's "all Lua
  modules" tar (probe: 89.6 MB gz) rather than from the live wiki. `TODO(verify)`: its exact URL and
  that it carries the same dump date as the JSONL files; where `dump_date` and `wiktextract_version`
  are published for each file.
- Fetch is polite: descriptive User-Agent with contact from `.env`, retries with backoff, honours
  `Retry-After`, streams to disk, resumes with HTTP Range (kaikki supports it), verifies size.

### Stable ids and determinism

- `word_id = "w_" + hex(sha256("{lang}\x1f{key}\x1f{etym_no}" UTF-8))[:16]`
- `link_id = "l_" + hex(sha256("{src_word_id}\x1f{dst_word_id}\x1f{type}"))[:16]`
- `run_id = "r_" + hex(sha256(canonical JSON of: sorted manifest sha256 values, pipeline git commit,
  config))[:12]`. Identical inputs, code and config give the identical `run_id`, so `run_id` inside
  data files does not break byte-identity. A dirty working tree is recorded in the run record and
  makes the run id differ.
- 64-bit ids: the build fails on any collision (expected probability ~10⁻⁸ at 10⁶ words).
- Every output is sorted by a total order (ids, then all columns); no set or dict iteration order
  reaches a file. CSV and N-Quads are written with fixed settings (UTF-8, `\n`); Parquet with a
  pinned `pyarrow` and fixed writer options.
- **Determinism check** (phase 2): build twice from the same raw files, compare SHA-256 of every file
  under `data/clean` and `data/export`. `import_runs.csv` is excluded only if it holds timestamps
  (data contract).

### Lemmas and file roles

- An entry is a **lemma** unless every sense has `form_of` or `alt_of` or the tag `form-of`
  (probe rule; 74% of entries are inflected forms). Non-lemmas are dropped as `NON_LEMMA`.
  In the first 60,000 lines, 33,268 de and 29,345 pl entries match this rule.
- **Target languages** (MVP: `de`, `pl`): all lemma entries become words, with or without links, so a
  lookup can tell "unknown word" from "no known link".
- **Ancestor files**: the full-language ancestors of the target languages from the module data
  (ADR 0002) plus configured donor files. Default MVP set: `gmh`, `goh`, `gmw-pro`, `gem-pro`,
  `ine-pro`, `zlw-opl`, `sla-pro`, `ine-bsl-pro`, `la`, `fr`. `TODO(verify)`: generate the ancestor
  part from the module data; decide on `fro`, `frm`, `grc` and `en` (3.4 GB) as donors (open
  question). Entries of ancestor files become words only if reachable from a target-language lemma.

### Graph rules (filter stage, from the probe)

| Reason code | Rule |
|---|---|
| `ANCESTOR_CHAIN_HOP` | links from ancestor files keep only `hop = 0` (the entry's own first hop) |
| `REVERSED_LANG` | drop a link whose etymon's language descends from the derived word's language |
| `UNKNOWN_LANG`, `MULTI_LANG_CODE` | drop (ADR 0002) |
| `NO_TERM`, `EMPTY_TERM` | drop: template names a language only, or the term is empty |
| `SELF_LOOP` | drop (ADR 0003) |
| `NOT_REACHABLE` | ancestor-file words and links not reachable from any target-language lemma |
| `NON_LEMMA` | extract stage, above |
| `MALFORMED_ARG` | an argument that cannot be repaired |

Repairs are counted too: `LIST_ARG_REPAIRED` (wiktextract's stringified list arguments), and
`DOTTED_CODE_MAPPED`. Duplicates merged under ADR 0003 are counted as `MERGED_DUPLICATE`.
Every drop is a row in the stage's `drops.parquet` (reason, source entry, raw template); the DQ
report gives counts per reason, resolution rates and the top unresolved targets.

### `add-lang`

`make add-lang CODE=sh`:

1. Adds `sh` to the target languages in config; computes its ancestor files from the module data.
2. Fetches only the files not yet in the manifest; extracts only those.
3. Re-runs `resolve → filter → build → export` over **all** extract partitions.
4. Loads with MERGE (ADR 0004), retiring elements of affected languages that the new run no longer
   produces.

- Existing languages are never re-fetched or re-extracted, and nothing in the schema changes:
  languages are rows, graphs are files, constraints are language-independent.
- Resolution is global on purpose: a new file can turn earlier stubs into entries (for example
  `sh` links into `sla-pro` entries that `pl` already linked as stubs). Per-language resolution was
  rejected because those stubs would stay stale. Resolve/build work on Parquet only; the expensive
  steps (download, JSON parsing) stay per-language. `TODO(verify)`: time the global steps in phase 2.

## Consequences

- Every stage can be tested on fixtures alone; CI never downloads.
- Byte-identical outputs make the determinism check a hash comparison.
- `data/` is git-ignored; reproducibility rests on the manifest (URL + SHA-256), the lock file and
  the git commit in `run_id`.

## Evidence

- Probe: the full pl file (898 MB) streamed in 28 s, de + sh together in 53 s; Italian add-lang first run 27 min (dominated by
  pySHACL), cached rerun 1.1 s; ancestor-file chain hops created hubs until filtered (7,259 chained
  hops, 2,565 reversed edges, 460 malformed codes dropped in one run).
- Probe: kaikki server sent gzip and supports HTTP Range; one parallel download timed out.

## Open questions

- Donor files beyond `la` and `fr` (`fro`, `frm`, `grc`, `en`?).
- `TODO(verify)`: module tar URL and pin; manifest dump-date source; timing of the global steps.
