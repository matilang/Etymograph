# Architecture decision records

Each ADR records one decision: its context, the options considered, the decision, its consequences,
and the evidence behind it. Evidence comes from two places:

- **Feasibility probe:** a throwaway prototype run in October and November 2026 against the kaikki
  dump of 2026-10-21 (enwiktionary dump 2026-10-01). It is not part of this repository; numbers quoted
  from it are labelled "probe".
- **Data inspection:** real kaikki JSONL lines from the same dump (German and Polish files) and the
  Wiktionary Lua language modules, inspected while writing these ADRs. Numbers quoted from it are
  labelled "sample" and state their size.

Anything not yet confirmed against the data is marked `TODO(verify)` and must be resolved before or
during the phase that implements it.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-word-identity.md) | Word identity | Proposed |
| [0002](0002-language-model.md) | Language model | Proposed |
| [0003](0003-link-model.md) | Link model | Proposed |
| [0004](0004-neo4j-physical-model.md) | Neo4j physical model | Proposed |
| [0005](0005-rdf-export-layout.md) | RDF export layout | Proposed |
| [0006](0006-pipeline-and-reproducibility.md) | Pipeline and reproducibility | Proposed |
| [0007](0007-reserved-extension-slots.md) | Reserved extension slots | Proposed |

The exact table and N-Quads schemas that follow from these decisions are in
[`docs/data_contract.md`](../data_contract.md).

**Status values:** Proposed (written, under review) → Accepted (approved in a merged PR) →
Superseded by ADR n. A changed decision gets a new ADR; an accepted ADR is not rewritten.

**Format of each ADR:** Context · Options · Decision · Consequences · Evidence · Open questions.
