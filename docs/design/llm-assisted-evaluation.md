# LLM-assisted evaluation — the blind reading test (opt-in mode)

Design note, 2026-07-04. Owner's proposal: an optional mode where a
lightweight model acts as a classifier for the newspaper/Narrative Index
readability property — "read this function and tell me what it does,
*without* giving it any of the helper functions — can you read this
function, basically?" — plus a confidence level.

Verdict: adopt as a design, as an **opt-in, advisory** subsystem. The hiding
of helpers is the key move and is kept exactly as proposed; the confidence
level is upgraded (below) because self-reported LLM confidence is the least
reliable signal a model produces.

## Why this patches the static metric's declared blind spot

The Narrative Index design is honest that it measures *conformance to
structure* and is gameable: name garbage `fetch_users` and narration ratio
passes. Semantic accuracy — does the name tell the truth — was declared not
statically decidable. A reading test measures the *effect* instead of the
structure: prose-style code is precisely code whose meaning survives with the
callee implementations hidden. That is a behavioral definition, and a language
model is the first affordable instrument that can administer it at scale.

## Scoring: blind vs informed agreement (not self-reported confidence)

Three tiers, cheapest to most rigorous:

1. **Classifier** (owner's baseline): one call — body only, helpers hidden —
   "state what this function does; rate your confidence." Cheapest; useful as
   a coarse first pass; confidence is self-reported and miscalibrated.
2. **Blind/informed agreement (the recommended design).** Two readings and a
   judgment, requiring no human ground truth:
   - *Blind pass*: the model sees ONLY the function body (signature + body,
     callee implementations hidden) and writes a one-paragraph summary of
     what the function does.
   - *Informed pass*: the model sees the function WITH its callees'
     implementations (one level down suffices) and writes the same summary.
   - *Judge pass*: a third call compares the two summaries — "do these
     describe materially the same behavior? list discrepancies."
   Agreement means the names told the truth: the local text was sufficient.
   Disagreement is the finding — either the names lie (blind reader was
   misled) or behavior hides below the abstraction. This catches exactly the
   static metric's gameable case: garbage logic named `fetch_users` reads
   "fetches users" blind and "deletes stale records" informed → flagged.
3. **Comprehension quiz**: generate questions from the informed context,
   answer them blind, grade. Most rigorous, most calls; reserve for audits.

Complementary cheap probes sharing the machinery:
- **Leaf naming test**: show a leaf's implementation with the name masked;
  ask the model to name it; compare (judge or embedding similarity) to the
  real name. Grades leaf name accuracy — the inverse of the blind test.
- **Calibration loop**: cross static score × blind-reading outcome. High
  static + failed reading = lying names. Low static + passed reading = the
  strictness profile may be tuned too hard. The LLM mode thereby calibrates
  the static thresholds instead of competing with them.

## Worked example (the probe's own samples)

Blind reader on the prose sample: `should_accept_new_users` — "decides
whether new users can be accepted, by fetching users, keeping active ones,
and checking capacity" — correct, names carried everything. Blind reader on
the junk-named twin (`check2`, `do_stuff`, `proc`, `chk`): the honest summary
is "returns the negation of some check on processed input — domain meaning
undeterminable," and the informed pass differs materially → flagged, which is
the correct verdict the static composite could only reach via the name floor.

## Architecture fit

- **Opt-in, never default**: a config block (provider, model, scope) plus an
  explicit flag. The HTML report stays fully offline; LLM calls happen at
  analysis time only, and results ride the snapshot like any metric.
- **Advisory, never gating (by default)**: rows carry
  `details: {"advisory": true, "model": ..., "prompt_version": ...}`.
  Nondeterministic judges must not flip CI exit codes; a team that wants
  gating opts in per-metric like any threshold.
- **The cache is what makes it affordable.** Key = content hash of the
  function body (+ callee bodies for the informed pass) + model id + prompt
  version — the existing content-addressed store, unchanged. Warm runs cost
  zero calls; a typical edit re-evaluates only the touched functions.
  Cold-run scope controls: narrators only (the classification from the
  Narrative Index tells us which), functions over N steps, or changed-only.
- **Cost envelope**: ~300–600 tokens per function per pass with a
  haiku-class model; a 1,000-function repo cold ≈ low single-digit dollars,
  warm ≈ pennies. The informed pass doubles it; run tier 2 on demand and the
  tier-1 classifier in routine runs if cost matters.
- **Privacy**: code leaves the machine only under explicit opt-in; provider
  abstraction must admit local models (an ollama-class endpoint) as a
  first-class target, not an afterthought.

## Honesty section

- The judge can be lenient; prompt it to enumerate behavioral discrepancies,
  not vibes. Pin model + prompt version in the fingerprint so scores are
  comparable across runs, and record both in the snapshot.
- Blind/informed agreement validates *truthfulness of names*, not *quality
  of decomposition* — a truthful 25-step run-on still reads fine blind. The
  static budgets keep owning structure; the LLM mode owns semantics. Neither
  replaces the other, and the report must not average them together.
- This is the first antipasta metric whose result is not a pure function of
  file content (model weights are an input). Advisory labeling and the
  fingerprint discipline are what keep that honest.

## Where it slots in the adoption plan

Independent track C in `metrics-adoption-plan.md`: needs Phase 0 (fact rows,
config profiles) and benefits from Phase 4's classification (to scope calls
to narrators), but has no other dependency. Tier 1 could ship as an
experiment alongside Phase 1's house metrics.
