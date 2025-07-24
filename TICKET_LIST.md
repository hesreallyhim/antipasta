T-01 Define metrics-config schema
• Decide file format (YAML with .code_cop.yaml)
• Draft key hierarchy (defaults, languages[].metrics[])
• Add JSON-schema or Pydantic model for validation
• CLI helper code-cop-validate-config that exits non-zero on invalid file
• Generate example config with sane defaults (radon: CC<=10, etc.)
• Unit test: valid sample passes
• Unit test: missing field or bad comparison operator fails

⸻

T-02 Language detector helper
• Collect extension→language map (.py, .ipynb, .ts[x], .js[x])
• Integrate pathspec to respect .gitignore
• Implement detect_language(path) → enum|None
• Batch helper group_by_language(files)
• Unit test: mixed set returns correct languages
• Unit test: ignored path is skipped

⸻

T-03 Python metric runner (Radon)
• Add Radon to requirements.txt
• CLI wrapper calls radon cc -j, radon mi -j, radon hal -j, radon raw -j
• Parse JSON → MetricResult dataclass (metric, value)
• Handle Radon import/exec errors with helpful message
• Support running on multiple files with aggregation
• Unit test: simple file returns CC=1, MI≈100
• Unit test: wrapper raises on invalid JSON

⸻

T-04 Python cognitive runner (Complexipy)
• Add Complexipy to dependencies (optionally lazy-import)
• CLI wrapper complexipy --json <file>
• Parse JSON → per-function complexity list
• Compare against threshold from config
• Implement skip logic if metric disabled
• Unit test: file with deep nesting exceeds threshold → violation
• Unit test: absence of Complexipy when disabled → no crash

⸻

T-05 TS/JS metric runner (ts-complex)-
• Add ts-complex (npm) to dev dependencies
• Node/NPX wrapper callable from Python (subprocess)
• Parse JSON output for CC, MI, Halstead
• Dataclass for TSMetricResult
• Fallback to complexity-report if ts-complex missing
• Unit test: small TS sample returns CC ≤ 2
• Unit test: malformed JSON handled gracefully

⸻

T-06 Aggregator & decision engine
• Define unified Violation and FileReport models
• Load thresholds via T-01 helper
• For each file metric compare value vs comparison operator
• Collect violations across files & languages
• Generate summary table (file, metric, value, limit)
• Exit codes: 0 = pass, 2 = block
• Unit test: all below thresholds → 0
• Unit test: one violation → 2, summary includes offending metric
• Unit test: multiple languages aggregated correctly

⸻

T-07 Pre-commit wrapper script
• CLI entry code-cop with --files argument
• If run under pre-commit, read $ARGS else run git diff --staged --name-only
• Detect language (T-02) per file
• Call corresponding runner (T-03/04/05) and collect results
• Feed into aggregator (T-06)
• Pretty-print summary, honour --quiet
• Return aggregator exit code
• Integration test: set up temporary git repo, commit bad file, hook blocks
• Package script in setup.py / pyproject.toml as console-script

⸻

T-08 Docs & samples
• Expand README “Getting started”
• Provide copy-paste .pre-commit-config.yaml
• Document each metric, default limits and how to override
• Add troubleshooting section (missing Node, Radon etc.)
• Include example output screenshots/asciicast
• Update CHANGELOG with initial release notes
• Verify docs build passes (e.g. mkdocs, if used)

⸻

T-09 CI integration workflow
• Create example_project/ with simple Python & TS files
• GitHub Action workflow: setup-python, setup-node, install deps
• Job pass: thresholds loose → CI success
• Job fail: copy file that violates CC → expect exit 2
• Upload summary artifact for inspection
• Add status badge to README
• Ensure workflow caches Node/Python deps for speed
