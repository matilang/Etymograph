// Load samples/de-pl-mini into Neo4j 5.26 + APOC, following ADR 0004.
// Run with cypher-shell (see README.md). Safe to run twice: every write is a MERGE.
// The real pipeline uses a Python loader; this file only serves the static sample.

// ---- 1. Constraints and indexes, before any data (ADR 0004)
CREATE CONSTRAINT word_id IF NOT EXISTS FOR (w:Word) REQUIRE w.id IS UNIQUE;
CREATE CONSTRAINT language_code IF NOT EXISTS FOR (l:Language) REQUIRE l.code IS UNIQUE;
CREATE CONSTRAINT import_run_id IF NOT EXISTS FOR (r:ImportRun) REQUIRE r.run_id IS UNIQUE;
CREATE CONSTRAINT derived_from_link_id IF NOT EXISTS
  FOR ()-[d:DERIVED_FROM]-() REQUIRE d.link_id IS UNIQUE;
CREATE INDEX word_lang IF NOT EXISTS FOR (w:Word) ON (w.lang);
CREATE INDEX word_lang_key IF NOT EXISTS FOR (w:Word) ON (w.lang, w.key);
CREATE INDEX word_lang_form IF NOT EXISTS FOR (w:Word) ON (w.lang, w.form);
CREATE INDEX derived_from_type IF NOT EXISTS FOR ()-[d:DERIVED_FROM]-() ON (d.type);
CALL db.awaitIndexes();

// ---- 2. Languages. Empty CSV fields arrive as null; list columns are JSON arrays.
LOAD CSV WITH HEADERS FROM 'file:///languages.csv' AS row
MERGE (l:Language {code: row.code})
SET l.name = row.name,
    l.wikt_type = row.wikt_type,
    l.category = row.category,
    l.family_code = row.family_code,
    l.parent_code = row.parent_code,
    l.full_code = row.full_code,
    l.scripts = CASE WHEN row.scripts IS NULL THEN null ELSE apoc.convert.fromJsonList(row.scripts) END,
    l.wikidata_qid = row.wikidata_qid,
    l.has_strip_rule = (row.has_strip_rule = 'true'),
    l.last_run_id = row.run_id;

// ---- 3. Language ancestry and varieties
LOAD CSV WITH HEADERS FROM 'file:///language_ancestors.csv' AS row
MATCH (l:Language {code: row.lang_code})
MATCH (a:Language {code: row.ancestor_code})
MERGE (l)-[h:HAS_ANCESTOR]->(a)
SET h.source = row.source, h.ordinal = toInteger(row.ordinal);

MATCH (l:Language) WHERE l.parent_code IS NOT NULL
MATCH (p:Language {code: l.parent_code})
MERGE (l)-[:VARIANT_OF]->(p);

// ---- 4. Words, the Reconstruction label and IN_LANGUAGE
LOAD CSV WITH HEADERS FROM 'file:///words.csv' AS row
MERGE (w:Word {id: row.word_id})
ON CREATE SET w.first_run_id = row.run_id
SET w.lang = row.lang,
    w.key = row.key,
    w.etym_no = toInteger(row.etym_no),
    w.form = row.form,
    w.is_reconstruction = (row.is_reconstruction = 'true'),
    w.status = row.status,
    w.stub_reason = row.stub_reason,
    w.pos = CASE WHEN row.pos IS NULL THEN null ELSE apoc.convert.fromJsonList(row.pos) END,
    w.ety_ids = CASE WHEN row.ety_ids IS NULL THEN null ELSE apoc.convert.fromJsonList(row.ety_ids) END,
    w.gloss = row.gloss,
    w.source_file = row.source_file,
    w.last_run_id = row.run_id
// A label cannot be set from a value in plain Cypher; FOREACH over a 0- or 1-element list does it.
FOREACH (_ IN CASE WHEN row.is_reconstruction = 'true' THEN [1] ELSE [] END | SET w:Reconstruction)
WITH w
MATCH (l:Language {code: w.lang})
MERGE (w)-[:IN_LANGUAGE]->(l);

// ---- 5. Links: derived word -[:DERIVED_FROM]-> etymon (ADR 0003)
LOAD CSV WITH HEADERS FROM 'file:///links.csv' AS row
MATCH (a:Word {id: row.src_word_id})
MATCH (b:Word {id: row.dst_word_id})
MERGE (a)-[d:DERIVED_FROM {link_id: row.link_id}]->(b)
SET d.type = row.type,
    d.source_entry = row.source_entry,
    d.template = row.template,
    d.keyword = row.keyword,
    d.syntax = row.syntax,
    d.target_lang_raw = row.target_lang_raw,
    d.target_form = row.target_form,
    d.target_sense_id = row.target_sense_id,
    d.extraction = row.extraction,
    d.hop = toInteger(row.hop),
    d.confidence = toFloat(row.confidence),
    d.resolution = row.resolution,
    d.evidence_count = toInteger(row.evidence_count),
    d.has_parallel = (row.has_parallel = 'true'),
    d.last_run_id = row.run_id;

// ---- 6. Import run (provenance)
LOAD CSV WITH HEADERS FROM 'file:///import_runs.csv' AS row
MERGE (r:ImportRun {run_id: row.run_id})
ON CREATE SET r.loaded_at = datetime()
SET r.contract_version = row.contract_version,
    r.pipeline_commit = row.pipeline_commit,
    r.pipeline_dirty = (row.pipeline_dirty = 'true'),
    r.config_sha256 = row.config_sha256,
    r.target_languages = apoc.convert.fromJsonList(row.target_languages),
    r.ancestor_files = apoc.convert.fromJsonList(row.ancestor_files),
    r.manifest_sha256 = row.manifest_sha256,
    r.dump_date = row.dump_date,
    r.wiktextract_version = row.wiktextract_version,
    r.n_languages = toInteger(row.n_languages),
    r.n_words = toInteger(row.n_words),
    r.n_links = toInteger(row.n_links);
