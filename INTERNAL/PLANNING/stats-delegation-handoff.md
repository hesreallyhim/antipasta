# Stats Command Improvements - Delegation Handoff Document

## Quick Context Recovery

**Project**: Antipasta - A code quality enforcement tool
**Current Branch**: AFTER_RENAMING
**Working Directory**: `/Users/hesreallyhim/coding/projects/antipasta/`
**Main File**: `/src/antipasta/cli/stats.py`

## Situation Summary

The `antipasta stats` command has three improvements that need implementation:

1. **TICKET-STATS-001**: Add `--depth 0` for unlimited directory traversal
2. **TICKET-STATS-002**: Fix metric inclusion logic (LOC only default when no `-m` flags)
3. **TICKET-STATS-003**: Add `--path-style` option with three modes (relative, parent, full)

These tickets are fully documented in `/INTERNAL/PLANNING/stats-improvements-tickets.md` with:
- Exact line numbers and code locations
- Before/after code snippets
- Test commands with expected output
- All edge cases clarified

## Delegation Strategy

### Why Delegate
- All three tickets are independent and can be implemented in parallel
- Each ticket is self-contained with clear acceptance criteria
- Implementation details are fully specified with no ambiguity
- Test commands provided for validation

### Expected Outcomes
Each agent should:
1. Implement their assigned ticket completely
2. Test using the provided commands
3. Commit their changes with appropriate commit messages
4. Report completion status

### Important Notes
- Agents should implement tickets in the CURRENT branch (AFTER_RENAMING)
- No need to create new branches unless there are conflicts
- Each ticket modifies the same file (`stats.py`) but different sections
- Order of implementation: STATS-002 → STATS-001 → STATS-003 (if sequential needed)

## Task Tool Invocation Prompts

Copy these prompts exactly when invoking the Task tool for each agent:

### Prompt 1: TICKET-STATS-001 (Unlimited Depth)

```
subagent_type: independent-contributor-opus
description: Implement unlimited depth option for stats

prompt: |
  Please implement TICKET-STATS-001 from the documentation at /INTERNAL/PLANNING/stats-improvements-tickets.md

  ## Your Task
  Implement support for --depth 0 to mean "unlimited" directory traversal (capped at MAX_DEPTH=20).

  ## Key Requirements
  1. Add MAX_DEPTH = 20 constant after line 35
  2. Update --depth option help text to indicate "0=unlimited"
  3. Modify _collect_directory_stats to use effective_depth = MAX_DEPTH if depth == 0 else depth
  4. Replace all occurrences of depth with effective_depth in the function

  ## File to Modify
  /src/antipasta/cli/stats.py

  ## Validation
  After implementation, run these tests:
  - antipasta stats -d src --by-directory --depth 0 (should show all levels)
  - antipasta stats -d src --by-directory --depth 1 (should work as before)
  - antipasta stats -d src --by-directory --depth 2 (should work as before)

  ## Commit Message
  Use conventional commit format:
  feat: add unlimited depth option (--depth 0) for directory stats

  - Add MAX_DEPTH=20 constant for safety boundary
  - Support --depth 0 to traverse all directories
  - Maintain backward compatibility for depth 1, 2, 3, etc.

  Please implement this ticket completely, test it, and commit your changes.
```

### Prompt 2: TICKET-STATS-002 (Metric Inclusion Logic)

```
subagent_type: independent-contributor-opus
description: Fix metric inclusion logic

prompt: |
  Please implement TICKET-STATS-002 from the documentation at /INTERNAL/PLANNING/stats-improvements-tickets.md

  ## Your Task
  Fix the bug where LOC metrics are ALWAYS shown even when user requests other metrics via -m flags.

  ## Key Requirements
  1. LOC should only be the default when NO -m flags are provided
  2. When -m flags are provided, show ONLY requested metrics (no implicit LOC)
  3. Update stats command logic around line 210-211 to default to LOC only if no metrics specified
  4. Make LOC collection conditional in _collect_overall_stats, _collect_directory_stats, _collect_module_stats
  5. Update _display_table to handle missing LOC data gracefully

  ## File to Modify
  /src/antipasta/cli/stats.py

  ## Critical Validation
  After implementation, this MUST pass:
  antipasta stats -p "src/antipasta/cli/*.py" -m cyc | grep -i "loc"
  # Should return NOTHING (no LOC shown when only cyc requested)

  Also test:
  - antipasta stats -p "src/antipasta/cli/*.py" (should show LOC by default)
  - antipasta stats -p "src/antipasta/cli/*.py" -m loc (should show LOC explicitly)
  - antipasta stats -p "src/antipasta/cli/*.py" -m all (should include LOC)

  ## Commit Message
  Use conventional commit format:
  fix: only show LOC metrics when explicitly requested or no metrics specified

  - LOC metrics now only default when no -m flags provided
  - When -m flags specified, show only requested metrics
  - File/function counts always shown regardless

  Please implement this ticket completely, test it thoroughly, and commit your changes.
```

### Prompt 3: TICKET-STATS-003 (Path Display Styles)

```
subagent_type: independent-contributor-opus
description: Add path display styles

prompt: |
  Please implement TICKET-STATS-003 from the documentation at /INTERNAL/PLANNING/stats-improvements-tickets.md

  ## Your Task
  Add --path-style option with three modes: relative (default), parent, and full.

  ## Key Requirements
  1. Add --path-style CLI option with choices ["relative", "parent", "full"]
  2. "relative": current behavior with 30-char truncation from front
  3. "parent": show last 2 path components with 30-char truncation
  4. "full": complete path with NO truncation (may break column alignment)
  5. Update stats function signature to include path_style parameter
  6. Pass path_style to _collect_directory_stats when by_directory=True
  7. Implement path formatting logic in _collect_directory_stats around line 426-430
  8. Truncation only applies to relative/parent styles, NOT full

  ## File to Modify
  /src/antipasta/cli/stats.py

  ## Validation
  After implementation, test:
  - antipasta stats -d src/antipasta --by-directory --depth 2 (default relative style)
  - antipasta stats -d src/antipasta --by-directory --depth 2 --path-style parent
  - antipasta stats -d src/antipasta --by-directory --depth 3 --path-style full
  - Verify --by-module is NOT affected (no path_style parameter)

  ## Commit Message
  Use conventional commit format:
  feat: add --path-style option for directory display formatting

  - Add three styles: relative (default), parent, full
  - relative/parent truncate to 30 chars from front
  - full shows complete paths with no truncation
  - Improves readability for deep directory structures

  Please implement this ticket completely, test all three styles, and commit your changes.
```

## Recovery Instructions for New Claude Session

When starting a new session, follow these steps:

1. **Read this document first** to understand the context

2. **Review the tickets** (optional but recommended):
   ```
   Read /INTERNAL/PLANNING/stats-improvements-tickets.md
   ```

3. **Check current state**:
   ```bash
   git status
   git branch
   ```

4. **Invoke the agents in parallel** using the Task tool:
   - Copy each prompt from above
   - Invoke all three Task tools in a SINGLE message for parallel execution
   - Monitor for completion

5. **Verify implementations**:
   ```bash
   # After all agents complete, run validation tests
   antipasta stats -d src --by-directory --depth 0  # Test TICKET-001
   antipasta stats -p "src/antipasta/cli/*.py" -m cyc | grep -i "loc"  # Test TICKET-002 (should be empty)
   antipasta stats -d src/antipasta --by-directory --depth 2 --path-style full  # Test TICKET-003
   ```

6. **Handle any conflicts**:
   - If git conflicts arise, resolve them maintaining all three changes
   - Each ticket modifies different parts of stats.py, conflicts should be minimal

## Success Criteria

All three tickets are successfully implemented when:
1. `--depth 0` shows all directories up to 20 levels deep
2. `-m cyc` shows ONLY cyclomatic complexity, no LOC
3. `--path-style full` shows complete paths without truncation
4. All existing functionality remains intact (backward compatible)
5. All test commands produce expected output

## Contingency Notes

- If an agent reports low confidence or has questions, check `/INTERNAL/PLANNING/stats-improvements-tickets.md` for clarifications added
- If implementation fails, the agent should report specific error messages
- Tickets are independent - if one fails, others can still proceed
- Each ticket has been reviewed by agents with 9/10 confidence

---

*This handoff document prepared on: 2025-09-21*
*Tickets finalized with all clarifications in commit: ba343bc*