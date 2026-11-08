# ADR 0005: RDF export layout for Role 2

Status: Proposed

## Context

Role 2 runs path-based SHACL-SPARQL rules (for example "an `inh` link must point to an ancestor
language", no cycles) in GraphDB, because Neo4j's SHACL add-on (n10s) does not document
`sh:sparql`. The probe confirmed that GraphDB 11.5 runs SPARQL-based constraints with a `+` path
inside the query, returning the same focus nodes as pySHACL, about 25× faster (2.9 s vs 77.7 s for
one rule on the Serbo-Croatian graph). The RDF must carry the same clean data as Neo4j, and the
link attributes must be reachable by SHACL.

## Options

- **IRIs:** readable (`…/word/de/Bank/1`) vs opaque hash ids. Readable IRIs need percent-encoding of
  arbitrary Unicode keys (spaces, `*`, `/`, `<`), and still change if a key rule changes. Opaque ids
  are stable and safe. **Opaque ids from the word id, plus readable literals.**
- **Link attributes:** RDF-star (`<< s p o >> ety:hop 1`) vs reified link nodes vs direct triples
  only. RDF-star support in GraphDB/pySHACL property paths is uneven; direct triples alone lose the
  attributes. **Direct triple + reified node**, as in the probe.
- **Graphs:** one default graph vs one named graph per language file. Per-file graphs let Role 2
  validate a language alone, and give named-graph provenance. **Named graphs.**

## Decision

### Namespaces

| Prefix | IRI | Use |
|---|---|---|
| `ety:` | `https://matilang.github.io/Etymograph/ns/ety#` | vocabulary (classes, properties) |
| `etyd:` | `https://matilang.github.io/Etymograph/id/` | data (words, links, languages, runs, graphs) |

- The base is under the repository owner's GitHub Pages domain so it is ours and stable; it does not
  need to resolve. **Decided (2026-11-08):** this base IRI is final, so Role 2 can write shapes
  against it.

### IRIs

| Thing | IRI | Example |
|---|---|---|
| Word | `etyd:word/{word_id}` | `etyd:word/w_3f2a9c0d1e4b5a67` |
| Link | `etyd:link/{link_id}` | `etyd:link/l_9b1e…` |
| Language | `etyd:lang/{code}` | `etyd:lang/la-vul` |
| Family | `etyd:family/{code}` | `etyd:family/zlw-lch` |
| Import run | `etyd:run/{run_id}` | `etyd:run/r_…` |
| Language-file graph | `etyd:graph/{code}` | `etyd:graph/de`, `etyd:graph/zlw-opl` |
| Languages graph | `etyd:graph/languages` | |

- Word and link ids are the hashes from ADR 0006, so IRIs are stable across runs and contain only
  `[a-z0-9_]`. Language codes are `[a-z0-9-]` in the data (`TODO(verify)` in phase 1 over all codes;
  anything else is percent-encoded).
- Literals are plain `xsd:string` without language tags: Wiktionary codes such as `ine-pro` or
  `la-vul` are not reliable BCP 47 tags.

### Graph contents

- **`etyd:graph/{code}`, one per language file** loaded (`de`, `pl`, and each ancestor file such as
  `la`, `zlw-opl`, `gem-pro`): every link whose `source_entry` comes from that file, and the full
  description of **every word that such a link touches** (both endpoints). A word can therefore be
  described in several graphs; RDF set semantics make the union consistent. Words of a file that
  have no link are also described in its graph.
- **`etyd:graph/languages`**: all `Language` resources, their direct ancestors, varieties and
  families, and the `ImportRun` resource(s). Role 2 queries a language graph together with this
  graph (`FROM etyd:graph/de FROM etyd:graph/languages`).
- No triples go into the default graph.

### Triples

Word:

```
etyd:word/w_… a ety:Word ;                    # plus ety:Reconstruction if is_reconstruction
    ety:form "tēgula" ; ety:key "tegula" ; ety:etymNo 0 ;
    ety:inLanguage etyd:lang/la ; ety:status "entry" ;
    ety:runId "r_…" .
```

Link, **both** forms:

```
# 1. direct triples, for property paths
etyd:word/w_SRC ety:derivedFrom etyd:word/w_DST .
etyd:word/w_SRC ety:inh         etyd:word/w_DST .      # or ety:bor / ety:der / ety:calque

# 2. reified link carrying the attributes
etyd:link/l_… a ety:Link ;
    ety:source etyd:word/w_SRC ; ety:target etyd:word/w_DST ;
    ety:linkType "inh" ; ety:sourceEntry etyd:word/w_… ;
    ety:template "inh+" ; ety:targetForm "*hertā" ; ety:targetLangRaw "gmw-pro" ;
    ety:extraction "chain" ; ety:hop 2 ; ety:confidence 0.6 ;
    ety:resolution "resolved" ; ety:evidenceCount 2 ; ety:runId "r_…" .
```

- `ety:inh`, `ety:bor`, `ety:der`, `ety:calque` are declared `rdfs:subPropertyOf ety:derivedFrom` in
  the vocabulary file; the export also writes the `ety:derivedFrom` triple explicitly so no
  inference is needed (GraphDB repository ruleset `empty`, as in the probe).
- Direction follows ADR 0003: subject = derived word, object = etymon. This reverses the probe's
  `ety:from`/`ety:to` convention.

Language (in `etyd:graph/languages`):

```
etyd:lang/la-vul a ety:Language ; ety:code "la-vul" ; ety:name "Vulgar Latin" ;
    ety:wiktType "etymology-only" ; ety:category "etymology-only" ;
    ety:variantOf etyd:lang/la-cla .
etyd:lang/pl ety:hasAncestor etyd:lang/zlw-mpl ; ety:family etyd:family/zlw-lch .
```

- Families are `ety:Family` resources under their own path `etyd:family/{code}`, so a family code
  can never clash with a language code.
- The full property list with datatypes is in the data contract; the vocabulary file
  (`ety.ttl`, phase 3) declares every class and property.

### Serialization

- **N-Quads**, one file per graph (`{code}.nq`, `languages.nq`), UTF-8, one quad per line, lines
  sorted in code-point order so the files are byte-identical for identical input (ADR 0006).
- The probe wrote Turtle per graph; N-Quads is chosen because it carries the graph name per line,
  can be concatenated and diffed, and loads into GraphDB with one request per file.

## Consequences

- SHACL rules can use property paths over `ety:derivedFrom` / `ety:inh` and still read every
  attribute from the `ety:Link` node.
- Link triples roughly double the quad count compared with direct triples only (probe L: 4.9 M quads,
  83 s GraphDB load). Acceptable at our size.
- Words repeated across graphs inflate the per-graph count; distinct-word counts must be taken over
  the union.

## Evidence

- Probe: same layout (direct + reified, one graph per file plus `graph/languages`) loaded into
  GraphDB 11.5.1 and queried; results matched PostgreSQL and Neo4j on all 108 query instances.
- Probe: GraphDB validation of S1–S3 in 2.9 s with the same focus nodes as pySHACL.

## Open questions

- `TODO(verify)`: language and family code character sets.
