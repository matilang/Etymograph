# Shapes

SHACL shapes for the RDF export (Role 2). They check the N-Quads described in the
[data contract](../docs/data_contract.md) (sections 5–8) and the rules of the ADRs: required
fields, types and allowed values, IDs, consistency between the two RDF forms of a link,
and path rules such as "an `inh` link points to an ancestor language".

There are two ways to run them:

| | `validate.py` (pySHACL) | GraphDB |
|---|---|---|
| Checks | **all** shapes, enforced and warnings, on the whole data | the `enforced/` shapes, on each insert |
| Use it | to validate an export, in CI, after any change to shapes | as a guard while loading data |
| Needs | `uv` | Docker |

`validate.py` is the complete check. GraphDB enforces a subset (see
[GraphDB limits](#graphdb-limits)).

## Layout

```
shapes/
  prefixes.ttl          the ety: prefix for all SPARQL-based shapes (sh:declare), once
  enforced/             hard rules: violations; GraphDB rejects data that breaks them
  warnings/             soft rules: reported by validate.py only, never loaded into GraphDB
  validate.py           pySHACL runner
  docker-compose.yml    GraphDB 11.5.1
```

Every shape file keeps its own `@prefix` lines (Turtle prefixes are per file) and uses
`sh:prefixes etys:`, which points at the declaration in `prefixes.ttl`.

## Shapes

### `enforced/structure.ttl`: words and links

| Shape | Rule | Source |
|---|---|---|
| `WordShape` | required fields, datatypes, allowed `status` / `stubReason`, IRI `…/word/w_<16 hex>`, `runId` pattern | contract §5, §8 |
| `WordStatusShape` | `stubReason` is set iff `status = stub`; stub and ambiguous words have `etymNo 0` | contract §5 |
| `ReconstructionShape` | an `ety:Reconstruction` is an `ety:Word` whose form and key start with one `*` | ADR 0001 |
| `LinkShape` | required fields, datatypes, allowed values and ranges (`hop ≥ 0`, `confidence` in [0, 1], `evidenceCount ≥ 1`), IRI `…/link/l_<16 hex>`, no self-loops (`sh:disjoint`) | contract §6, §8; ADR 0003 |
| `LinkKeywordShape` | `keyword` is absent for `syntax classic` and present for `syntax ety` | contract §6 |

### `enforced/link_consistency.ttl`: links

| Shape | Rule | Source |
|---|---|---|
| `LinkHasDirectTriplesShape` | every `ety:Link` has the direct triples `ety:derivedFrom` and `ety:<type>` between its source and target | ADR 0005 |
| `DirectTripleHasLinkShape` | every direct triple (`derivedFrom`, `inh`, `bor`, `der`, `calque`) has an `ety:Link` with the same type | ADR 0005 |
| `LinkResolutionShape` | `resolution` matches the target's `status`: `resolved*` → `entry`, `stub` → `stub`, `ambiguous` → `ambiguous` | contract §6 |

The first two matter for every path rule: paths follow the direct triples, while the
attributes sit on the link node, so the two must describe the same links.

### `enforced/inh_ancestor.ttl`: the ancestor rule

| Shape | Rule | Source |
|---|---|---|
| `InhTargetsAncestorShape` | the etymon of an `inh` link is in an ancestor language of the derived word's language, or a variety of one: path `hasAncestor/(hasAncestor\|variantOf)*` | ADR 0002, 0003 |

### `enforced/languages.ttl`: the languages graph

| Shape | Rule | Source |
|---|---|---|
| `LanguageShape` | required fields, allowed `wiktType` / `category`, code pattern `[a-z0-9-]+` | contract §2, §8; ADR 0005 |
| `LanguageIriShape` | the IRI is `…/lang/{code}` | ADR 0005 |
| `LanguageTypeShape` | `etymology-only` ⇔ category `etymology-only`, one `variantOf`, no family; `reconstructed` ⇔ `proto`; others are `modern` / `historical` without `variantOf` | ADR 0002, contract §2 |
| `AncestryAcyclicShape` | no language is its own ancestor (`hasAncestor+`) | ADR 0002 |
| `WordInFullLanguageShape` | words are filed under a full language, never an etymology-only one | ADR 0002, contract §5 |
| `FamilyShape` | IRI pattern, at most one parent family and proto-language | contract §4 |
| `ImportRunShape` | IRI `…/run/r_<12 hex>` | ADR 0006 |
| `RunIdKnownShape` | every `runId` names an existing `ety:ImportRun` | ADR 0006, 0007 |

### `warnings/no_cycles.ttl`

| Shape | Rule | Source |
|---|---|---|
| `NoCycleShape` | a link that is part of a derivation cycle (`derivedFrom*` back to its source). A warning: cycles are kept in the data on purpose | ADR 0003 |

The sample has one cycle (`de:Devise` ⇄ `fr:devise`), so `validate.py` always reports two
warnings on it.

## Running `validate.py`

From the repo root:

```powershell
uv run shapes/validate.py                     # the de-pl-mini sample
uv run shapes/validate.py data/export/nq      # a pipeline export
```

uv reads the dependencies from the script header; no virtual environment is needed. The
script merges all named graphs into one graph first (path rules need the word graphs and
`graph/languages` together), loads every `.ttl` under `shapes/`, and prints the report.
Exit code 0 means no violations (warnings allowed), 1 means at least one violation.

Expected result on the sample: `Conforms: True` with 2 warnings (the Devise cycle).

If uv fails with `invalid peer certificate: UnknownIssuer`, set
`$env:UV_NATIVE_TLS = "true"` (uses the Windows certificate store).

## GraphDB

### Start and create the repository

```powershell
cd shapes
docker compose up -d
```

Workbench: <http://localhost:7200>. Create a repository once under **Setup → Repositories →
Create new → GraphDB Repository**:

- ID `etymograph`
- Ruleset **No inference** (the export writes every triple explicitly, ADR 0005)
- **Enable SHACL validation** ticked (can only be set at creation)

### Load data, then shapes

Order matters: once shapes are loaded, data that breaks them is rejected.

1. **Data:** Import → Upload RDF files → all files in `samples/de-pl-mini/nq/` (or an
   export), Target graphs **From data**. Or from the repo root:

   ```powershell
   Get-ChildItem samples\de-pl-mini\nq\*.nq | ForEach-Object {
     curl.exe -s -w "%{http_code}`n" -X POST -H "Content-Type: application/n-quads" `
       --data-binary "@$($_.FullName)" `
       http://localhost:7200/repositories/etymograph/statements
   }
   ```

2. **Shapes:** Import → Upload RDF files → `prefixes.ttl` and every file in `enforced/`,
   Target graphs **Named graph** `http://rdf4j.org/schema/rdf4j#SHACLShapeGraph`. Do **not**
   load `warnings/`. The upload validates the existing data; it succeeds if the data conforms.

To change a shape, clear the shapes graph and load all shape files again. Re-uploading one
file adds its triples a second time instead of replacing them.

```sparql
CLEAR GRAPH <http://rdf4j.org/schema/rdf4j#SHACLShapeGraph>
```

### Check that a shape is enforced

The shapes graph cannot be read with a normal query, so test a shape by trying to break
it. A rejected update is rolled back. Example (`LinkShape`, allowed link types):

```sparql
PREFIX ety: <https://matilang.github.io/Etymograph/ns/ety#>
DELETE { GRAPH ?g { ?link ety:linkType "bor" } }
INSERT { GRAPH ?g { ?link ety:linkType "loan" } }
WHERE {
  { SELECT ?link WHERE { ?link a ety:Link ; ety:linkType "bor" } LIMIT 1 }
  GRAPH ?g { ?link ety:linkType "bor" }
}
```

Expected: "Failed SHACL validation" with `sh:InConstraintComponent`. In SPARQL, IRIs with
`/` after the prefix must be written in full (`<https://…/id/lang/de>`, not `etyd:lang/de`).

## GraphDB limits

Found while testing the shapes in GraphDB 11.5.1. They are why `validate.py`, not GraphDB,
is the complete check.

| Limit | Consequence | What the shapes do |
|---|---|---|
| **Any result rejects the transaction, even `sh:Warning`** | a warning shape would block loading | warning shapes live in `warnings/` and run in `validate.py` only |
| **`sh:xone` is silently ignored** | the shape loads, but the rule is never checked | `sh:or` is used instead; the alternatives exclude each other, so the meaning is the same |
| **A SPARQL rule is re-checked only for new targets** | changing an existing node (for example adding `hasAncestor` to an existing language) does not re-run a `sh:targetClass` rule | `AncestryAcyclicShape` targets `sh:targetSubjectsOf ety:hasAncestor`, so the triple that could create a cycle triggers it. Other rules can still miss edits of existing nodes; loading new data is always checked |
| **The shapes graph is not readable with SELECT** | a query cannot show which shapes are loaded | test with a deliberate break (above) |

SHACL itself (not GraphDB) also forbids `VALUES` in SPARQL constraints; use `FILTER (?x IN (…))`
or `UNION`.

## Adding a shape

1. Decide: hard rule → `enforced/`, soft rule → `warnings/`.
2. Write it with the file's `@prefix` lines; SPARQL rules use `sh:prefixes etys:`. A SPARQL
   rule returns **one row per violation**.
3. `uv run shapes/validate.py`: the sample must still give `Conforms: True`.
4. Break a copy of the data on purpose and check that the new shape catches it (and only it).
5. For `enforced/`: reload the shapes graph in GraphDB and repeat the break as an update
   (above). Avoid `sh:xone`; for a SPARQL rule, target the triple that can break it.

## Open points

- **Contract (Eldar):** `ety:Family` has no `code` / `name` in the RDF, and `ety:ImportRun`
  has none of the `import_runs` columns (contract §7, §8). If they are added, `FamilyShape` and
  `ImportRunShape` get `minCount` rules.
- **Contract (Eldar):** the rules do not need `language_ancestors.source` or `ordinal` in the
  RDF (the open TODO in contract §8).
- **Pending phase 2:** whether `REVERSED_LANG_LOAN` / `REVERSED_LANG_DER` stay warnings, once
  the data-quality report shows how many are errors.
- **Not yet written:** a warning for weak `der` links (ADR 0003).
- **Not yet measured:** validation time on the full export (about 5 M quads).
