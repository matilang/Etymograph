# ADR 0004: Neo4j physical model

Status: Proposed

## Context

Neo4j 5.26 Community + APOC is the primary model. Role 3 writes the Cypher queries (paths, common
ancestors, donor profiles), Role 2 needs the same data for constraints. The probe loaded the same data
into Neo4j and measured the traps that matter here:

- the composite `Word(lang, word)` index is **not used for `lang` alone**: Q4 did a `NodeByLabelScan`
  over all 329,844 words; a single-property `Word(lang)` index took Q4 from 52.8 to 17.2 ms;
- without the `(lang, word)` index Q1 went from 1.7 to 49.2 ms;
- Community has one user database, and no node key or property existence constraints.

## Options

- **Language of a word:** a `lang` property only; an `IN_LANGUAGE` relationship only; or both.
- **Loading:** `neo4j-admin database import` (fastest, but only into an empty database); `LOAD CSV`
  (needs the files inside the container's import directory); the Python driver with `UNWIND` batches.
- **Ancestry:** direct `HAS_ANCESTOR` edges, or the transitive closure.

## Decision

### Labels and properties

| Label | Key | Properties |
|---|---|---|
| `Word` | `id` | all `words` columns (data contract): `lang`, `key`, `etym_no`, `form`, `status`, `stub_reason`, `pos`, `ety_ids`, `gloss`, `source_file`, `is_reconstruction`, `ipa`, `ipa_source`, `first_run_id`, `last_run_id` |
| `Reconstruction` | — | extra label on `Word` nodes with `is_reconstruction = true` |
| `Language` | `code` | all `languages` columns |
| `ImportRun` | `run_id` | all `import_runs` columns |

- `Reconstruction` is a label, not a separate node type: a reconstruction is a word like any other,
  and the label lets queries say `(:Reconstruction)` and lets the planner use label scans.
- List columns (`pos`, `ety_ids`, `scripts`) become Neo4j lists of strings.

### Relationships

| Relationship | From → To | Properties |
|---|---|---|
| `DERIVED_FROM` | `Word` (derived) → `Word` (etymon) | all `links` columns except the endpoints, including `link_id`, `type` |
| `IN_LANGUAGE` | `Word` → `Language` | none |
| `HAS_ANCESTOR` | `Language` → `Language` (direct ancestor) | `source` (`explicit` / `family_default`), `ordinal` |
| `VARIANT_OF` | etymology-only `Language` → parent `Language` | none |

- **One relationship type `DERIVED_FROM` with a `type` property**, not four relationship types:
  "any etymological ancestor" is the common query (`-[:DERIVED_FROM*]->`), and C3/C5 queries filter on
  `type`. `TODO(verify)` in phase 3: whether a relationship index on `DERIVED_FROM(type)` helps Q4/Q6.
- **Both `lang` and `IN_LANGUAGE`.** `Word.lang` is the canonical value and is indexed: it is what
  filters and point lookups use (the measured trap). `IN_LANGUAGE` is derived from it by the loader,
  so a word's language is a graph pattern too, for example
  `(w)-[:IN_LANGUAGE]->(:Language)-[:HAS_ANCESTOR*]->(a)` in the C3 ancestor rule and for the
  language-level graph. Cost: one extra relationship per word; the loader writes both from the same
  column, so they cannot disagree. Rejected: `IN_LANGUAGE` only (every language filter becomes an
  expand from a few huge `Language` nodes) and property only (language ancestry then needs a value
  join instead of a pattern, which is what the course wants to show).
- **`HAS_ANCESTOR` is direct only** (ADR 0002); transitive ancestry is `HAS_ANCESTOR*`.
- **Provenance:** every node and relationship carries `last_run_id` (and nodes `first_run_id`). The
  `ImportRun` node holds the run metadata. There is **no relationship from every element to
  `ImportRun`**: it would create one supernode with hundreds of thousands of relationships and adds
  nothing a property lookup cannot do.

### Constraints and indexes (created before any data is loaded)

```cypher
CREATE CONSTRAINT word_id IF NOT EXISTS FOR (w:Word) REQUIRE w.id IS UNIQUE;
CREATE CONSTRAINT language_code IF NOT EXISTS FOR (l:Language) REQUIRE l.code IS UNIQUE;
CREATE CONSTRAINT import_run_id IF NOT EXISTS FOR (r:ImportRun) REQUIRE r.run_id IS UNIQUE;
CREATE CONSTRAINT derived_from_link_id IF NOT EXISTS
  FOR ()-[d:DERIVED_FROM]-() REQUIRE d.link_id IS UNIQUE;
CREATE INDEX word_lang IF NOT EXISTS FOR (w:Word) ON (w.lang);
CREATE INDEX word_lang_key IF NOT EXISTS FOR (w:Word) ON (w.lang, w.key);
CREATE INDEX word_lang_form IF NOT EXISTS FOR (w:Word) ON (w.lang, w.form);
CREATE INDEX derived_from_type IF NOT EXISTS FOR ()-[d:DERIVED_FROM]-() ON (d.type);
```

- `word_lang` is the single-property index the probe showed is needed; the composite indexes serve
  lookups by key (resolution checks) and by form (user-facing queries).
- Identity uniqueness is enforced on `id`, which is a hash of (`lang`, `key`, `etym_no`). The build
  checks that the triple is unique before export.
- `TODO(verify)`: that relationship property uniqueness constraints are available in 5.26
  **Community** (they were added in 5.7; edition availability not yet checked). Fallback: a
  relationship range index on `link_id` and a loader-side uniqueness check.

### Batching and MERGE

- Loader: the Python driver (`neo4j` package, pinned), reading the handover CSVs, sending
  `UNWIND $rows AS row` batches of 10,000 rows per transaction. `TODO(verify)`: tune the batch size in
  phase 3 (the probe used 20k-row `LOAD CSV` transactions; full L load 9 s).
- Order: constraints/indexes → `Language` → `HAS_ANCESTOR`, `VARIANT_OF` → `Word` + `IN_LANGUAGE` →
  `DERIVED_FROM` → `ImportRun`.
- Nodes: `MERGE (w:Word {id: row.id}) ON CREATE SET w.first_run_id = row.run_id SET w += row.props,
  w.last_run_id = row.run_id`; the `Reconstruction` label is set in the same statement.
- Relationships: `MATCH` both endpoints by `id` (index seek), then
  `MERGE (a)-[d:DERIVED_FROM {link_id: row.link_id}]->(b) SET d += row.props`.
- **Idempotent:** loading the same run twice gives identical counts (phase 3 test).
- **Retiring:** after a load, elements of the loaded languages whose `last_run_id` is not the current
  run (for example a stub that became a numbered entry, ADR 0001) are deleted in batches. Elements
  of languages not in the run are not touched. `TODO(verify)`: the exact scope rule in phase 3.
- Rejected: `neo4j-admin import` (empty database only, so it cannot do `add-lang`); `LOAD CSV` (ties
  the loader to the container's import directory; the handover CSVs are the same either way).

## Consequences

- Queries filter on `w.lang` and get an index seek; patterns can still go through `IN_LANGUAGE`.
- `DISTINCT` is still needed on multi-hop queries because of parallel links (ADR 0003) and cycles.
- The common-ancestor query must use **two `MATCH` clauses**: the one-pattern form
  `(x)-[*0..]->(c)<-[*0..]-(y)` lost ancestors on 4–5 of 10 golden pairs in the probe (relationship
  isomorphism). Role 3 owns the queries; this is recorded here because it constrains the model only
  in that it must not depend on one-pattern queries.

## Evidence

- Probe, three-database run: index effects (Q1 1.7 → 49.2 ms without `(lang, word)`; Q4 52.8 → 17.2 ms
  with `Word(lang)`), load time 9 s for 338,821 nodes / 277,384 relationships, one-pattern trap.

## Open questions

- `TODO(verify)`: relationship uniqueness constraint in Community; index on `DERIVED_FROM(type)`;
  batch size; retire scope.
