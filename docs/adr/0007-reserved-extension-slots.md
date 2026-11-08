# ADR 0007: Reserved extension slots

Status: Proposed

## Context

Three extensions are likely after the MVP, and the probe measured all three:

- **Pronunciation:** IPA coverage of lemmas is pl 99.8%, de 64.1%, sh 86.5%, fr 77.3%, ro 10.0%;
  PanPhon distance separates direct links (median 1.45) from unrelated pairs (3.61).
- **Compounds and affixes (`COMPOSED_OF`):** 37–51% of de/pl/nl/ro lemmas have only a morphological
  template, and 67–93% of compound lemmas reach an etymology chain through a part. Including them
  naively puts 46–74% of nodes in one component.
- **Data versions:** comparing two dumps (course criterion C6) was not tried in the probe.

None of them is loaded in the MVP. The goal of this ADR is that adding them later needs **no change**
to existing columns, labels, relationship types, IRIs or constraints, only additions.

## Options

- Add the slots only when needed (no cost now, but a later schema change that breaks Role 2's
  shapes and Role 3's queries) vs. **reserve them now** as nullable columns, names and rules that the
  v1 contract already documents. **Reserve now.**

## Decision

### Pronunciation

- `words.ipa` (string, nullable) and `words.ipa_source` (enum, nullable: `wiktionary`, `epitran`,
  `wikidata`) are in contract v1 and are **null in v1**.
- `ipa` holds one transcription as written in the source, delimiters included (`/…/` or `[…]`);
  the probe found both notations and several variants per entry, so normalisation is a separate,
  documented step when the slot is filled, not part of the stored value. `TODO(verify)`: which kaikki
  `sounds` entry to pick when there are several (the probe took the first).
- `links.pron_dist` (float, nullable) and `links.pron_dist_method` (string, nullable, for example
  `panphon-wfed-v0.22.2`) are reserved, null in v1. A distance is computed outside the database
  (none of the three systems can compute PanPhon distances in-database, probe).
- Neo4j: same property names on `Word` / `DERIVED_FROM`. RDF: `ety:ipa`, `ety:ipaSource`,
  `ety:pronDist`, `ety:pronDistMethod`.

### `COMPOSED_OF`

- Reserved relationship `(:Word)-[:COMPOSED_OF {composition_id, position, template, run_id}]->(:Word)`.
  `position` is the 1-based part index in the template. One `composition_id` per analysis (one
  template instance), so competing analyses of one word (probe: `englisch` Engel vs England) do not
  mix and "one part per position" holds per composition.
- Reserved label `Affix` for parts that start or end with `-`; linking elements (de/nl `-s-`, `-n-`,
  `-en-`, `-e-`, pl `-o-`) are not nodes but a `linking_elements` attribute of the composition.
- Reserved tables (contract v2): `compositions(composition_id, word_id, template, linking_elements,
  run_id)` and `composition_parts(composition_id, position, part_word_id, part_form_raw)`.
- Reserved RDF: `ety:Composition` with `ety:compositionOf`, `ety:hasPart [ety:part …; ety:position n]`,
  in the same per-file graphs.
- `COMPOSED_OF` is **never** a `DERIVED_FROM` and never an `ety:derivedFrom` triple, so etymology
  paths, cognate queries and C3 ancestor rules are unaffected by construction.
- Extraction is designed in phase 1 so that morphology templates are already parsed into
  `link_records` with a `morph` kind and dropped in `filter` with reason `RESERVED_MORPH` (counted).
  Turning it on later is a filter change plus the new tables.

### Data versions

- Every element carries the `run_id` that produced it (tables, CSV, RDF `ety:runId`); Neo4j keeps
  `first_run_id` and `last_run_id` (ADR 0004); `ImportRun` nodes accumulate, one per loaded run.
- A two-dump comparison is then a query: elements with `last_run_id` = old run are absent from the
  new dump; `first_run_id` = new run are new. Because ids are content-derived (ADR 0006), the same
  word or link in two dumps has the same id.
- Neo4j Community has one user database, so versions are compared inside one database this way,
  not by loading two databases.
- RDF graph IRIs in v1 are unversioned (`etyd:graph/de`). Reserved for archival loads of an older
  run next to the current one: `etyd:graph/{run_id}/{code}`. This is an addition; the current graphs
  keep their IRIs.

### Other reserved columns

- `languages.glottocode` and `languages.iso639_3` (nullable, null in v1) for the optional Glottolog
  / ISO enrichment (ADR 0002).

## Consequences

- The v1 CSVs have some always-null columns. That is the price of not changing the contract later.
- Role 2 and Role 3 can already write shapes and queries that mention the reserved names; they simply
  match nothing in v1.

## Evidence

- Probe: pronunciation coverage and distance numbers above; COMPOSED_OF coverage, hub sizes and
  component effects; Wikidata Lexemes not usable as an IPA source (ro 113 lexemes).

## Open questions

- `TODO(verify)`: which `sounds` entry to keep; whether linking elements are reliably recognisable
  from the template alone.
