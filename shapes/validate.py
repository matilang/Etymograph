# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyshacl>=0.29,<1",
# ]
# ///


"""Validate N-Quads exports against all shapes in shapes/ with pySHACL.

Usage: uv run shapes/validate.py [NQ_DIR]
Default NQ_DIR: samples/de-pl-mini/nq
"""

import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Dataset, Graph

SHAPES_DIR = Path(__file__).resolve().parent
REPO_ROOT = SHAPES_DIR.parent
nq_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "samples/de-pl-mini/nq"

nq_files = sorted(nq_dir.glob("*.nq"))
if not nq_files:
    sys.exit(f"No .nq files in {nq_dir}")

# Merge all named graphs into one graph: rules such as inh_ancestor need the
# word graphs and graph/languages together, and pySHACL would otherwise
# validate each named graph on its own.
dataset = Dataset()
for f in nq_files:
    dataset.parse(f, format="nquads")
    
data = Graph()
for s, p, o, _ in dataset.quads((None, None, None, None)):
    data.add((s, p, o))

shapes = Graph()
for f in sorted(SHAPES_DIR.rglob("*.ttl")):
    try:
        shapes.parse(f, format="turtle")
    except Exception as e:
        sys.exit(f"Cannot parse {f.relative_to(REPO_ROOT)}: {e}")

conforms, _, report_text = validate(
    data,
    shacl_graph=shapes,
    allow_warnings=True,  # warnings are reported but do not fail the run
)
print(report_text)
sys.exit(0 if conforms else 1)
