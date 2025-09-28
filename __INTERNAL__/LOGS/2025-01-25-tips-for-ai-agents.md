# Tips for AI Agents Working on Software Projects

**Date**: January 25, 2025
**Context**: Lessons learned from successful debugging and development work

## 🎯 Key Principles for Success

### 1. **Understand Before Acting**
- Always read existing code before modifying it
- Check for patterns in neighboring files
- Look for existing tests to understand expected behavior
- Read the CLAUDE.md and project documentation first

### 2. **Systematic Debugging**
```
Problem → Reproduce → Isolate → Fix → Verify
```
- Create minimal reproduction cases
- Use debug scripts to isolate issues
- Test fixes in isolation before applying broadly
- Always verify the fix actually works

### 3. **Use Tools Effectively**

#### Search First, Edit Later
```bash
# Bad approach
Edit file blindly based on assumption

# Good approach
1. Grep for usage patterns
2. Read the full file context
3. Check related files
4. Then edit with confidence
```

#### Batch Operations
- Run multiple searches in parallel
- Use Task tool for complex investigations
- Group related tool calls in single messages

### 4. **Documentation as You Go**
- Create detailed logs for complex issues
- Document decisions and rationale
- Leave breadcrumbs for future developers
- Convert debug scripts to tests instead of deleting

### 5. **Test Continuously**
```bash
# After every significant change:
1. Run the specific test that was failing
2. Run the test suite
3. Check for side effects
4. Verify no new files were created (like .coverage.*)
```

## 🛠️ Practical Techniques

### Finding Root Causes
1. **Start with the error message** - Read it carefully
2. **Trace backwards** - From error to source
3. **Question assumptions** - "Is this path what I think it is?"
4. **Create minimal tests** - Isolate the specific issue
5. **Check environment differences** - CI vs local, temp dirs, etc.

### Working with Subprocess Issues
```python
# Always consider environment inheritance
env = os.environ.copy()
env['COVERAGE_CORE'] = ''  # Disable coverage in subprocess

# Use explicit paths
result = subprocess.run([sys.executable, "-m", "module"], ...)
```

### Path Handling Gotchas
- Temporary test files may have unexpected paths
- Use `.relative_to()` carefully - it throws ValueError
- Always handle both absolute and relative paths
- Test with files outside the project directory

### Configuration Complexity
- Test with minimal config first
- Add complexity incrementally
- Document each configuration's purpose
- Provide sensible defaults

## 📋 Process Tips

### 1. **Use TodoWrite Proactively**
- Break complex tasks into steps immediately
- Mark items in_progress BEFORE starting
- Update status in real-time
- Only mark completed when truly done

### 2. **Commit Messages Matter**
- Use conventional commit format
- Explain the "why" not just "what"
- Reference related issues
- Include breaking changes

### 3. **Ask Clarifying Questions**
Instead of assuming:
- "Should I fix X while I'm here?"
- "Which approach would you prefer?"
- "Is this the expected behavior?"

### 4. **Performance Considerations**
- Avoid subprocess calls in tight loops
- Cache expensive operations
- Mock external dependencies in tests
- Consider --parallel flags for tools

## 🚨 Red Flags to Watch For

1. **Tests that pass locally but fail in CI**
   - Check for hardcoded paths
   - Look for timing dependencies
   - Verify environment variables

2. **Mysterious file generation**
   - Check subprocess environment inheritance
   - Look for tools running in parallel mode
   - Verify cleanup in test fixtures

3. **Import errors that "shouldn't happen"**
   - Check for circular imports
   - Verify import order
   - Look for conditional imports

4. **Pattern matching surprises**
   - Understand glob vs regex differences
   - Test with edge cases
   - Consider path normalization

## 💡 Meta-Tips for AI Agents

### Stay Focused
- Complete current task before starting new ones
- Resist scope creep
- Flag issues for later rather than fixing everything

### Communicate Clearly
- Show your reasoning for complex decisions
- Highlight uncertainty when present
- Summarize long outputs
- Use examples to clarify

### Build Trust
- Admit when you're unsure
- Test your changes
- Document your work
- Follow project conventions

### Learn from Patterns
- Similar issues often have similar solutions
- Build mental models of the codebase
- Recognize common debugging patterns
- Apply lessons across projects

## 🎁 Bonus: Debugging Checklist

- [ ] Can I reproduce the issue?
- [ ] Do I understand the expected behavior?
- [ ] Have I isolated the root cause?
- [ ] Does my fix address the cause, not symptoms?
- [ ] Have I tested the fix?
- [ ] Will this break anything else?
- [ ] Is there a simpler solution?
- [ ] Should this be documented?

## Summary

Success in software projects comes from:
1. **Systematic investigation** over rushed fixes
2. **Clear documentation** over clever solutions
3. **Comprehensive testing** over assumptions
4. **Incremental progress** over big bangs
5. **Communication** over isolation

Remember: Every confusing bug is an opportunity to improve the codebase's clarity for the next developer (human or AI).