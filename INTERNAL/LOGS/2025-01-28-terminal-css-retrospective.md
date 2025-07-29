# Terminal Dashboard CSS Issue - Retrospective

**Date**: 2025-01-28  
**Issue**: Terminal dashboard crash with CSS parsing error  
**Root Cause**: Phantom CSS rule injection causing parser failure  

## Issue Discovery

The user encountered an error when running:
```bash
code-cop metrics -f ./DEMOS/05_metrics_analyzer_cognitive.py --format terminal
```

The command failed with a CSS parsing error that referenced content not present in our codebase:
```
╭─ Error at /Users/hesreallyhim/coding/projects/cc-code-cop/code_cop/terminal/─╮
│   38 │   │   Screen.-maximized-view {                                        │
│   39 │   │   │   layout: vertical !important;                                │
│ ❱ 40 │   │   │   hatch: right $panel;                                        │
│   41 │   │   │   overflow-y: auto !important;                                │
│   42 │   │   │   align: center middle;                                       │
╰──────────────────────────────────────────────────────────────────────────────╯
   expected a percentage here; found '#2d2d2d'  
```

## Investigation Process

1. **Initial Verification**
   - Confirmed the target file existed
   - Reproduced the error with `python -m code_cop metrics`
   - Found that JSON format worked fine, isolating the issue to terminal format

2. **CSS File Analysis**
   - Examined `dashboard.tcss` at the reported line 40
   - Found line 40 was just a closing brace for `.heatmap` selector
   - No "Screen.-maximized-view" or "hatch" property existed in our CSS

3. **Codebase Search**
   - Searched entire codebase for the phantom CSS selector
   - Searched for "hatch" property references
   - Checked all .tcss and .css files
   - Examined Python files for dynamically generated CSS
   - Result: The problematic CSS existed nowhere in our codebase

4. **Isolation Testing**
   - Created minimal Textual app with our CSS file - reproduced error
   - Created minimal Textual app without CSS - worked fine
   - Confirmed issue was specific to our CSS file parsing

## Root Cause Analysis

The error message showed CSS content that didn't exist in our file:
- Selector: `Screen.-maximized-view`
- Property: `hatch: right $panel`
- Error: "expected a percentage here; found '#2d2d2d'"

The `#2d2d2d` value was from our CSS variable `$panel: #2d2d2d`. This suggests:

1. **Textual CSS Processing Issue**: Textual was somehow injecting or generating CSS that included the non-existent "hatch" property
2. **Variable Expansion Problem**: The `$panel` variable was being expanded to its value `#2d2d2d` in a context where a percentage was expected
3. **Parser State Corruption**: The CSS parser was reporting errors at the wrong line numbers, suggesting internal state issues

## The Fix

Removed the unused `$panel` CSS variable:
```diff
/* Define color variables */
$accent: #3498db;
$primary: #2ecc71;
$surface: #1e1e1e;
-$panel: #2d2d2d;
$text: #ffffff;
```

This immediately resolved the issue, suggesting the parser had problems with this specific variable name or its usage pattern.

## Relation to Mypy

This issue was **completely unrelated to mypy**. The CSS parsing error occurred at runtime within Textual's CSS engine, not during type checking. No mypy errors were involved in either the cause or the solution.

## Side Effects

The crash left the terminal in a bad state with mouse tracking enabled. This required manual terminal reset using:
```bash
reset
# or
printf '\033[?1000l\033[?1003l\033[?1015l\033[?1006l\033[?1049l'
```

## Concrete Proposals to Avoid This Problem

### 1. **CSS Validation in CI**
Add a test that loads and validates all CSS files:
```python
def test_css_files_valid():
    """Ensure all CSS files can be parsed without errors."""
    from textual.app import App
    from pathlib import Path

    css_files = Path("code_cop/terminal").glob("*.tcss")
    for css_file in css_files:
        app = App(css_path=str(css_file))
        # This will raise if CSS is invalid
        app._css_has_errors  # Force CSS parsing
```

### 2. **Graceful Terminal Cleanup**
Add proper exception handling to ensure terminal state is restored:
```python
class TerminalDashboard(App):
    def run(self, *args, **kwargs):
        try:
            super().run(*args, **kwargs)
        except Exception as e:
            # Ensure mouse tracking is disabled
            print('\033[?1000l\033[?1003l\033[?1015l\033[?1006l')
            raise
```

### 3. **CSS Variable Usage Guidelines**
- Document which CSS variable names are reserved or problematic
- Avoid variable names that might conflict with Textual internals
- Consider prefixing custom variables (e.g., `$cc-panel` instead of `$panel`)

### 4. **Error Reporting Enhancement**
Improve error messages to show actual file content at reported line numbers:
```python
def handle_css_error(error, css_file):
    """Enhanced CSS error reporting showing actual file content."""
    with open(css_file) as f:
        lines = f.readlines()

    # Show actual content at error line
    error_line = error.line_number
    context = lines[max(0, error_line-3):error_line+3]
    # Display with proper line numbers
```

### 5. **Textual Version Pinning**
Pin Textual version in requirements to avoid breaking changes:
```
textual==5.0.1  # Pin to tested version
```

### 6. **Pre-commit CSS Validation**
Add a pre-commit hook that validates CSS files before commit:
```yaml
- repo: local
  hooks:
    - id: validate-css
      name: Validate Textual CSS
      entry: python -m code_cop.utils.validate_css
      language: system
      files: \.tcss$
```

## Lessons Learned

1. **CSS Parsing Errors Can Be Misleading**: The error location and content may not match the actual file
2. **Variable Names Matter**: Even unused CSS variables can cause parser issues
3. **Terminal State Management**: Always ensure proper cleanup in terminal applications
4. **Isolation Testing**: Creating minimal reproducible examples is crucial for debugging
5. **Third-party Library Quirks**: Be prepared for unexpected behavior in CSS/styling engines

## Action Items

- [ ] Implement CSS validation test
- [ ] Add terminal cleanup exception handler  
- [ ] Document CSS variable naming conventions
- [ ] Consider reporting issue to Textual project
- [ ] Add pre-commit CSS validation hook