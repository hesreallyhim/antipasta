# Treemap LOC Failure: What Went Wrong and the Fix

## The Symptom
Running `treemap_loc.py` to visualize our codebase failed with:

```
ValueError: ('None entries cannot have not-None children',
            ('antipasta', 'cli', 'config', 'config_generate', 'file_operations.py'))
```

Plotly (the charting library) refused to build the treemap, saying that some nodes had `None` parents. That message is opaque, so here’s what it really means.

## The Root Cause in Plain English
The treemap needs to know the tree structure from folders down to files. We were giving it this information as a table with columns like `level_0`, `level_1`, …, where deeper levels get filled in when the path is that deep. For shallower files, the unused columns were left as `None`.

Plotly expects every lane in the tree to be continuous. When it encountered the row for
`antipasta/cli/config/config_generate/file_operations.py`, it looked at the columns and saw:

```
level_0 = 'antipasta'
level_1 = 'cli'
level_2 = 'config'
level_3 = 'config_generate'
```

So far, so good. But for many other files that lived in shallower folders (say, only two levels deep), the columns for deeper levels were `None`. Plotly interpreted this as “there is an entry where a parent is `None`, but the child isn’t,” which breaks its internal tree building. In short, we never explicitly told Plotly “this is a directory node,” so it couldn’t piece together the hierarchy reliably.

## The Fix
Instead of relying on those sparse columns, we now build an explicit tree ourselves:

1. **Keep raw path parts** for every file (e.g., `['antipasta', 'cli', 'config']`).
2. **Aggregate directories** with their total line counts.
3. **Construct a node table** with columns `id`, `label`, `parent`, and `value`, so every directory and file becomes a row, and every row knows its parent’s `id`.
4. Feed this table into Plotly using its `ids`, `parents`, and `values` arguments.

With this structure, no node has a missing parent, and Plotly is happy—it can also correctly size directories based on the sum of their children.

We tested the new flow by running:

```
python treemap_loc.py --root src --output /tmp/out.html
```

The script now writes the HTML treemap without the previous error.

## TL;DR
- Plotly treemaps need every node to have a real parent.
- Our original dataframe only described leaf nodes, leaving implied parents as `None`.
- We now explicitly add directory nodes and wire up the parent–child relationships before calling Plotly.
- The treemap generation works again.
