# Terminal Dashboard Design

## Overview

The terminal dashboard provides a rich, interactive TUI (Terminal User Interface) for code-cop metrics visualization directly in the terminal. It complements the web dashboard by offering immediate, inline analysis during development.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                          │
│              code-cop analyze --format=terminal                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                    Terminal UI Framework                        │
│                    (Rich/Textual/Blessed)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                  Dashboard Components                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │ FileTreePane │ │ MetricsPane  │ │ DetailsPane  │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │ HeatmapView  │ │ TrendView    │ │ SummaryView  │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                    Code-Cop Core Engine                         │
└─────────────────────────────────────────────────────────────────┘
```

## UI Layout Options

### 1. **Split Pane Layout** (Default)
```
┌─────────────────────┬─────────────────────────────────────────┐
│   File Explorer     │          Metrics Overview               │
│                     │                                         │
│ ▼ src/              │  Cyclomatic Complexity Distribution    │
│   ▶ auth/           │  ████████████████ 45% (≤5)            │
│   ▼ core/           │  ███████          20% (6-10)          │
│     • engine.py  🔴 │  ████             12% (11-15)         │
│     • parser.py  🟡 │  ██               8% (16-20)          │
│   ▶ utils/          │  █                5% (>20)            │
│                     │                                         │
├─────────────────────┼─────────────────────────────────────────┤
│   Quick Stats       │          Detail View                    │
│                     │                                         │
│ Files:        127   │  src/core/engine.py                     │
│ Critical:       3   │  ─────────────────────────────────────  │
│ High:          12   │  process_metrics() - CC: 18 🔴          │
│ Medium:        34   │  validate_input()  - CC: 12 🟡          │
│ Low:           78   │  initialize()      - CC: 3  🟢          │
└─────────────────────┴─────────────────────────────────────────┘
[Tab] Switch Pane  [↑↓] Navigate  [Enter] Select  [q] Quit  [?] Help
```

### 2. **Heatmap Focus Mode**
```
┌─────────────────────────────────────────────────────────────────┐
│                    Complexity Heatmap                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  src/                                                          │
│  ├─ auth/          ████████░░ 76%  [4 files]                  │
│  ├─ core/          █████████░ 89%  [8 files] ⚠️               │
│  ├─ database/      ███░░░░░░░ 31%  [12 files]                 │
│  ├─ api/           ██████░░░░ 58%  [23 files]                 │
│  └─ utils/         ██░░░░░░░░ 22%  [15 files]                 │
│                                                                 │
│  Hottest Files:                                                │
│  1. core/engine.py         ██████████ CC: 142 🔴              │
│  2. core/analyzer.py       █████████░ CC: 98  🔴              │
│  3. auth/validator.py      ████████░░ CC: 67  🟠              │
│  4. api/endpoints.py       ███████░░░ CC: 54  🟠              │
│  5. api/middleware.py      ██████░░░░ CC: 43  🟡              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
[Enter] Drill Down  [Esc] Back  [s] Sort  [f] Filter  [q] Quit
```

### 3. **Trend Analysis Mode**
```
┌─────────────────────────────────────────────────────────────────┐
│              Complexity Trends (Last 30 Days)                   │
├─────────────────────────────────────────────────────────────────┤
│     ▲                                                          │
│  40 │     ╭─╮                                                  │
│  35 │    ╱  ╲              Average Complexity                  │
│  30 │   ╱    ╲    ╭───╮                                       │
│  25 │  ╱      ╲__╱     ╲                                      │
│  20 │ ╱                 ╲____╱╲                               │
│  15 │╱                          ╲___________                    │
│  10 │                                       ╲───               │
│   5 │                                                          │
│     └────────────────────────────────────────────► Time        │
│      1w ago                                    Today           │
│                                                                 │
│  Recent Changes:                                                │
│  ↓ -23% engine.py     (Refactored process_metrics)            │
│  ↑ +45% new_api.py    (Added complex validation)              │
│  ↓ -12% auth.py       (Simplified auth flow)                  │
└─────────────────────────────────────────────────────────────────┘
[←→] Change Timeframe  [m] Metrics  [c] Compare  [q] Quit
```

## Key Features

### 1. **Interactive Navigation**
- Keyboard-driven with vim-style bindings
- Mouse support for modern terminals
- Breadcrumb navigation
- Quick jump with fuzzy search (/)

### 2. **Real-time Updates**
- File watcher integration
- Live complexity recalculation
- Smooth transitions between states
- Progress indicators for analysis

### 3. **Multiple Views**
- **Overview**: High-level metrics summary
- **File Explorer**: Navigate with inline indicators
- **Heatmap**: Visual complexity distribution
- **Details**: Function-level breakdown
- **Trends**: Historical analysis
- **Compare**: Side-by-side branch/commit comparison

### 4. **Terminal-Optimized Visualizations**
- ASCII/Unicode charts and graphs
- Box-drawing characters for structure
- Emoji indicators (optional)
- 256-color gradients
- Braille patterns for high-density data

## Implementation Approach

### Framework Selection

**Recommendation: Textual (Python)**
- Modern, React-like component model
- Built-in widgets and layouts
- CSS-like styling
- Async support
- Active development

**Alternatives considered:**
- Rich: Great for simple TUIs, less suited for complex interactions
- Blessed/Urwid: Powerful but more complex API
- Bubble Tea (Go): Would require language switch

### Component Structure

```python
# code_cop/terminal/dashboard.py
class TerminalDashboard(App):
    def compose(self):
        yield Header()
        yield Container(
            FileTree(id="file-tree"),
            MetricsPanel(id="metrics"),
            DetailsView(id="details"),
        )
        yield Footer()

# code_cop/terminal/widgets/heatmap.py  
class HeatmapWidget(Widget):
    def render(self) -> RenderableType:
        # Generate colored blocks based on metrics
        pass
```

## Color Schemes

### Default Theme
- 🟢 Green: 0-5 complexity
- 🟡 Yellow: 6-10 complexity  
- 🟠 Orange: 11-15 complexity
- 🔴 Red: 16-20 complexity
- 🟣 Purple: >20 complexity

### Accessibility
- Colorblind-friendly palette option
- Pattern indicators (/, \, |, #)
- High contrast mode
- Screen reader annotations

## Integration Points

### 1. **CLI Arguments**
```bash
code-cop analyze --format=terminal
code-cop tui                      # Alias for terminal dashboard
code-cop tui --watch             # Auto-refresh mode
code-cop tui --theme=solarized   # Custom themes
```

### 2. **Configuration**
```yaml
# .code_cop.yaml
terminal:
  theme: default
  colors:
    low: green
    medium: yellow
    high: red
    critical: magenta
  unicode: true
  mouse: true
  refresh_interval: 5
```

### 3. **Export Options**
- Screenshot to PNG (if supported)
- Export current view to text file
- Copy formatted output to clipboard
- Generate shareable ASCII report

## Performance Considerations

- Lazy loading for large codebases
- Virtual scrolling for file lists
- Debounced updates during rapid changes
- Minimal redraw regions
- Background metric calculation