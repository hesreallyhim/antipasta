# Caching strategy for structural (whole-program) metrics

Design note, 2026-07-04. Owner's question: the content-addressed cache works
because per-file metrics are pure functions of file content — but what about
directory-wide metrics that are *not* per-file aggregates: Module Tree Shape
(layered architecture, bounded fan-out), import layering, dependency cycles?
Their inputs cross file boundaries, and some inputs (file *names*, directory
*existence*, a module's *location*) live in no file's content at all.

## The strategy: split extract from derive

Every structural metric decomposes into two stages with wildly different costs:

1. **Extraction (per file, content-pure, expensive).** Parse one file and emit
   fact rows: its raw import statements, its statement count, its function
   fingerprints. This is a pure function of file content — so it rides the
   existing content-addressed cache **unchanged**, as just another row kind
   returned by `_collect_file_metrics`. A file edit invalidates exactly that
   file's facts.
2. **Derivation (whole-program, cheap, recomputed every run).** Assemble the
   cached facts plus the live directory tree into the structure — import
   graph, package fan-out counts — and derive the metric: strongly connected
   components for cycles, edge direction against layer order, children per
   package against the 5–7 band.

**Measured, not assumed** (probe: `tests/temp/structural_cache_probe.temp.py`):

| Corpus | Extraction (parse) | Derivation (assemble + SCC) | Ratio | Graph |
|---|--:|--:|--:|---|
| antipasta src (68 files) | 37 ms | 0.08 ms | ~450× | 79 edges, 0 cycles |
| bench corpus (167 files) | 341 ms | 0.32 ms | ~1,050× | 184 edges, **1 real cycle found** |

Derivation is three orders of magnitude cheaper than extraction and linear in
nodes + edges; even a 10,000-file monorepo derives in tens of milliseconds.
So the whole caching question collapses to what the substrate already does:
**cache extraction; recompute derivation.** A warm structural run costs the
cache reads plus ~a millisecond of graph work. (Bonus dogfood result: antipasta
itself has zero import cycles — it already passes its own future metric.)

## The correctness rule extraction must obey: strictly path-independent facts

Relative imports are the trap: `from . import x` resolves to different targets
depending on where the file *sits*. Resolution therefore belongs to the
derivation layer — extraction stores the raw statement (`.x`, with dot level),
never the resolved module. This is the same failure class as the complexipy
`file_name`-in-details leak the cache integration test caught: **anything
location-derived in a cached row poisons content-addressed hits** (two
identical files at different locations share one cache entry). Rule of thumb:
a fact row must be reproducible from the file's bytes alone, with the file's
location supplied fresh at derivation time.

## Structure-only changes (why derivation must not be cached naively)

A rename or move with unchanged content changes Module Tree Shape while
hitting every per-file cache — names and existence are not content. Because
derivation re-reads the live directory tree each run, it is always correct by
construction, and the tree walk costs only `os.scandir`. This is the second
reason "recompute the derivation" is the default: it makes the one input the
content cache cannot see (structure) always-fresh for free.

## Escape hatch: Merkle tree hash, for derivations that are genuinely expensive

Most derivations never earn a cache. The exception is quadratic-or-worse
whole-program work — pydry's near-match similarity (pairwise over function
fingerprints) is the concrete case on the roadmap. For those, memoize the
derivation result under a **Merkle-style tree hash**:

- file node = the layer-1 content hash (already computed for the fact cache);
- directory node = hash of its sorted child *names* + child hashes;
- a derivation over subtree X caches under X's tree hash.

Properties, all inherited from the construction: a content edit bubbles up and
invalidates exactly the derivations on its ancestor path (O(depth), not
O(tree)); renames/moves/adds/deletes change the hash even when contents are
identical (names are hashed); directory-scoped metrics (fan-out of package X,
cycles within X) get per-subtree granularity. Git's tree objects are exactly
this structure, so inside a clean git checkout the hashes could even be read
from the index instead of recomputed. For pairwise work there is also the
incremental form: re-compare only changed files' fingerprints against the
corpus — O(changed × total) instead of O(total²).

## Config stays out of the facts

Same discipline the violation layer already established: extraction is
judgment-free (a fact row doesn't know what "too many children" means), so
changing layer definitions, fan-out bands, or allowlists never invalidates the
fact cache. A memoized derivation folds its config into its own cache key;
un-memoized derivations (the default) just recompute under the new config.

## Summary

| Stage | Scope | Cost | Cache | Invalidated by |
|---|---|---|---|---|
| Extraction | per file | high (parse) | existing content-addressed store | that file's content edit, analyzer upgrade |
| Derivation | whole program / subtree | ~1000× lower | none (default) | n/a — recomputed |
| Expensive derivation | subtree | high (e.g. pairwise) | Merkle tree hash (opt-in) | any content/name change in the subtree |

Nothing new has to be built for Module Tree Shape, layering, or cycles beyond
emitting fact rows through the existing pipeline — the substrate landed for
priorities (i)/(ii) already carries the structural tier.
