/* antipasta offline report renderer.
 *
 * Reads window.ANTIPASTA_DATA (injected by antipasta.report.html) and renders:
 *  - a d3 treemap (area = SLOC, color = selected metric vs threshold)
 *  - hover tooltip with all file metrics
 *  - click-to-inspect detail panel with a sortable function table
 *  - a global "worst functions" table
 *  - per-language metric coverage chips (missing metrics render neutral)
 *  - when DATA.baseline is present: "vs baseline" mode — delta tile coloring
 *    (red = regressed, green = improved), a regressions table, and baseline
 *    metadata in the header
 *
 * Framework-free ES6; d3 v7 is embedded in the same document.
 */
(() => {
  "use strict";

  const DATA = window.ANTIPASTA_DATA;
  const files = DATA.files || [];
  const thresholds = DATA.thresholds || {};
  const coverage = DATA.language_coverage || {};
  const baseline = DATA.baseline || null;
  const baselineAddedFiles = new Set(baseline ? baseline.files_added : []);
  let baselineMode = Boolean(baseline);

  const CANONICAL_METRICS = [
    "cyclomatic_complexity", "cognitive_complexity", "maintainability_index",
    "halstead_volume", "halstead_difficulty", "halstead_effort",
    "halstead_time", "halstead_bugs", "lines_of_code",
    "logical_lines_of_code", "source_lines_of_code", "comment_lines",
    "blank_lines",
  ];

  const NEUTRAL = "#d3d7dc";
  const badnessColor = d3.scaleLinear()
    .domain([0, 0.5, 1, 1.5])
    .range(["#1a9850", "#a6d96a", "#fee08b", "#d73027"])
    .clamp(true);

  // ----- helpers ----------------------------------------------------------

  function metricLabel(key) {
    const text = key.replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function fmt(value) {
    if (value === null || value === undefined) return "—";
    if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString();
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function availableMetrics() {
    const seen = new Set();
    for (const f of files) {
      for (const k of Object.keys(f.metrics)) seen.add(k);
      for (const fn of f.functions) for (const k of Object.keys(fn.metrics)) seen.add(k);
    }
    const ordered = CANONICAL_METRICS.filter((k) => seen.has(k));
    for (const k of [...seen].sort()) if (!ordered.includes(k)) ordered.push(k);
    return ordered;
  }

  // 90th percentile per metric, for coloring metrics that have no threshold.
  const relativeScale = {};
  function relScale(metricKey) {
    if (!(metricKey in relativeScale)) {
      const values = files
        .map((f) => f.metrics[metricKey])
        .filter((v) => v !== undefined && v !== null)
        .sort((a, b) => a - b);
      relativeScale[metricKey] = values.length
        ? values[Math.min(values.length - 1, Math.floor(values.length * 0.9))]
        : 0;
    }
    return relativeScale[metricKey];
  }

  function badness(metricKey, value) {
    const th = thresholds[metricKey];
    if (th && th.threshold > 0) {
      if (th.direction === "min") return value <= 0 ? 1.5 : th.threshold / value;
      return value / th.threshold;
    }
    const scale = relScale(metricKey);
    return scale > 0 ? value / scale : 0;
  }

  function tileFill(fileEntry, metricKey) {
    const value = fileEntry ? fileEntry.metrics[metricKey] : undefined;
    if (value === undefined || value === null) return NEUTRAL;
    return badnessColor(badness(metricKey, value));
  }

  function isOverThreshold(metricKey, value) {
    if (value === undefined || value === null) return false;
    const th = thresholds[metricKey];
    if (!th || th.threshold <= 0) return false;
    return th.direction === "min" ? value < th.threshold : value > th.threshold;
  }

  // ----- baseline deltas ----------------------------------------------------

  const UNCHANGED_FILL = "#eef1f4";
  const NEW_FILE_FILL = "#cfdcec";
  const regressRamp = d3.scaleLinear().domain([0, 1]).range(["#f6ebe8", "#c62828"]).clamp(true);
  const improveRamp = d3.scaleLinear().domain([0, 1]).range(["#e8f0ea", "#1b7837"]).clamp(true);

  function fmtDelta(value) {
    if (value === null || value === undefined) return "—";
    const text = fmt(Math.abs(value));
    return value >= 0 ? `+${text}` : `−${text}`;
  }

  function baselineDelta(fileEntry, metricKey) {
    const deltas = baseline.file_deltas[fileEntry.path];
    return deltas ? deltas[metricKey] : undefined;
  }

  // Largest |delta| per metric across files, for red/green intensity.
  const deltaScaleCache = {};
  function deltaScale(metricKey) {
    if (!(metricKey in deltaScaleCache)) {
      let max = 0;
      for (const deltas of Object.values(baseline.file_deltas)) {
        const d = deltas[metricKey];
        if (d !== undefined && d !== null) max = Math.max(max, Math.abs(d));
      }
      deltaScaleCache[metricKey] = max;
    }
    return deltaScaleCache[metricKey];
  }

  function deltaFill(fileEntry, metricKey) {
    if (baselineAddedFiles.has(fileEntry.path)) return NEW_FILE_FILL;
    const delta = baselineDelta(fileEntry, metricKey);
    if (delta === undefined || delta === null || delta === 0) return UNCHANGED_FILL;
    const th = thresholds[metricKey];
    const worse = th && th.direction === "min" ? -delta : delta;
    const scale = deltaScale(metricKey);
    const intensity = scale > 0 ? Math.abs(worse) / scale : 0;
    return worse > 0 ? regressRamp(intensity) : improveRamp(intensity);
  }

  function currentTileFill(fileEntry, metricKey) {
    if (baselineMode && baseline) return deltaFill(fileEntry, metricKey);
    return tileFill(fileEntry, metricKey);
  }

  // ----- header -----------------------------------------------------------

  function renderHeader() {
    const meta = document.getElementById("meta-line");
    meta.textContent = `${DATA.root} · generated ${DATA.generated_at}` +
      ` · antipasta v${DATA.tool_version} · schema v${DATA.schema_version}` +
      (baseline
        ? ` · vs baseline ${baseline.label}` +
          (baseline.generated_at ? ` (${baseline.generated_at})` : "")
        : "");

    const chips = document.getElementById("summary-chips");
    const s = DATA.summary || {};
    chips.append(el("span", { class: "chip" }, `${s.total_files ?? files.length} files`));
    const byLang = s.files_by_language || {};
    for (const [lang, count] of Object.entries(byLang)) {
      chips.append(el("span", { class: "chip" }, `${lang}: ${count}`));
    }
    const violations = s.total_violations ?? 0;
    chips.append(el(
      "span",
      { class: `chip ${violations > 0 ? "alert" : "ok"}` },
      violations > 0
        ? `${violations} violations in ${s.files_with_violations} files`
        : "no violations",
    ));
    if (baseline) renderBaselineChips(chips);
  }

  function renderBaselineChips(chips) {
    const added = baseline.files_added.length;
    const removed = baseline.files_removed.length;
    if (added || removed) {
      chips.append(el("span", { class: "chip" }, `files +${added} / −${removed}`));
    }
    const regressed = baseline.regressions.length;
    const improved = baseline.improvements.length;
    chips.append(el(
      "span",
      { class: `chip ${regressed > 0 ? "delta-reg" : "ok"}` },
      `${regressed} regressed`,
    ));
    if (improved) chips.append(el("span", { class: "chip delta-imp" }, `${improved} improved`));
    if (baseline.violations_added > 0) {
      chips.append(el("span", { class: "chip alert" },
        `+${baseline.violations_added} new violations`));
    }
  }

  // ----- coverage chips ---------------------------------------------------

  function renderCoverageChips(selectedMetric) {
    const box = document.getElementById("coverage-chips");
    clear(box);
    for (const [lang, metrics] of Object.entries(coverage)) {
      const has = metrics.includes(selectedMetric);
      const chip = el(
        "span",
        { class: `chip ${has ? "" : "missing"}` },
        has
          ? `${lang} · ${metrics.length} metrics`
          : `${lang} · no ${metricLabel(selectedMetric).toLowerCase()}`,
      );
      chip.title = `${lang} coverage: ${metrics.map(metricLabel).join(", ")}`;
      box.append(chip);
    }
  }

  function renderLegend(selectedMetric) {
    const th = thresholds[selectedMetric];
    const low = document.getElementById("legend-low");
    const high = document.getElementById("legend-high");
    const bar = document.getElementById("legend-bar");
    bar.classList.toggle("delta", baselineMode && Boolean(baseline));
    if (baselineMode && baseline) {
      low.textContent = "improved";
      high.textContent = "regressed vs baseline";
      return;
    }
    if (th && th.threshold > 0) {
      low.textContent = th.direction === "min" ? "high (good)" : "low (good)";
      high.textContent = `${th.direction === "min" ? "below" : "over"} threshold (${fmt(th.threshold)})`;
    } else {
      low.textContent = "low";
      high.textContent = "high (relative scale, no threshold)";
    }
  }

  // ----- treemap ----------------------------------------------------------

  const svg = d3.select("#treemap");
  const WIDTH = 1160;
  const HEIGHT = 640;
  let leafSelection = null;
  let selectedTile = null;

  function buildHierarchy() {
    const rootNode = d3.stratify()
      .id((d) => d.id)
      .parentId((d) => d.parent)(DATA.treemap);
    rootNode.sum((d) => d.value || 0);
    rootNode.sort((a, b) => b.value - a.value);
    d3.treemap()
      .size([WIDTH, HEIGHT])
      .paddingInner(2)
      .paddingTop((d) => (d.depth > 0 ? 16 : 4))
      .paddingLeft(3)
      .paddingRight(3)
      .paddingBottom(3)
      .round(true)(rootNode);
    return rootNode;
  }

  function renderTreemap(selectedMetric) {
    clear(svg.node());
    if (!files.length) {
      svg.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40)
        .text("No analyzable files found.");
      return;
    }

    let rootNode;
    try {
      rootNode = buildHierarchy();
    } catch (err) {
      svg.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40)
        .text(`Treemap error: ${err.message}`);
      return;
    }

    const dirs = rootNode.descendants().filter((d) => d.children && d.depth > 0);
    const dirGroups = svg.selectAll("g.dir").data(dirs).join("g").attr("class", "dir");
    dirGroups.append("rect")
      .attr("class", "dir-rect")
      .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
      .attr("width", (d) => Math.max(0, d.x1 - d.x0))
      .attr("height", (d) => Math.max(0, d.y1 - d.y0));
    dirGroups.append("text")
      .attr("class", "dir-label")
      .attr("x", (d) => d.x0 + 4).attr("y", (d) => d.y0 + 12)
      .text((d) => truncate(d.data.label, d.x1 - d.x0 - 8));

    const leaves = rootNode.leaves().filter((d) => d.data.file_index !== undefined && d.data.file_index !== null);
    const groups = svg.selectAll("g.leaf").data(leaves).join("g").attr("class", "leaf");

    leafSelection = groups.append("rect")
      .attr("class", "tile")
      .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
      .attr("width", (d) => Math.max(0, d.x1 - d.x0))
      .attr("height", (d) => Math.max(0, d.y1 - d.y0))
      .attr("fill", (d) => currentTileFill(files[d.data.file_index], selectedMetric))
      .on("mousemove", (event, d) => showTooltip(event, files[d.data.file_index], selectedMetricNow()))
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => selectFile(d.data.file_index, event.currentTarget));

    groups.filter((d) => d.x1 - d.x0 > 56 && d.y1 - d.y0 > 16)
      .append("text")
      .attr("class", "tile-label")
      .attr("x", (d) => d.x0 + 4).attr("y", (d) => d.y0 + 12)
      .text((d) => truncate(d.data.label, d.x1 - d.x0 - 8));

    const badged = groups.filter((d) => (files[d.data.file_index].violations || []).length > 0);
    badged.append("circle")
      .attr("class", "badge")
      .attr("cx", (d) => d.x1 - 9).attr("cy", (d) => d.y0 + 9).attr("r", 7);
    badged.append("text")
      .attr("class", "badge-text")
      .attr("x", (d) => d.x1 - 9).attr("y", (d) => d.y0 + 12)
      .text((d) => files[d.data.file_index].violations.length);
  }

  function truncate(label, width) {
    const maxChars = Math.floor(width / 6.2);
    if (maxChars <= 1) return "";
    return label.length > maxChars ? label.slice(0, Math.max(1, maxChars - 1)) + "…" : label;
  }

  function recolorTreemap(selectedMetric) {
    if (leafSelection) {
      leafSelection.attr("fill", (d) => currentTileFill(files[d.data.file_index], selectedMetric));
    }
  }

  // ----- tooltip ----------------------------------------------------------

  const tooltip = document.getElementById("tooltip");

  function tooltipMetricsTable(fileEntry) {
    const table = el("table");
    const addRow = (label, value, over) => {
      const tr = el("tr");
      tr.append(el("td", null, label));
      const td = el("td", null, value);
      if (over) td.style.color = "#ff9e97";
      tr.append(td);
      table.append(tr);
    };
    addRow("Language", fileEntry.language);
    for (const key of CANONICAL_METRICS) {
      if (key in fileEntry.metrics) {
        addRow(metricLabel(key), fmt(fileEntry.metrics[key]),
          isOverThreshold(key, fileEntry.metrics[key]));
      }
    }
    return table;
  }

  function baselineTooltipNote(fileEntry, selectedMetric) {
    if (!baselineMode || !baseline) return null;
    if (baselineAddedFiles.has(fileEntry.path)) {
      return el("div", { class: "tt-note" }, "New file — not in baseline");
    }
    const delta = baselineDelta(fileEntry, selectedMetric);
    const label = metricLabel(selectedMetric).toLowerCase();
    return el("div", { class: "tt-note" },
      delta === undefined || delta === null
        ? `No ${label} change vs baseline`
        : `Δ ${label} vs baseline: ${fmtDelta(delta)}`);
  }

  function positionTooltip(event) {
    const pad = 14;
    const rect = tooltip.getBoundingClientRect();
    let x = event.clientX + pad;
    let y = event.clientY + pad;
    if (x + rect.width > window.innerWidth - 8) x = event.clientX - rect.width - pad;
    if (y + rect.height > window.innerHeight - 8) y = event.clientY - rect.height - pad;
    tooltip.style.left = `${Math.max(4, x)}px`;
    tooltip.style.top = `${Math.max(4, y)}px`;
  }

  function showTooltip(event, fileEntry, selectedMetric) {
    clear(tooltip);
    tooltip.append(el("div", { class: "tt-path" }, fileEntry.path));
    tooltip.append(tooltipMetricsTable(fileEntry));
    const note = baselineTooltipNote(fileEntry, selectedMetric);
    if (note) tooltip.append(note);
    if (!(selectedMetric in fileEntry.metrics)) {
      tooltip.append(el("div", { class: "tt-note" },
        `No ${metricLabel(selectedMetric).toLowerCase()} data for ${fileEntry.language} — shown neutral`));
    }
    if ((fileEntry.violations || []).length) {
      tooltip.append(el("div", { class: "tt-alert" },
        `${fileEntry.violations.length} threshold violation(s)`));
    }
    if (fileEntry.error) {
      tooltip.append(el("div", { class: "tt-alert" }, `Analysis error: ${fileEntry.error}`));
    }
    tooltip.hidden = false;
    positionTooltip(event);
  }

  function hideTooltip() {
    tooltip.hidden = true;
  }

  // ----- sortable tables --------------------------------------------------

  function renderSortableTable(table, columns, rows, onRowClick) {
    const state = { key: null, desc: true };

    const renderHead = () => {
      const thead = table.querySelector("thead");
      clear(thead);
      const tr = el("tr");
      for (const col of columns) {
        const th = el("th", { class: col.numeric ? "num" : "" }, col.label);
        if (state.key === col.key) {
          th.append(el("span", { class: "arrow" }, state.desc ? "▼" : "▲"));
        }
        th.addEventListener("click", () => {
          state.desc = state.key === col.key ? !state.desc : true;
          state.key = col.key;
          renderBody();
          renderHead();
        });
        tr.append(th);
      }
      thead.append(tr);
    };

    const compareRows = (a, b) => {
      const av = a[state.key];
      const bv = b[state.key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const dir = state.desc ? -1 : 1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    };

    const cellText = (col, value) => {
      if (col.delta) return fmtDelta(value);
      if (col.numeric) return fmt(value);
      return value ?? "—";
    };

    const buildCell = (col, value) => {
      const td = el("td", { class: col.numeric ? "num" : "" }, cellText(col, value));
      if (col.metric && isOverThreshold(col.metric, value)) td.classList.add("cell-over");
      if (col.delta && typeof value === "number" && value !== 0) {
        td.classList.add(value > 0 ? "delta-pos" : "delta-neg");
      }
      return td;
    };

    const buildRow = (row) => {
      const tr = el("tr");
      for (const col of columns) tr.append(buildCell(col, row[col.key]));
      if (onRowClick) tr.addEventListener("click", () => onRowClick(row));
      return tr;
    };

    const renderBody = () => {
      const tbody = table.querySelector("tbody");
      clear(tbody);
      const sorted = [...rows];
      if (state.key !== null) sorted.sort(compareRows);
      for (const row of sorted) tbody.append(buildRow(row));
    };

    renderHead();
    renderBody();
  }

  // ----- detail panel -----------------------------------------------------

  function selectFile(fileIndex, tileNode) {
    if (selectedTile) selectedTile.classList.remove("selected");
    if (tileNode) {
      selectedTile = tileNode;
      selectedTile.classList.add("selected");
    }
    const fileEntry = files[fileIndex];
    document.getElementById("detail-placeholder").hidden = true;
    document.getElementById("detail-body").hidden = false;
    document.getElementById("detail-title").textContent = "File details";
    document.getElementById("detail-path").textContent =
      `${fileEntry.path} (${fileEntry.language})`;

    const meta = document.getElementById("detail-meta");
    clear(meta);
    for (const key of CANONICAL_METRICS) {
      if (key in fileEntry.metrics) {
        meta.append(el("span", { class: "k" }, metricLabel(key)));
        const v = el("span", { class: "v" }, fmt(fileEntry.metrics[key]));
        if (isOverThreshold(key, fileEntry.metrics[key])) v.classList.add("cell-over");
        meta.append(v);
      }
    }

    const violationsBox = document.getElementById("detail-violations");
    clear(violationsBox);
    if ((fileEntry.violations || []).length) {
      const ul = el("ul", { class: "violation-list" });
      for (const violation of fileEntry.violations) {
        ul.append(el("li", null, violation.message));
      }
      violationsBox.append(ul);
    }
    if (fileEntry.error) {
      violationsBox.append(el("p", { class: "violation-list" }, `Analysis error: ${fileEntry.error}`));
    }

    const rows = fileEntry.functions.map((fn) => ({
      name: fn.name,
      line: fn.line,
      cyclomatic_complexity: fn.metrics.cyclomatic_complexity ?? null,
      cognitive_complexity: fn.metrics.cognitive_complexity ?? null,
      halstead_volume: fn.metrics.halstead_volume ?? null,
      halstead_difficulty: fn.metrics.halstead_difficulty ?? null,
    }));
    renderSortableTable(document.getElementById("function-table"), [
      { key: "name", label: "Function" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyclomatic_complexity", label: "Cyc", numeric: true, metric: "cyclomatic_complexity" },
      { key: "cognitive_complexity", label: "Cog", numeric: true, metric: "cognitive_complexity" },
      { key: "halstead_volume", label: "Volume", numeric: true },
      { key: "halstead_difficulty", label: "Difficulty", numeric: true },
    ], rows);
  }

  // ----- worst functions --------------------------------------------------

  function renderWorstFunctions() {
    const rows = [];
    files.forEach((fileEntry, index) => {
      for (const fn of fileEntry.functions) {
        const cyc = fn.metrics.cyclomatic_complexity;
        const cog = fn.metrics.cognitive_complexity;
        const candidates = [cyc, cog].filter((v) => v !== undefined && v !== null);
        if (!candidates.length) continue;
        rows.push({
          score: Math.max(...candidates),
          name: fn.name,
          path: fileEntry.path,
          line: fn.line,
          cyclomatic_complexity: cyc ?? null,
          cognitive_complexity: cog ?? null,
          halstead_volume: fn.metrics.halstead_volume ?? null,
          fileIndex: index,
        });
      }
    });
    rows.sort((a, b) => b.score - a.score || a.path.localeCompare(b.path));
    const top = rows.slice(0, 50);
    document.getElementById("worst-count").textContent =
      rows.length > 50 ? `(top 50 of ${rows.length})` : `(${rows.length})`;

    renderSortableTable(document.getElementById("worst-table"), [
      { key: "score", label: "Score", numeric: true },
      { key: "name", label: "Function" },
      { key: "path", label: "File" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyclomatic_complexity", label: "Cyc", numeric: true, metric: "cyclomatic_complexity" },
      { key: "cognitive_complexity", label: "Cog", numeric: true, metric: "cognitive_complexity" },
      { key: "halstead_volume", label: "Volume", numeric: true },
    ], top, (row) => {
      selectFile(row.fileIndex, null);
      document.getElementById("detail-panel").scrollIntoView({ block: "nearest" });
    });
  }

  // ----- baseline regressions / improvements tables -------------------------

  function baselineFunctionRow(entry, pathIndex) {
    const cyc = entry.deltas.cyclomatic_complexity;
    const cog = entry.deltas.cognitive_complexity;
    return {
      score_delta: entry.score_delta,
      name: (entry.new_violation ? "⚠ " : "") + entry.name,
      path: entry.path,
      line: entry.line,
      cyc_delta: cyc ? cyc.delta : null,
      cog_delta: cog ? cog.delta : null,
      fileIndex: pathIndex.has(entry.path) ? pathIndex.get(entry.path) : null,
    };
  }

  function renderBaselineFunctionTable(tableId, countId, entries, pathIndex) {
    const rows = entries.slice(0, 50).map((entry) => baselineFunctionRow(entry, pathIndex));
    document.getElementById(countId).textContent =
      entries.length > 50 ? `(top 50 of ${entries.length})` : `(${entries.length})`;
    renderSortableTable(document.getElementById(tableId), [
      { key: "score_delta", label: "Δ score", numeric: true, delta: true },
      { key: "name", label: "Function" },
      { key: "path", label: "File" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyc_delta", label: "Δ cyc", numeric: true, delta: true },
      { key: "cog_delta", label: "Δ cog", numeric: true, delta: true },
    ], rows, (row) => {
      if (row.fileIndex === null) return;
      selectFile(row.fileIndex, null);
      document.getElementById("detail-panel").scrollIntoView({ block: "nearest" });
    });
  }

  function renderBaselineTables() {
    if (!baseline) return;
    document.getElementById("regressions-section").hidden = false;
    const pathIndex = new Map(files.map((entry, index) => [entry.path, index]));
    renderBaselineFunctionTable(
      "regressions-table", "regressions-count", baseline.regressions, pathIndex);
    renderBaselineFunctionTable(
      "improvements-table", "improvements-count", baseline.improvements, pathIndex);
  }

  // ----- boot -------------------------------------------------------------

  const metricSelect = document.getElementById("metric-select");

  function selectedMetricNow() {
    return metricSelect.value;
  }

  function boot() {
    renderHeader();

    const metrics = availableMetrics();
    for (const key of metrics) {
      metricSelect.append(el("option", { value: key }, metricLabel(key)));
    }
    const initial = metrics.includes("cyclomatic_complexity")
      ? "cyclomatic_complexity"
      : metrics[0] || "";
    if (initial) metricSelect.value = initial;

    metricSelect.addEventListener("change", () => {
      const metric = selectedMetricNow();
      recolorTreemap(metric);
      renderLegend(metric);
      renderCoverageChips(metric);
    });

    if (baseline) {
      const wrap = document.getElementById("baseline-toggle-wrap");
      const toggle = document.getElementById("baseline-toggle");
      wrap.hidden = false;
      toggle.checked = baselineMode;
      toggle.addEventListener("change", () => {
        baselineMode = toggle.checked;
        recolorTreemap(selectedMetricNow());
        renderLegend(selectedMetricNow());
      });
    }

    renderTreemap(initial);
    renderLegend(initial);
    renderCoverageChips(initial);
    renderBaselineTables();
    renderWorstFunctions();
  }

  boot();
})();
