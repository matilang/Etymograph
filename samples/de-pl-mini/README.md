# de-pl-mini: a hand-picked sample in data contract v1

57 real words and 49 links picked from the kaikki files (dump 2026-10-01, extracted 2026-10-30),
written exactly in the format of [data contract v1](../../docs/data_contract.md). Role 2 and Role 3
can use it to write shapes and queries before the pipeline exists. It is static: it is not produced
by pipeline code, and it does not change when the pipeline does.

## Files

| File | Content |
|---|---|
| `languages.csv`, `language_ancestors.csv`, `families.csv` | 26 languages, 25 direct ancestor edges, 19 families (contract §2–4) |
| `words.csv`, `links.csv` | 57 words, 49 links (contract §5–6) |
| `import_runs.csv` | one run row (contract §7) |
| `nq/{code}.nq`, `nq/languages.nq` | N-Quads: one named graph per language file, plus `graph/languages` ([ADR 0005](../../docs/adr/0005-rdf-export-layout.md)) |
| `load.cypher`, `docker-compose.yml` | Neo4j 5.26 Community + APOC, model of [ADR 0004](../../docs/adr/0004-neo4j-physical-model.md) |

## What is in it

| Case | Words |
|---|---|
| Common ancestor across the two families | `de:Ziegel` and `pl:cegła` meet at `gmh:ziegel` and continue to `la:tēgula` (key `tegula`) and `ine-pro:*(s)teg-` |
| Common ancestor via an Old Polish loan | `de:Küche` and `pl:kuchnia` meet at `goh:chuhhina` |
| Full chain to Proto-Indo-European | `de:Herz` → `gmh:hërze` → `goh:hërza` → `gmw-pro:*hertā` → `gem-pro:*hertô` → `ine-pro:*ḱérd` (stub) |
| Chain that stops early | `pl:serce` → `zlw-opl:serce` → `sla-pro:*sь̑rdьce`. The next step is the affix `*sьrdь + *-ьce` (`{{ety\|:af}}`), reserved for `COMPOSED_OF` and not loaded in v1, so **Herz and serce have no common ancestor here** |
| Homographs | `de:Bank` 1 "bench" (→ Old High German) and 2 "bank" (→ French, Italian); `de:Mangel` 1 and 2 |
| French loan in both languages | `de:Adresse` and `pl:adres` → `fr:adresse`; also `pl:biżuteria` → `fr:bijouterie` (German has no `Bijouterie` entry) |
| Direct loans de → pl | `pl:kreda` ← `de:Kreide`, `pl:gwint` ← `de:Gewinde`, `pl:magiel` ← `de:Mangel` |
| Ambiguous target | `pl:magiel` → `de:Mangel` (etym_no 0, `status = ambiguous`): the template does not say which of the two homographs. Also the classic template in `de:Adresse` / `pl:adres` → `fr:adresse` (0) |
| Stubs | `no_entry`, for example `gmh:ziegel`, `ine-pro:*ḱérd`; `no_file`, for example `it:banco`, `frm:banque`, `grc:τάγηνον` |
| Parallel links (`inh` + `der`) | `de:Kreide` → `gmh:krīde`, `gmh:krīde` → `goh:krīda`, `fr:banque` → `frm:banque` (`has_parallel = true`) |
| Cycle | `de:Devise` → `fr:devise` (`bor`), `fr:devise` → `de:Devise` (`calque`, semantic loan) |

Notes:

- Links are the links between the picked words after the ADR 0006 graph rules and the ADR 0003
  merge. Words outside the pick are left out, so a path can end where the real graph continues.
- The run used the phase 1 file set (`import_runs.ancestor_files`), so Old and Middle French and
  Ancient Greek targets are `no_file` stubs. `pipeline_commit` is the `develop` commit the sample
  was made on, and `pipeline_dirty = true` because no pipeline code produced it.
- `languages.category` follows the ADR 0002 heuristic, which is still `TODO(verify)`: French and
  German count as `historical` because creoles and pidgins list them as ancestors (for example
  Seychellois Creole → `fr`, Unserdeutsch → `de`), and Ancient Greek counts as `modern`.
- Families are not nodes in Neo4j (ADR 0004 keeps `family_code` on `Language`); they are in the
  CSV and the RDF.

## Neo4j

```bash
cd samples/de-pl-mini
docker compose up -d                 # Neo4j 5.26 Community + APOC, ports 7474 / 7687
docker compose exec neo4j cypher-shell -u neo4j -p etymograph-sample -f /import/load.cypher
```

Browser: <http://localhost:7474>, user `neo4j`, password `etymograph-sample`. Other ports or
password: set `SAMPLE_HTTP_PORT`, `SAMPLE_BOLT_PORT`, `SAMPLE_NEO4J_PASSWORD` before `up`.
Loading twice gives the same counts (84 nodes, 139 relationships). Stop with `docker compose down`.

Check: the common ancestors of Ziegel and cegła include `la:tēgula`. Use two `MATCH` clauses; the
one-pattern form `(x)-[*0..]->(c)<-[*0..]-(y)` returns 1 row instead of 7 here (ADR 0004).

```cypher
MATCH (x:Word {lang: 'de', key: 'Ziegel'})-[:DERIVED_FROM*0..]->(c:Word)
MATCH (y:Word {lang: 'pl', key: 'cegła'})-[:DERIVED_FROM*0..]->(c)
RETURN DISTINCT c.lang, c.form, c.key
```

## GraphDB

1. Create a repository (for example `etymograph`) with ruleset **No inference**: the export
   writes `ety:derivedFrom` explicitly, so nothing needs to be inferred (ADR 0005).
2. Import every file in `nq/`: Workbench → Import → Upload RDF files (the graph names come from the
   files), or with curl:

   ```bash
   for f in nq/*.nq; do
     curl -X POST -H 'Content-Type: application/n-quads' --data-binary @"$f" \
       http://localhost:7200/repositories/etymograph/statements
   done
   ```

3. Query a language graph together with `graph/languages`, for example
   `FROM <https://matilang.github.io/Etymograph/id/graph/de>` plus
   `FROM <https://matilang.github.io/Etymograph/id/graph/languages>`, or all graphs at once.
