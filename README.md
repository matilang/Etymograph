# Etymograph

## Contents

- [Project overview](#project-overview)
- [Team and roles](#team-and-roles)
- [Branch and commit conventions](#branch-and-commit-conventions)
- [Role 1: data pipeline (status)](#role-1-data-pipeline-status)
- [Getting started](#getting-started)
- [License](#license)

## Project overview

EtymoGraph is the team project for the TU Wien course "Management of Graph Data" (W2026). It builds
an etymology graph from Wiktionary data (via kaikki.org Wiktextract) to find and explain the
connections between words across languages. Neo4j is the primary data model. The same clean data is
also exported as RDF so that path-based SHACL rules can be run in GraphDB. The project covers the
electives C3 (schemas and constraints) and C5 (advanced querying). The MVP languages are German and
Polish, plus the ancestor languages they link to. Serbo-Croatian comes next, added with `add-lang`,
followed by French and Romanian.

## Team and roles

| Role | Owner | Responsibility | Main folders |
|------|-------|----------------|--------------|
| Role 1: Data Engineer | Eldar (@vikaloeldar) | Data pipeline, word identity, manifest, exports | `etymo/`, `docs/data_contract.md`, manifest, exports |
| Role 2: Graph Modeler | TBD | Schema, SHACL constraints, data quality, golden set | `shapes/`, schema, data quality, golden set |
| Role 3: Query & Analysis Lead | TBD | Queries, analysis, demo | `queries/`, analysis, `demo/` |

## Branch and commit conventions

**Branch model**

| Branch | Purpose |
|--------|---------|
| `main` | Verified milestone versions only, tagged `v0.1-plan`, `v0.5-mvp`, `v1.0-submission` |
| `develop` | Integration branch; must always pass `make test` (the Makefile is planned for phase 1) |
| working branches | One coherent step each, created from an up-to-date `develop` |

- Nobody commits directly to `main` or `develop`.
- Every change goes through a pull request into `develop` that at least one teammate reviews.
- Pull requests are squash-merged into `develop`.
- `main` is updated from `develop` only when a milestone is verified, and that version is tagged.

**Branch names:** `<owner>/<type>-<area>-<topic>`, lowercase, words joined with hyphens.

| Part | Meaning | Values |
|------|---------|--------|
| `owner` | The person working on the branch | First name or GitHub username |
| `type` | Kind of change | `feat`, `fix`, `docs`, `test`, `chore`, `refactor` |
| `area` | Part of the repo | `pipeline` (`etymo/`), `shapes`, `queries`, `docs`, `ci`, `demo` |
| `topic` | What the branch does | Two to four words |

Examples:

- `eldar/feat-pipeline-extract-identity`
- `eldar/docs-adr-data-contract`
- `<name>/feat-shapes-ancestor-rule`
- `<name>/feat-queries-common-ancestor`

Branches are short-lived. One branch covers one coherent step and is merged within days, not weeks.

**Commit messages:** [Conventional Commits](https://www.conventionalcommits.org/) with the area as
scope, in the imperative mood, one logical change per commit. Example:

```
feat(pipeline): resolve link targets by entry key
```

**Pull request description:** what changed and why, how it was tested, and a link to the ADR if a
decision changed.

**Ownership:** [`.github/CODEOWNERS`](.github/CODEOWNERS) maps folders to owners: `etymo/` and
`docs/data_contract.md` to Eldar (@vikaloeldar), `shapes/` to Role 2, `queries/` and `demo/` to Role 3. The Role 2
and Role 3 entries are placeholders until those owners are set.

**Never commit** `data/` or `.env`. See
[`.gitignore`](.gitignore).

## Role 1: data pipeline (status)

**Exists now:** repository conventions (this README, `.gitignore`, `.github/CODEOWNERS`). There is no
pipeline code yet.

**Planned:**

| Phase | Content |
|-------|---------|
| 0 | Architecture decision records (`docs/adr/`) and data contract v1 (`docs/data_contract.md`) |
| 1 | Repo skeleton; fetch with manifest; extraction of etymology links; word identity resolution; unit tests |
| 2 | Clean tables for German + Polish; data-quality report; determinism check; golden set |
| 3 | Neo4j loader; CSV + N-Quads export; `add-lang` dry run for Serbo-Croatian; CI workflow; setup docs |

**For teammates (planned, not yet available):**

- Data contract: `docs/data_contract.md` (exact table schemas and the RDF layout).
- Golden set: `tests/golden/` (German–Polish word pairs with expected paths).

## Getting started

To be completed in phase 3. Prerequisites:

- Docker
- [uv](https://docs.astral.sh/uv/)
- Python 3.12
- GraphDB Free licence

## License

MIT, see [LICENSE](LICENSE).
