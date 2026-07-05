"""The layered lexicon: context-aware vocabulary for name-clarity scoring.

Four layers, per docs/design/narrative-index.md:

1. A vendored English wordlist (``data/wordlist.txt.gz``, ~200k lowercase
   words derived from the public-domain web2 list shipped with macOS/BSD;
   offline, same posture as the vendored d3).
2. A curated programming-abbreviation list (``ctx``, ``cfg``, ``idx`` — the
   abbreviations reviewers accept without blinking).
3. The project's own anchor vocabulary — words harvested from module and
   class names ONLY. Anchors-only is the load-bearing restriction: harvesting
   from all identifiers would let junk self-whitelist ("fn" used forty times
   would become vocabulary). This is how "foo" is a good word inside a
   project named foo-measure and a junk word everywhere else.
4. A per-project allowlist from config, for domain terms the harvest misses.

A junk stop-list overrides everything — no lexicon layer can launder ``fn``.
"""

from __future__ import annotations

from functools import lru_cache
import gzip
import importlib.resources
import re

#: Abbreviations reviewers accept without expansion.
ABBREVIATIONS = frozenset(
    """
    abs arg args attr attrs auth avg bool buf calc char cls cmd cfg col
    cols config ctx db dec dest dict diff dir dirs doc docs elem env err
    exc expr fd fmt func gen html http https id idx info init int io iter
    json kw kwargs lang len lhs lib max md min mod msg num opt opts param
    params pct pos prev props pt qty rc re rec ref regex repo req res resp
    rhs sep seq src std str sql tok ts tz url utf uuid val vals var vars
    ver vm xml yaml
    """.split()  # noqa: SIM905 (wordset stays readable as prose)
)

#: Words no lexicon layer can launder.
JUNK_WORDS = frozenset(
    """
    fn obj tmp mgr hlpr impl stuff thing thingy proc chk foo bar baz quux
    asdf blah dummy junk misc2 xx xxx zz
    """.split()  # noqa: SIM905 (wordset stays readable as prose)
)

#: Verb heads that make a callable name read as an action or a question.
VERB_HEADS = frozenset(
    """
    add analyze apply build calc calculate call check classify clean clear
    close collect compare compute configure convert copy count create
    decode delete derive detect determine diff dispatch do dump emit encode
    ensure execute expand extract fetch filter finalize find fold format
    gather generate get group handle harvest infer init inject inspect
    install is iterate join keep list load log lookup make map mark match
    measure merge normalize open parse pick plot pop prepare print process
    produce prune publish pull push put read rebuild record refresh
    register release reload remove render repair replace report require
    reset resolve restore retry return roll rollup run save scan score
    select send set setup should show shut sort spawn split start stop
    store strip submit summarize swap sync tally test tokenize touch track
    transform translate trim try update upgrade validate verify visit walk
    warn wrap write has can was will
    """.split()  # noqa: SIM905 (wordset stays readable as prose)
)

_SPLIT_PATTERN = re.compile(r"[a-z]+|[A-Z][a-z]*|[0-9]+")


@lru_cache(maxsize=1)
def english_words() -> frozenset[str]:
    """The vendored wordlist (loaded once per process)."""
    resource = importlib.resources.files("antipasta") / "data" / "wordlist.txt.gz"
    with resource.open("rb") as handle:
        payload = gzip.decompress(handle.read()).decode()
    return frozenset(payload.split())


def split_identifier(identifier: str) -> list[str]:
    """snake_case and camelCase word parts, lowercased; digit runs dropped."""
    parts = []
    for chunk in identifier.split("_"):
        for match in _SPLIT_PATTERN.findall(chunk):
            if not match.isdigit():
                parts.append(match.lower())
    return parts


def harvest_anchors(module_names: list[str], class_names: list[str]) -> frozenset[str]:
    """Project vocabulary from anchor names only (see module docstring)."""
    anchors: set[str] = set()
    for module in module_names:
        for segment in module.split("."):
            anchors.update(split_identifier(segment))
    for class_name in class_names:
        anchors.update(split_identifier(class_name))
    return frozenset(anchors - JUNK_WORDS)


def score_identifier(
    identifier: str,
    vocabulary: frozenset[str],
    is_callable: bool = True,
) -> float:
    """0..1 clarity: lexicon hit rate, verb-head factor, junk penalty."""
    parts = split_identifier(identifier)
    if not parts:
        return 0.0
    hit_rate = sum(1 for part in parts if _hits(part, vocabulary)) / len(parts)
    junk_penalty = sum(1 for part in parts if part in JUNK_WORDS) / len(parts)
    verb_factor = 1.0 if (not is_callable or parts[0] in VERB_HEADS) else 0.7
    return max(0.0, hit_rate * verb_factor - junk_penalty)


def _hits(part: str, vocabulary: frozenset[str]) -> bool:
    """Direct hit or a naive-stem hit.

    The web2 base list is singular/uninflected, but identifiers are full of
    plurals and participles (users, entries, cached, building) — a few fixed
    stemming rules close the gap without a linguistics dependency.
    """
    if part in vocabulary:
        return True
    candidates = []
    if part.endswith("ies"):
        candidates.append(part[:-3] + "y")
    if part.endswith("es"):
        candidates.append(part[:-2])
    if part.endswith("s"):
        candidates.append(part[:-1])
    if part.endswith("ed"):
        candidates.extend((part[:-2], part[:-2] + "e", part[:-1]))
    if part.endswith("ing"):
        candidates.extend((part[:-3], part[:-3] + "e"))
    return any(candidate in vocabulary for candidate in candidates)


def full_vocabulary(anchors: frozenset[str], allowlist: list[str]) -> frozenset[str]:
    """All lexicon layers combined (junk stays junk regardless)."""
    return english_words() | ABBREVIATIONS | anchors | frozenset(word.lower() for word in allowlist)
