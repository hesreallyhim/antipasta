# Terminal Dashboard - Ticket List

## Overview

This ticket list covers the implementation of a terminal-based dashboard for antipasta, providing rich TUI visualizations directly in the terminal. The terminal dashboard complements the web dashboard for developers who prefer CLI workflows.

## Ticket List

### Phase 1: Foundation

#### TERM-001: Set up Textual framework
**Priority**: P0
**Effort**: 2 points
**Description**: Initialize terminal UI framework
- Add `textual` to requirements.txt
- Create `antipasta/terminal/` package structure
- Set up basic app skeleton
- Configure CSS styling system
- Add development hot-reload setup

#### TERM-002: Create base dashboard application
**Priority**: P0
**Effort**: 3 points
**Description**: Implement core dashboard app class
- Create `TerminalDashboard(App)` class
- Set up main layout containers
- Implement keyboard navigation
- Add basic theming support
- Create app lifecycle management

#### TERM-003: Add CLI entry point
**Priority**: P0
**Effort**: 2 points
**Description**: Wire up terminal dashboard to CLI
- Add `antipasta tui` command
- Add `--format=terminal` to analyze command
- Support common flags (--watch, --theme)
- Handle terminal capability detection
- Add graceful exit handling

#### TERM-004: Build data bridge to core engine
**Priority**: P0
**Effort**: 3 points
**Description**: Connect TUI to metric collection
- Create data adapter layer
- Implement metric refresh logic
- Add caching for performance
- Handle async metric updates
- Create error boundary handling

### Phase 2: Core Widgets

#### TERM-005: Implement file tree widget
**Priority**: P1
**Effort**: 4 points
**Description**: Interactive file explorer with indicators
- Tree structure with expand/collapse
- Inline complexity indicators (colored dots/emoji)
- Keyboard navigation (j/k, arrow keys)
- Search/filter capability (/)
- File count badges per directory

#### TERM-006: Create metrics overview panel
**Priority**: P1
**Effort**: 3 points
**Description**: Summary statistics widget
- Total files analyzed
- Complexity distribution bars
- Critical/High/Medium/Low counts
- Average metrics display
- Refresh timestamp

#### TERM-007: Build heatmap visualization
**Priority**: P1
**Effort**: 5 points
**Description**: Terminal-based heatmap rendering
- Colored Unicode blocks (█▓▒░)
- Hierarchical directory view
- Intensity mapping to colors
- Interactive drill-down
- Legend and scale display

#### TERM-008: Implement detail view panel
**Priority**: P1
**Effort**: 4 points
**Description**: File/function detail display
- Syntax-highlighted code preview
- Function-level metric breakdown
- Line-by-line complexity indicators
- Scrollable content area
- Copy-to-clipboard support

### Phase 3: Interactive Features

#### TERM-009: Add keyboard shortcut system
**Priority**: P1
**Effort**: 3 points
**Description**: Comprehensive keyboard controls
- Vim-style navigation bindings
- Quick actions (r=refresh, q=quit, ?=help)
- Mode switching (1-9 for views)
- Customizable keybindings
- Shortcut hint bar

#### TERM-010: Implement focus management
**Priority**: P2
**Effort**: 2 points
**Description**: Pane focus and navigation
- Tab to cycle panes
- Visual focus indicators
- Maintain focus state
- Focus history (Alt+Tab style)
- Mouse click focus support

#### TERM-011: Create command palette
**Priority**: P2
**Effort**: 3 points
**Description**: Quick command interface (Ctrl+P)
- Fuzzy file search
- Action commands
- Recent files list
- Quick navigation
- Extensible command system

#### TERM-012: Build filtering system
**Priority**: P2
**Effort**: 3 points
**Description**: Filter metrics display
- Complexity threshold filters
- File pattern matching
- Include/exclude patterns
- Quick filter presets
- Filter indicator badges

### Phase 4: Visualizations

#### TERM-013: Implement ASCII charts
**Priority**: P2
**Effort**: 4 points
**Description**: Terminal-friendly charts
- Bar charts for distributions
- Line graphs for trends
- Sparklines for quick stats
- Box plots for ranges
- Unicode/ASCII fallback modes

#### TERM-014: Create trend view
**Priority**: P2
**Effort**: 4 points
**Description**: Historical metric tracking
- Time series visualization
- Period selection (1d/1w/1m)
- Delta indicators (↑↓)
- Commit message integration
- Export trend data

#### TERM-015: Build comparison mode
**Priority**: P3
**Effort**: 4 points
**Description**: Side-by-side comparisons
- Split screen layout
- Branch/commit selection
- Diff highlighting
- Metric delta display
- Synchronized scrolling

#### TERM-016: Add minimap widget
**Priority**: P3
**Effort**: 3 points
**Description**: Bird's eye view of codebase
- Braille pattern density map
- Scrollable overview
- Click to navigate
- Highlight current position
- Configurable size

### Phase 5: Advanced Features

#### TERM-017: Implement watch mode
**Priority**: P2
**Effort**: 3 points
**Description**: Auto-refresh on file changes
- File system monitoring
- Incremental updates
- Change notifications
- Debounced refreshing
- Pause/resume capability

#### TERM-018: Add export functionality
**Priority**: P3
**Effort**: 3 points
**Description**: Export dashboard views
- Screenshot to image (if supported)
- Copy formatted text
- Export to markdown
- Generate ASCII reports
- Save view state

#### TERM-019: Create theme system
**Priority**: P3
**Effort**: 3 points
**Description**: Customizable appearance
- Built-in themes (dark/light/solarized)
- Color scheme editor
- Font/character preferences
- Save custom themes
- Theme hot-swapping

#### TERM-020: Build plugin architecture
**Priority**: P4
**Effort**: 5 points
**Description**: Extensible widget system
- Widget plugin API
- Custom visualization types
- Plugin discovery
- Sandboxed execution
- Plugin marketplace

### Phase 6: Performance & Polish

#### TERM-021: Optimize rendering performance
**Priority**: P3
**Effort**: 4 points
**Description**: Smooth UI performance
- Virtual scrolling for long lists
- Dirty region tracking
- Render batching
- Lazy widget loading
- FPS monitoring

#### TERM-022: Add accessibility features
**Priority**: P3
**Effort**: 3 points
**Description**: Screen reader support
- Alternative text for visuals
- High contrast mode
- Pattern-based indicators
- Keyboard-only navigation
- Sound cues option

#### TERM-023: Implement session management
**Priority**: P4
**Effort**: 3 points
**Description**: Save and restore state
- Remember last view
- Bookmark locations
- Session history
- Quick save/load
- Multi-session support

#### TERM-024: Create interactive tutorial
**Priority**: P4
**Effort**: 2 points
**Description**: Onboarding experience
- Guided tour overlay
- Interactive hints
- Practice playground
- Feature discovery
- Skip/resume options

## Technical Implementation Notes

### Widget Architecture
```python
# Base widget class
class MetricWidget(Static):
    def __init__(self, metric_data: MetricResult):
        self.metric_data = metric_data

    def on_mount(self):
        self.update_display()

    def update_display(self):
        # Render metric visualization
        pass
```

### Layout Management
- Use Textual's grid system
- Responsive container sizing
- Dock areas for fixed panels
- Scrollable regions for content

### Performance Strategies
- Virtualize long lists
- Cache rendered content
- Debounce rapid updates
- Use worker threads for analysis
- Progressive rendering

### Color Management
```python
# Adaptive color system
class ColorMapper:
    def get_color(self, value: float, metric_type: str) -> str:
        if not self.terminal_supports_color():
            return self.get_pattern(value)
        return self.get_gradient_color(value)
```

## Integration with Existing Tools

### Shared Components
- Reuse metric collection from core
- Share configuration system
- Common color/threshold logic
- Unified plugin interface

### Terminal Detection
```python
# Capability detection
def get_terminal_features():
    return {
        'colors': curses.has_colors(),
        'unicode': sys.stdout.encoding == 'utf-8',
        'mouse': curses.has_mouse(),
        'size': shutil.get_terminal_size()
    }
```

## Success Metrics

- Sub-100ms response to keystrokes
- Support 10k+ file codebases
- Work in 80x24 terminals minimum
- <5 second startup time
- 90%+ command coverage vs web UI