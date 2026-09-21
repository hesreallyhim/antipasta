/* antipasta offline report renderer — Analytical Console.
 *
 * Reads window.ANTIPASTA_DATA (injected by antipasta.report.html) and renders a
 * self-contained dashboard: hero health score, KPI strip, "fix these first"
 * list, 5 category panels (Complexity, Size, Architecture, Object Orientation,
 * Naming — the last three from the project[] block), an elevated d3 treemap,
 * top-hotspots + architecture watchlist rails, drill-down file detail with a
 * sortable function table, a worst-functions table, a violations-by-type
 * breakdown, a light/dark toggle, and — when DATA.baseline exists — full
 * "vs baseline" mode (delta tile coloring, regressions/improvements tables,
 * baseline chips, per-file delta tooltips).
 *
 * Framework-free ES6; d3 v7 is embedded in the same document. All health
 * scoring is derived here from the snapshot; every tunable lives in the
 * HEALTH block below so it can be retuned without hunting through render code.
 */
(() => {
  "use strict";

  const DATA = window.ANTIPASTA_DATA || {};
  const files = DATA.files || [];
  const thresholds = DATA.thresholds || {};
  const coverage = DATA.language_coverage || {};
  const project = DATA.project || [];
  const summary = DATA.summary || {};
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
  const PRESSURE_METRIC = "pressure";

  // ===== HEALTH ENGINE (tunables) ==========================================
  const HEALTH_WEIGHTS = { complexity: .30, readability: .24, solid: .20, mixed: .14, loc: .12 };
  const SEV_W = { viol: 0.55, prox: 0.30, worst: 0.15 };
  const PROX_LO = 0.70, PROX_HI = 1.00;
  const SOFT = {
    source_lines_of_code: 1000, single_responsibility_index: 5,
    depth_of_inheritance_tree: 5, name_clarity_floor: 0.60,
    distance_tolerance: 0.50,
  };
  // File-level metrics scored against a fixed threshold (falls back to DATA.thresholds).
  const COMPLEXITY_FILE_UNITS = {
    halstead_volume: { T: 1000, dir: "max" },
    halstead_difficulty: { T: 10, dir: "max" },
    halstead_effort: { T: 10000, dir: "max" },
  };

  // ===== metric categories =================================================
  // Canonical buckets from docs/supported_metrics.md's "Category" column. Every
  // metric belongs to exactly one; the dashboard groups and focuses by these.
  // `needs` (empty buckets) explains why a category has no data in this run;
  // DRYness is flagged custom because it has a dedicated view planned.
  const CATS = [
    { id: "loc", name: "Lines of code", src: "files" },
    { id: "complexity", name: "Complexity", src: "files · thresholds" },
    { id: "readability", name: "Readability", src: "files · project" },
    { id: "solid", name: "SOLID", src: "project" },
    { id: "mixed", name: "Mixed", src: "files · project" },
    { id: "dryness", name: "DRYness", src: "custom", custom: true,
      needs: "a duplication config block", note: "Custom duplication analysis — dedicated view planned." },
    { id: "test", name: "Test quality", src: "coverage · git", needs: "a coverage.py artifact or git history" },
    { id: "vcs", name: "VCS", src: "git history", needs: "mined git history" },
  ];
  const CAT_BY_ID = Object.fromEntries(CATS.map((c) => [c.id, c]));

  const METRIC_CAT = {
    lines_of_code: "loc", logical_lines_of_code: "loc", source_lines_of_code: "loc",
    comment_lines: "loc", blank_lines: "loc",
    cyclomatic_complexity: "complexity", halstead_volume: "complexity", halstead_difficulty: "complexity",
    halstead_effort: "complexity", halstead_time: "complexity", halstead_bugs: "complexity",
    function_statements: "complexity",
    cognitive_complexity: "readability", message_chain_depth: "readability", function_arity: "readability",
    boolean_flag_parameters: "readability", exception_discipline: "readability", global_state_reach: "readability",
    marker_density: "readability", comment_density: "readability", expression_flatness: "readability",
    pipeline_linearity: "readability", narrative_mixed_functions: "readability", narrator_budget_exceeded: "readability",
    computer_budget_exceeded: "readability", step_down_ordering: "readability", name_clarity: "readability",
    naming_antipatterns: "readability",
    lack_of_cohesion: "solid", weighted_methods_per_class: "solid", coupling_between_objects: "solid",
    depth_of_inheritance_tree: "solid", number_of_children: "solid", directory_children: "solid",
    efferent_coupling: "solid", afferent_coupling: "solid", instability: "solid", dependency_cycles: "solid",
    stable_dependencies_violations: "solid", abstractness: "solid", distance_from_main_sequence: "solid",
    dependency_inversion: "solid", layering_violations: "solid", deferred_imports: "solid",
    duplication_ratio: "dryness", clone_occurrences: "dryness",
    assertions_per_test: "test", mock_call_assertions: "test", big_literal_assertions: "test",
    test_churn_ratio: "test", co_churn_multiplicity: "test", suite_redundancy_index: "test", blast_radius: "test",
    code_churn: "vcs", change_coupling: "vcs",
    maintainability_index: "mixed", single_responsibility_index: "mixed", hotspot: "mixed",
  };
  function categoryOf(metricKey) { return METRIC_CAT[metricKey] || null; }
  let focusedCat = null; // null = "All"; otherwise a CATS id with data

  // ===== small helpers =====================================================
  function metricLabel(key) {
    if (key === PRESSURE_METRIC) return "Pressure (composite)";
    const text = String(key).replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  function fmt(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString();
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }
  function byId(id) { return document.getElementById(id); }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function baseName(p) { return String(p).split("/").pop(); }

  // ===== severity ==========================================================
  const SEV = {
    good: { glyph: "●", word: "Healthy" },
    warn: { glyph: "▲", word: "Watch" },
    bad: { glyph: "■", word: "Critical" },
    none: { glyph: "—", word: "n/a" },
  };
  function tier(h) {
    if (h === null || h === undefined) return "none";
    if (h >= 85) return "good";
    if (h >= 70) return "warn";
    return "bad";
  }
  const GRADE_BANDS = [
    [97, "A+"], [93, "A"], [90, "A-"], [87, "B+"], [83, "B"], [80, "B-"],
    [77, "C+"], [73, "C"], [70, "C-"], [67, "D+"], [63, "D"], [60, "D-"],
  ];
  function grade(h) {
    if (h === null || h === undefined) return "—";
    for (const [lo, g] of GRADE_BANDS) if (h >= lo) return g;
    return "F";
  }
  // Threshold value for a metric, falling back to a default (0/undefined -> default).
  function thresholdOr(key, dflt) {
    const th = thresholds[key];
    return (th && th.threshold) || dflt;
  }

  // ===== pressure / badness ================================================
  function pressure(value, T, dir) {
    if (value === null || value === undefined) return null;
    if (dir === "min") return value > 0 ? T / value : 2.0;
    return T > 0 ? value / T : null;
  }
  const relativeScale = {};
  function relScale(metricKey) {
    if (!(metricKey in relativeScale)) {
      const values = files.map((f) => f.metrics[metricKey])
        .filter((v) => v !== undefined && v !== null).sort((a, b) => a - b);
      relativeScale[metricKey] = values.length
        ? values[Math.min(values.length - 1, Math.floor(values.length * 0.9))] : 0;
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
  function isOverThreshold(metricKey, value) {
    if (value === undefined || value === null) return false;
    const th = thresholds[metricKey];
    if (!th || th.threshold <= 0) return false;
    return th.direction === "min" ? value < th.threshold : value > th.threshold;
  }
  // Composite per-file pressure across canonical file + function metrics.
  function filePressure(fileEntry) {
    let mx = 0, seen = false;
    for (const k of CANONICAL_METRICS) {
      const v = fileEntry.metrics[k];
      if (v === undefined || v === null) continue;
      seen = true; mx = Math.max(mx, badness(k, v));
    }
    for (const fn of fileEntry.functions || []) {
      for (const k of ["cyclomatic_complexity", "cognitive_complexity"]) {
        const v = fn.metrics[k];
        if (v === undefined || v === null) continue;
        seen = true; mx = Math.max(mx, badness(k, v));
      }
    }
    return seen ? mx : null;
  }

  // Composite per-file pressure restricted to one category's metrics (for the
  // treemap when focused on that bucket). Uses badness() so metrics without a
  // threshold fall back to a relative (90th-percentile) scale.
  function filePressureForCat(fileEntry, catId) {
    let mx = 0, seen = false;
    const consider = (k, v) => {
      if (v == null || categoryOf(k) !== catId) return;
      seen = true; mx = Math.max(mx, badness(k, v));
    };
    for (const [k, v] of Object.entries(fileEntry.metrics)) consider(k, v);
    for (const fn of fileEntry.functions || []) for (const [k, v] of Object.entries(fn.metrics)) consider(k, v);
    return seen ? mx : null;
  }

  // ===== project[] bucketing ==============================================
  const buckets = Object.fromEntries(CATS.map((c) => [c.id, []]));
  (function bucketProject() {
    for (const row of project) {
      for (const m of row.metrics || []) {
        const cat = METRIC_CAT[m.type];
        if (!cat || !buckets[cat]) continue;
        buckets[cat].push({
          subject: row.subject, type: m.type, value: m.value,
          details: m.details, line: m.line_number, fn: m.function_name,
        });
      }
    }
  })();
  function bucketByType(bucket, type) { return bucket.filter((u) => u.type === type); }
  function valuesOf(bucket, type) {
    return bucketByType(bucket, type).map((u) => u.value).filter((v) => v !== null && v !== undefined);
  }

  // ===== per-category unit pressures + health =============================
  function offenderUnits(bucket, types) {
    // Each metric here is a "count of offenders": > 0 is a real problem.
    const P = [];
    for (const t of types) for (const v of valuesOf(bucket, t)) P.push(v > 0 ? 1.5 : 0.2);
    return P;
  }
  function fileComplexityUnits(f) {
    const P = [];
    for (const [k, u] of Object.entries(COMPLEXITY_FILE_UNITS)) {
      if (f.metrics[k] == null) continue;
      const th = thresholds[k];
      P.push(pressure(f.metrics[k], th ? th.threshold : u.T, th ? th.direction : u.dir));
    }
    return P;
  }
  function fnMetricUnits(metricKey, T) {
    const P = [];
    for (const f of files) for (const fn of f.functions || []) {
      const v = fn.metrics[metricKey];
      if (v != null) P.push(pressure(v, T, "max"));
    }
    return P;
  }
  function locUnits() { // Lines of code: source-lines-of-code soft-cap pressure
    return files.filter((f) => f.metrics.source_lines_of_code != null)
      .map((f) => pressure(f.metrics.source_lines_of_code, SOFT.source_lines_of_code, "max"));
  }
  function complexityUnits() { // cyclomatic (function) + file-level Halstead
    const P = fnMetricUnits("cyclomatic_complexity", thresholdOr("cyclomatic_complexity", 10));
    for (const f of files) P.push(...fileComplexityUnits(f));
    return P;
  }
  function readabilityUnits() { // cognitive (function) + naming/narrative offenders
    const b = buckets.readability;
    const P = fnMetricUnits("cognitive_complexity", thresholdOr("cognitive_complexity", 15));
    for (const v of valuesOf(b, "name_clarity")) P.push(v > 0 ? SOFT.name_clarity_floor / v : 2.0);
    return P.concat(offenderUnits(b,
      ["naming_antipatterns", "narrative_mixed_functions", "narrator_budget_exceeded", "computer_budget_exceeded"]));
  }
  function solidUnits() { // distance-from-main-sequence + inheritance depth + SDV
    const b = buckets.solid, P = [];
    for (const v of valuesOf(b, "distance_from_main_sequence")) P.push(pressure(v, SOFT.distance_tolerance, "max"));
    for (const v of valuesOf(b, "depth_of_inheritance_tree")) P.push(pressure(v, SOFT.depth_of_inheritance_tree, "max"));
    return P.concat(offenderUnits(b, ["stable_dependencies_violations"]));
  }
  function mixedUnits() { // maintainability index (file) + single-responsibility index
    const P = files.filter((f) => f.metrics.maintainability_index != null)
      .map((f) => pressure(f.metrics.maintainability_index, thresholdOr("maintainability_index", 50), "min"));
    for (const v of valuesOf(buckets.mixed, "single_responsibility_index"))
      P.push(pressure(v, SOFT.single_responsibility_index, "max"));
    return P;
  }
  function categoryHealth(P) {
    const units = P.filter((p) => p !== null && p !== undefined);
    const n = units.length;
    if (n === 0) return { health: null, n: 0 };
    const violationRate = units.filter((p) => p > 1).length / n;
    const proximity = units.reduce((s, p) => s + clamp((p - PROX_LO) / (PROX_HI - PROX_LO), 0, 1), 0) / n;
    const worstExcess = clamp(Math.max(...units) - 1, 0, 1);
    const severity = clamp(SEV_W.viol * violationRate + SEV_W.prox * proximity + SEV_W.worst * worstExcess, 0, 1);
    return { health: Math.round(100 * (1 - severity)), n };
  }

  const UNIT_FN = {
    loc: locUnits, complexity: complexityUnits, readability: readabilityUnits,
    solid: solidUnits, mixed: mixedUnits,
  };
  function computeHealth() {
    const out = {};
    for (const c of CATS) out[c.id] = categoryHealth(UNIT_FN[c.id] ? UNIT_FN[c.id]() : []);
    return out;
  }
  const HEALTH = computeHealth();

  function overallHealth() {
    let wsum = 0, acc = 0;
    for (const c of CATS) {
      const h = HEALTH[c.id].health;
      if (h === null) continue;
      wsum += HEALTH_WEIGHTS[c.id]; acc += HEALTH_WEIGHTS[c.id] * h;
    }
    return wsum > 0 ? Math.round(acc / wsum) : null;
  }
  const OVERALL = overallHealth();

  // ===== SVG gauge / dial builders =========================================
  function arcPath(cx, cy, r, a0, a1) {
    // angles in radians, 0 at 12 o'clock, clockwise positive.
    const p = (a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    const large = (a1 - a0) > Math.PI ? 1 : 0;
    return `M${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
  }
  const SVGNS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    const node = document.createElementNS(SVGNS, tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }
  // 270° gauge, ring style. health null -> track only + neutral.
  function drawGauge(svg, health, opts) {
    clear(svg);
    const o = opts || {};
    const cx = 50, cy = 50, r = o.r || 40, w = o.w || 9;
    const span = (270 * Math.PI) / 180, start = -span / 2;
    const t = tier(health);
    const col = cssVar("--sev-" + (t === "none" ? "none" : t));
    svg.appendChild(svgEl("path", {
      d: arcPath(cx, cy, r, start, start + span), fill: "none",
      stroke: cssVar("--line"), "stroke-width": w, "stroke-linecap": "round",
    }));
    const frac = health === null ? 0 : clamp(health / 100, 0, 1);
    if (frac > 0) {
      svg.appendChild(svgEl("path", {
        class: "gauge-arc", d: arcPath(cx, cy, r, start, start + span * frac), fill: "none",
        stroke: col, "stroke-width": w, "stroke-linecap": "round",
      }));
    }
  }
  // full-circle ring (0..1 depletion), for the hotspot KPI.
  function drawRing(svg, frac, t) {
    clear(svg);
    const cx = 24, cy = 24, r = 18, w = 5;
    const col = cssVar("--sev-" + (t === "none" ? "none" : t));
    svg.setAttribute("viewBox", "0 0 48 48");
    svg.appendChild(svgEl("circle", { cx, cy, r, fill: "none", stroke: cssVar("--line"), "stroke-width": w }));
    const f = clamp(frac, 0, 1);
    if (f > 0.001) {
      const span = 2 * Math.PI * 0.999;
      svg.appendChild(svgEl("path", {
        class: "k-ring-arc", d: arcPath(cx, cy, r, -Math.PI, -Math.PI + span * f),
        fill: "none", stroke: col, "stroke-width": w, "stroke-linecap": "round",
      }));
    }
  }

  // ===== top bar ===========================================================
  function renderTopbar() {
    const meta = byId("meta-line");
    meta.textContent = `${DATA.root} · ${files.length} files · antipasta v${DATA.tool_version}`
      + ` · schema v${DATA.schema_version} · ${DATA.generated_at}`
      + (baseline ? ` · vs baseline ${baseline.label}` + (baseline.generated_at ? ` (${baseline.generated_at})` : "") : "");

    const leg = byId("sev-legend");
    clear(leg);
    for (const key of ["good", "warn", "bad", "none"]) {
      const s = el("span", { class: "sl", "data-sev": key });
      s.append(el("span", { class: "shape" }, SEV[key].glyph));
      s.append(document.createTextNode(SEV[key].word));
      s.style.color = "var(--c)";
      leg.append(s);
    }

    const chips = byId("summary-chips");
    clear(chips);
    chips.append(el("span", { class: "chip" }, `${summary.total_files ?? files.length} files`));
    for (const [lang, count] of Object.entries(summary.files_by_language || {}))
      chips.append(el("span", { class: "chip" }, `${lang}: ${count}`));
    const violations = summary.total_violations ?? 0;
    chips.append(el("span", { class: `chip ${violations > 0 ? "alert" : "ok"}` },
      violations > 0 ? `${violations} violations · ${summary.files_with_violations} files` : "no violations"));
    if (baseline) renderBaselineChips(chips);
  }
  function renderBaselineChips(chips) {
    const added = baseline.files_added.length, removed = baseline.files_removed.length;
    if (added || removed) chips.append(el("span", { class: "chip" }, `files +${added} / −${removed}`));
    const regressed = baseline.regressions.length, improved = baseline.improvements.length;
    chips.append(el("span", { class: `chip ${regressed > 0 ? "delta-reg" : "ok"}` }, `${regressed} regressed`));
    if (improved) chips.append(el("span", { class: "chip delta-imp" }, `${improved} improved`));
    if (baseline.violations_added > 0)
      chips.append(el("span", { class: "chip alert" }, `+${baseline.violations_added} new violations`));
  }

  // ===== hero ==============================================================
  function worstHotspot() {
    // File carrying the most violations, tie-broken by composite pressure.
    let best = null;
    files.forEach((f, i) => {
      const vc = (f.violations || []).length;
      const p = filePressure(f) || 0;
      const cand = { i, file: f, vc, p };
      if (!best || vc > best.vc || (vc === best.vc && p > best.p)) best = cand;
    });
    return best;
  }
  function renderHeroScore(t) {
    byId("overall-card").dataset.sev = t;
    byId("overall-score").textContent = OVERALL === null ? "n/a" : OVERALL;
    const badge = byId("overall-grade-badge");
    badge.dataset.sev = t;
    clear(badge);
    badge.append(el("span", { class: "shape" }, SEV[t].glyph));
    badge.append(document.createTextNode(` ${grade(OVERALL)} · ${SEV[t].word}`));
    drawGauge(byId("overall-gauge"), OVERALL, { r: 40, w: 10 });
  }
  function heroVerdictBaseline(verdict) {
    const reg = baseline.regressions.length, imp = baseline.improvements.length;
    verdict.append(document.createTextNode(
      reg > 0
        ? `Compared to baseline ${baseline.label}: ${reg} function${reg === 1 ? "" : "s"} regressed`
          + (imp ? `, ${imp} improved` : "") + `. `
        : `No regressions vs baseline ${baseline.label}` + (imp ? ` — ${imp} improved.` : ".")));
    if (baseline.violations_added > 0)
      verdict.append(document.createTextNode(`${baseline.violations_added} new violation${baseline.violations_added === 1 ? "" : "s"} introduced.`));
  }
  function allViolationsInHotspot(totalV, hot) {
    return totalV > 0 && hot && hot.vc === totalV && hot.vc > 0;
  }
  function heroVerdictScored(verdict, t) {
    const s = summary;
    const clean = (s.total_files ?? files.length) - (s.files_with_violations ?? 0);
    const hot = worstHotspot();
    const totalV = s.total_violations ?? 0;
    const band = t === "good" ? "A healthy codebase" : t === "warn" ? "A codebase worth watching" : "A codebase under real pressure";
    verdict.append(document.createTextNode(`${band} — ${clean} of ${s.total_files ?? files.length} files are clean`));
    if (allViolationsInHotspot(totalV, hot)) {
      verdict.append(document.createTextNode(`; all ${totalV} violations live in `));
      verdict.append(el("code", null, hot.file.path)); verdict.append(document.createTextNode("."));
    } else if (totalV > 0) {
      verdict.append(document.createTextNode(`; ${totalV} threshold violation${totalV === 1 ? "" : "s"} across ${s.files_with_violations} file${s.files_with_violations === 1 ? "" : "s"}.`));
    } else {
      verdict.append(document.createTextNode(" with no threshold violations."));
    }
  }
  function renderHeroVerdict(t) {
    const verdict = byId("hero-verdict");
    clear(verdict);
    if (baselineMode && baseline) heroVerdictBaseline(verdict);
    else if (OVERALL === null) verdict.textContent = "Not enough measured signal to score this codebase.";
    else heroVerdictScored(verdict, t);
  }
  function renderHeroTrend() {
    const worstCat = CATS.map((c) => ({ c, h: HEALTH[c.id].health })).filter((x) => x.h !== null).sort((a, b) => a.h - b.h)[0];
    byId("hero-trend").textContent = worstCat
      ? `weakest area: ${worstCat.c.name} (${worstCat.h}/100 · ${grade(worstCat.h)})`
      : "no measured categories";
  }
  function renderHero() {
    const t = tier(OVERALL);
    renderHeroScore(t);
    renderHeroVerdict(t);
    renderHeroTrend();
  }

  // ===== KPI strip =========================================================
  function kpiCard(lab, val, sub, sev) {
    const c = el("div", { class: "card kpi" });
    if (sev) c.dataset.sev = sev;
    c.append(el("div", { class: "k-lab" }, lab));
    c.append(el("span", { class: "k-val" }, val));
    c.append(el("div", { class: "k-sub" }, sub));
    return c;
  }
  function filesKpiCard() {
    const s = summary;
    const langs = Object.keys(s.files_by_language || {});
    return kpiCard("Files analyzed", String(s.total_files ?? files.length),
      langs.length ? `${langs.length} language${langs.length === 1 ? "" : "s"}: ${langs.join(", ")}` : "—", null);
  }
  function severityFor(value, goodBelow, warnBelow) {
    if (value < goodBelow) return "good";
    if (value < warnBelow) return "warn";
    return "bad";
  }
  function deltaViolationsKpiCard() {
    const net = baseline.violations_added;
    const sign = net >= 0 ? "+" : "−";
    let sev = "none";
    if (net > 0) sev = "bad";
    else if (net < 0) sev = "good";
    const sub = baseline.regressions.length + " regressed · " + baseline.improvements.length + " improved";
    return kpiCard("Δ violations vs baseline", sign + Math.abs(net), sub, sev);
  }
  function thresholdViolationsKpiCard() {
    const s = summary;
    const totalV = s.total_violations ?? 0;
    const filesN = s.total_files ?? files.length;
    const affected = s.files_with_violations ?? 0;
    const sev = totalV === 0 ? "good" : severityFor(totalV, 0, 6);
    return kpiCard("Threshold violations", String(totalV), affected + " of " + filesN + " files affected", sev);
  }
  function violationsKpiCard() {
    if (baselineMode && baseline) return deltaViolationsKpiCard();
    return thresholdViolationsKpiCard();
  }
  function hotspotSeverity(hot, p) {
    if (!(hot.vc > 0 || p > 1)) return "good";
    return p > 1.3 || hot.vc > 3 ? "bad" : "warn";
  }
  function emptyHotspotKpiCard() {
    const card = el("div", { class: "card kpi" });
    card.dataset.sev = "none";
    card.append(el("div", { class: "k-lab" }, "Primary hotspot"));
    card.append(el("span", { class: "k-val" }, "—"));
    card.append(el("div", { class: "k-sub" }, "no files"));
    return card;
  }
  function hotspotKpiCard() {
    const hot = worstHotspot();
    if (!hot) return emptyHotspotKpiCard();
    const p = hot.p || 0;
    const frac = clamp((p - 0.7) / 0.8, 0, 1);
    const st = hotspotSeverity(hot, p);
    const mi = hot.file.metrics.maintainability_index;
    const card = el("div", { class: "card kpi" });
    card.dataset.sev = st;
    card.append(el("div", { class: "k-lab" }, "Primary hotspot"));
    card.append(el("span", { class: "k-val", style: "font-size:16px;line-height:1.3;white-space:normal;word-break:break-all" }, baseName(hot.file.path)));
    card.append(el("div", { class: "k-sub" },
      `${hot.vc} violation${hot.vc === 1 ? "" : "s"}` + (mi != null ? ` · MI ${fmt(mi)}` : "")));
    const ring = svgEl("svg", { class: "k-ring", viewBox: "0 0 48 48" });
    card.append(ring);
    drawRing(ring, mi != null ? clamp(1 - mi / 100, 0, 1) : frac, st);
    card.append(el("div", { class: "k-ringnum" }, mi != null ? String(Math.round(mi)) : ""));
    card.style.cursor = "pointer";
    card.addEventListener("click", () => { selectFile(hot.i, null); scrollToDetail(); });
    return card;
  }
  function cleanFilesKpiCard() {
    const s = summary;
    const cleanFiles = (s.total_files ?? files.length) - (s.files_with_violations ?? 0);
    const cleanPct = files.length ? Math.round((cleanFiles / (s.total_files ?? files.length)) * 100) : 0;
    return kpiCard("Clean files", `${cleanPct}%`, `${cleanFiles} of ${s.total_files ?? files.length} without violations`,
      cleanPct >= 90 ? "good" : cleanPct >= 70 ? "warn" : "bad");
  }
  function renderKPIs() {
    const strip = byId("kpi-strip");
    clear(strip);
    strip.append(filesKpiCard());
    strip.append(violationsKpiCard());
    strip.append(hotspotKpiCard());
    strip.append(cleanFilesKpiCard());
  }

  // ===== fix these first ===================================================
  function fileViolationCats(f) {
    const s = new Set();
    for (const v of f.violations || []) { const c = categoryOf(v.type); if (c) s.add(c); }
    return s;
  }
  function fileFixItem(f, i) {
    const vc = (f.violations || []).length;
    const p = filePressure(f) || 0;
    return {
      kind: "file", index: i, cats: fileViolationCats(f),
      score: vc * 10 + p,
      sev: vc > 3 || p > 1.3 ? "bad" : "warn",
      title: f.path,
      why: `${vc} threshold violation${vc === 1 ? "" : "s"}`
        + (f.metrics.maintainability_index != null ? ` · MI ${fmt(f.metrics.maintainability_index)}` : ""),
    };
  }
  function topUnits(bucket, type, cap, limit) {
    return bucketByType(bucket, type).filter((u) => u.value != null && u.value > cap)
      .sort((a, b) => b.value - a.value).slice(0, limit);
  }
  function buildFixList() {
    const items = [];
    files.forEach((f, i) => { if ((f.violations || []).length) items.push(fileFixItem(f, i)); });
    for (const u of topUnits(buckets.solid, "distance_from_main_sequence", SOFT.distance_tolerance, 2)) {
      items.push({ kind: "cat", cat: "solid", cats: new Set(["solid"]),
        score: 5 + u.value * 3, sev: u.value >= 0.9 ? "bad" : "warn", title: u.subject,
        why: `distance from main sequence ${fmt(u.value)} — in the zone of pain` });
    }
    for (const u of topUnits(buckets.mixed, "single_responsibility_index", SOFT.single_responsibility_index, 1)) {
      items.push({ kind: "cat", cat: "mixed", cats: new Set(["mixed"]),
        score: 4 + u.value / 5, sev: u.value > 10 ? "bad" : "warn", title: u.subject,
        why: `single-responsibility index ${fmt(u.value)} (soft cap ${SOFT.single_responsibility_index})` });
    }
    const filtered = focusedCat ? items.filter((it) => it.cats.has(focusedCat)) : items;
    filtered.sort((a, b) => b.score - a.score);
    return filtered.slice(0, 6);
  }
  function renderFixList() {
    const ol = byId("fix-list");
    clear(ol);
    const items = buildFixList();
    if (!items.length) {
      const msg = focusedCat
        ? `Nothing urgent in ${CAT_BY_ID[focusedCat].name}.`
        : (summary.total_violations ? "No ranked items." : "No threshold violations or architectural hotspots — nothing urgent to fix.");
      ol.append(el("li", { class: "fixempty" }, msg));
      return;
    }
    for (const it of items) {
      const li = el("li", { class: "fixrow" });
      li.dataset.sev = it.sev;
      li.append(el("span", { class: "fx-rank" }));
      const main = el("div", { class: "fx-main" });
      const title = el("div", { class: "fx-title" });
      title.append(el("code", null, it.title));
      main.append(title);
      main.append(el("div", { class: "fx-why" }, it.why));
      li.append(main);
      const st = el("span", { class: "status" });
      st.append(el("span", { class: "shape" }, SEV[it.sev].glyph));
      st.append(document.createTextNode(SEV[it.sev].word));
      li.append(st);
      if (it.kind === "file") li.addEventListener("click", () => { selectFile(it.index, null); scrollToDetail(); });
      else li.addEventListener("click", () => setFocus(it.cat));
      ol.append(li);
    }
  }

  // ===== category grid =====================================================
  // Returns the up-to-4 headline numbers for a category panel.
  function fnStat(metricKey, threshold) {
    let over = 0, max = 0;
    for (const f of files) for (const fn of f.functions || []) {
      const v = fn.metrics[metricKey];
      if (v == null) continue;
      max = Math.max(max, v);
      if (threshold != null && v > threshold) over++;
    }
    return { over, max };
  }
  function fileStat(metricKey, threshold) {
    let over = 0, max = 0, min = Infinity, n = 0;
    for (const f of files) {
      const v = f.metrics[metricKey];
      if (v == null) continue;
      n++; max = Math.max(max, v); min = Math.min(min, v);
      if (threshold != null && v > threshold) over++;
    }
    return { over, max, min: n ? min : null, n };
  }
  function catMetricsLoc() {
    const slocs = files.map((f) => f.metrics.source_lines_of_code).filter((v) => v != null);
    const total = slocs.reduce((a, b) => a + b, 0);
    const largest = slocs.length ? Math.max(...slocs) : 0;
    const big = slocs.filter((v) => v > 400).length;
    return [
      { v: fmt(total), l: "total SLOC", over: false },
      { v: slocs.length ? fmt(Math.round(total / slocs.length)) : "—", l: "avg / file", over: false },
      { v: fmt(largest), l: "largest file", over: largest > SOFT.source_lines_of_code },
      { v: big, l: "files > 400 SLOC", over: big > 0 },
    ];
  }
  function catMetricsComplexity() {
    const cycT = thresholdOr("cyclomatic_complexity", 10);
    const cyc = fnStat("cyclomatic_complexity", cycT);
    const hv = fileStat("halstead_volume", thresholdOr("halstead_volume", 1000));
    const hd = fileStat("halstead_difficulty", thresholdOr("halstead_difficulty", 10));
    return [
      { v: cyc.over, l: "fns over cyclomatic", over: cyc.over > 0 },
      { v: fmt(cyc.max), l: "max cyclomatic", over: cyc.max > cycT },
      { v: hd.over, l: "files over difficulty", over: hd.over > 0 },
      { v: fmt(hv.max), l: "max halstead vol", over: hv.over > 0 },
    ];
  }
  function catMetricsReadability() {
    const cogT = thresholdOr("cognitive_complexity", 15);
    const cog = fnStat("cognitive_complexity", cogT);
    const clar = valuesOf(buckets.readability, "name_clarity");
    const avg = clar.length ? clar.reduce((a, x) => a + x, 0) / clar.length : null;
    const anti = valuesOf(buckets.readability, "naming_antipatterns").filter((v) => v > 0).length;
    return [
      { v: cog.over, l: "fns over cognitive", over: cog.over > 0 },
      { v: fmt(cog.max), l: "max cognitive", over: cog.max > cogT },
      { v: avg == null ? "—" : avg.toFixed(2), l: "avg name clarity", over: avg != null && avg < SOFT.name_clarity_floor },
      { v: anti, l: "naming antipatterns", over: anti > 0 },
    ];
  }
  function catMetricsSolid() {
    const b = buckets.solid;
    const off = valuesOf(b, "distance_from_main_sequence").filter((v) => v > SOFT.distance_tolerance).length;
    const ca = valuesOf(b, "afferent_coupling");
    const inst = valuesOf(b, "instability");
    const dit = valuesOf(b, "depth_of_inheritance_tree");
    return [
      { v: off, l: "modules off main-seq", over: off > 0 },
      { v: ca.length ? fmt(Math.max(...ca)) : "—", l: "max afferent (Ca)", over: false },
      { v: inst.length ? (inst.reduce((a, x) => a + x, 0) / inst.length).toFixed(2) : "—", l: "mean instability", over: false },
      { v: dit.length ? fmt(Math.max(...dit)) : "—", l: "max inheritance depth", over: false },
    ];
  }
  function catMetricsMixed() {
    const mi = fileStat("maintainability_index", null);
    const low = files.filter((f) => f.metrics.maintainability_index != null && f.metrics.maintainability_index < 50).length;
    const sri = valuesOf(buckets.mixed, "single_responsibility_index");
    const sriOut = sri.filter((v) => v > SOFT.single_responsibility_index).length;
    return [
      { v: low, l: "files MI < 50", over: low > 0 },
      { v: mi.min == null ? "—" : fmt(mi.min), l: "lowest MI", over: mi.min != null && mi.min < 50 },
      { v: sriOut, l: "SRI outliers (>5)", over: sriOut > 0 },
      { v: sri.length ? fmt(Math.max(...sri)) : "—", l: "max SRI", over: false },
    ];
  }
  const CAT_METRICS_FN = {
    loc: catMetricsLoc, complexity: catMetricsComplexity, readability: catMetricsReadability,
    solid: catMetricsSolid, mixed: catMetricsMixed,
  };
  function catMetrics(catId) {
    const fn = CAT_METRICS_FN[catId];
    return fn ? fn() : [];
  }
  function catCardHead(c, t, h, n) {
    const top = el("div", { class: "c-top" });
    const left = el("div");
    left.append(el("div", { class: "c-name" }, c.name));
    left.append(el("div", { class: "c-src" }, n ? `${c.src} · n=${n}` : (c.custom ? "custom analysis" : "unmeasured")));
    top.append(left);
    const st = el("span", { class: "status" });
    st.append(el("span", { class: "shape" }, SEV[t].glyph));
    st.append(document.createTextNode(SEV[t].word));
    top.append(st);
    return top;
  }
  function catCardScore(c, t, h) {
    const row = el("div", { class: "c-score-row" });
    const dialWrap = el("div", { class: "dial-wrap" });
    const dial = el("div", { class: "cat-dial" });
    const svg = svgEl("svg", { viewBox: "0 0 100 100" });
    dial.append(svg);
    const score = el("div", { class: "c-score" });
    score.append(el("b", null, h === null ? "n/a" : String(h)));
    score.append(el("span", null, h === null ? "unmeasured" : "/ 100"));
    dialWrap.append(dial); dialWrap.append(score);
    row.append(dialWrap);
    const gb = el("span", { class: "grade-badge" });
    gb.dataset.sev = t;
    gb.append(el("span", { class: "shape" }, SEV[t].glyph));
    gb.append(document.createTextNode(" " + grade(h)));
    row.append(gb);
    drawGauge(svg, h, focusedCat === c.id ? { r: 40, w: 11 } : { r: 38, w: 9 });
    return row;
  }
  function catCardMetrics(c) {
    const metrics = el("div", { class: "c-metrics" });
    for (const m of catMetrics(c.id)) {
      const cell = el("div", { class: "m" + (m.over ? " over" : "") });
      cell.append(el("div", { class: "mv" }, String(m.v)));
      cell.append(el("div", { class: "ml" }, m.l));
      metrics.append(cell);
    }
    return metrics;
  }
  function catCardDrill(card, c) {
    if (c.id !== "loc" && c.id !== "solid") return;
    const drill = el("div", { class: "c-drill", hidden: "" });
    const btn = el("button", { class: "c-more", type: "button", "data-drill": c.id }, "details ›");
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const open = drill.hasAttribute("hidden");
      if (!open) { drill.setAttribute("hidden", ""); btn.textContent = "details ›"; return; }
      drill.removeAttribute("hidden"); btn.textContent = "hide ‹";
      if (c.id === "loc") drawSizeStrip(drill); else drawArchQuadrant(drill);
    });
    card.append(btn);
    card.append(drill);
  }
  function catCard(c) {
    const h = HEALTH[c.id].health, n = HEALTH[c.id].n, t = tier(h);
    const focusable = n > 0;
    const card = el("div", { class: "card cat" });
    card.dataset.cat = c.id; card.dataset.sev = t;
    if (focusedCat === c.id) card.classList.add("focused");
    card.append(el("span", { class: "accent-edge" }));
    card.append(catCardHead(c, t, h, n));
    card.append(catCardScore(c, t, h));
    if (!focusable) {
      card.classList.add("unmeasured");
      card.append(el("div", { class: "c-note" }, c.note || (c.needs ? `Unmeasured — needs ${c.needs}.` : "No data for this run.")));
      return card;
    }
    card.append(catCardMetrics(c));
    catCardDrill(card, c);
    card.classList.add("clickable");
    card.title = focusedCat === c.id ? "Click to clear focus" : `Focus on ${c.name}`;
    card.addEventListener("click", () => setFocus(focusedCat === c.id ? null : c.id));
    return card;
  }
  function renderCategoryGrid() {
    const grid = byId("cat-grid");
    clear(grid);
    grid.classList.toggle("focused", focusedCat !== null);
    const list = focusedCat ? CATS.filter((c) => c.id === focusedCat) : CATS;
    for (const c of list) grid.append(catCard(c));
  }

  function drawSizeStrip(container) {
    clear(container);
    const slocs = files.map((f, i) => ({ i, v: f.metrics.source_lines_of_code })).filter((x) => x.v != null);
    if (!slocs.length) { container.append(el("p", { class: "drill-note" }, "No SLOC data.")); return; }
    const max = Math.max(...slocs.map((x) => x.v));
    const strip = el("div", { class: "dotstrip" });
    strip.append(el("div", { class: "axis" }));
    for (const x of slocs) {
      const p = pressure(x.v, SOFT.source_lines_of_code, "max");
      const t = p > 1 ? "bad" : p > 0.7 ? "warn" : "good";
      const dot = el("span", { class: "dot" });
      dot.style.left = `${(x.v / max) * 100}%`;
      dot.style.background = cssVar("--sev-" + t);
      dot.title = `${files[x.i].path} — ${fmt(x.v)} SLOC`;
      dot.addEventListener("click", () => { selectFile(x.i, null); scrollToDetail(); });
      dot.style.cursor = "pointer";
      strip.append(dot);
    }
    container.append(strip);
    container.append(el("p", { class: "drill-note" }, `one dot per file · position = SLOC / ${fmt(max)} (largest) · color = size pressure`));
  }

  function drawArchQuadrant(container) {
    clear(container);
    const b = buckets.solid;
    const bySubj = {};
    for (const u of b) {
      if (u.type !== "instability" && u.type !== "abstractness") continue;
      (bySubj[u.subject] = bySubj[u.subject] || {})[u.type] = u.value;
    }
    const pts = Object.entries(bySubj).map(([s, o]) => ({ s, x: o.instability, y: o.abstractness }))
      .filter((p) => p.x != null && p.y != null);
    if (!pts.length) { container.append(el("p", { class: "drill-note" }, "No instability/abstractness data.")); return; }
    const W = 240, H = 160, pad = 18;
    const svg = svgEl("svg", { class: "drill-svg", viewBox: `0 0 ${W} ${H}` });
    const px = (x) => pad + x * (W - 2 * pad);
    const py = (y) => (H - pad) - y * (H - 2 * pad);
    // frame
    svg.appendChild(svgEl("rect", { x: pad, y: pad, width: W - 2 * pad, height: H - 2 * pad, fill: "none", stroke: cssVar("--line") }));
    // main sequence diagonal (A + I = 1)
    svg.appendChild(svgEl("line", { x1: px(0), y1: py(1), x2: px(1), y2: py(0), stroke: cssVar("--faint"), "stroke-dasharray": "4 3" }));
    for (const p of pts) {
      const d = Math.abs(p.x + p.y - 1);
      const t = d > SOFT.distance_tolerance ? "bad" : d > 0.3 ? "warn" : "good";
      const c = svgEl("circle", { cx: px(p.x), cy: py(p.y), r: 4, fill: cssVar("--sev-" + t), stroke: cssVar("--surface"), "stroke-width": 1 });
      c.appendChild(svgEl("title", {}));
      c.lastChild.textContent = `${p.s} — I=${fmt(p.x)} A=${fmt(p.y)} D=${fmt(d)}`;
      svg.appendChild(c);
    }
    const l1 = svgEl("text", { x: px(0.04), y: py(0.06) }); l1.textContent = "zone of pain";
    const l2 = svgEl("text", { x: px(0.62), y: py(0.94) }); l2.textContent = "zone of uselessness";
    svg.appendChild(l1); svg.appendChild(l2);
    container.append(svg);
    container.append(el("p", { class: "drill-note" }, "x = instability · y = abstractness · dashed = main sequence (A+I=1)"));
  }

  // ===== treemap ===========================================================
  const svgTM = d3.select("#treemap");
  const WIDTH = 960, HEIGHT = 560;
  let leafSelection = null, selectedTile = null;

  let RAMP, REGRESS, IMPROVE, NEUTRAL_FILL, NEW_FILE_FILL, UNCHANGED_FILL;
  function refreshRamps() {
    RAMP = d3.scaleLinear().domain([0, 0.55, 0.85, 1.15])
      .range([cssVar("--sev-good"), cssVar("--sev-ok"), cssVar("--sev-warn"), cssVar("--sev-bad")]).clamp(true);
    REGRESS = d3.scaleLinear().domain([0, 1]).range([cssVar("--surface-2"), cssVar("--sev-bad")]).clamp(true);
    IMPROVE = d3.scaleLinear().domain([0, 1]).range([cssVar("--surface-2"), cssVar("--sev-good")]).clamp(true);
    NEUTRAL_FILL = cssVar("--sev-none-soft");
    NEW_FILE_FILL = cssVar("--accent-soft");
    UNCHANGED_FILL = cssVar("--line-2");
  }

  const deltaScaleCache = {};
  function deltaScale(metricKey) {
    if (!(metricKey in deltaScaleCache)) {
      let max = 0;
      for (const deltas of Object.values(baseline.file_deltas)) {
        const dd = deltas[metricKey];
        if (dd !== undefined && dd !== null) max = Math.max(max, Math.abs(dd));
      }
      deltaScaleCache[metricKey] = max;
    }
    return deltaScaleCache[metricKey];
  }
  function baselineDelta(fileEntry, metricKey) {
    const deltas = baseline.file_deltas[fileEntry.path];
    return deltas ? deltas[metricKey] : undefined;
  }
  function deltaFill(fileEntry, metricKey) {
    if (baselineAddedFiles.has(fileEntry.path)) return NEW_FILE_FILL;
    const dm = metricKey === PRESSURE_METRIC ? "cyclomatic_complexity" : metricKey;
    const delta = baselineDelta(fileEntry, dm);
    if (delta === undefined || delta === null || delta === 0) return UNCHANGED_FILL;
    const th = thresholds[dm];
    const worse = th && th.direction === "min" ? -delta : delta;
    const scale = deltaScale(dm);
    const intensity = scale > 0 ? Math.abs(worse) / scale : 0;
    return worse > 0 ? REGRESS(intensity) : IMPROVE(intensity);
  }
  function metricTileFill(fileEntry, metricKey) {
    if (metricKey === PRESSURE_METRIC) {
      const p = focusedCat ? filePressureForCat(fileEntry, focusedCat) : filePressure(fileEntry);
      return p === null ? NEUTRAL_FILL : RAMP(p);
    }
    const value = fileEntry ? fileEntry.metrics[metricKey] : undefined;
    if (value === undefined || value === null) return NEUTRAL_FILL;
    return RAMP(badness(metricKey, value));
  }
  function currentTileFill(fileEntry, metricKey) {
    if (baselineMode && baseline) return deltaFill(fileEntry, metricKey);
    return metricTileFill(fileEntry, metricKey);
  }

  function buildHierarchy() {
    const rootNode = d3.stratify().id((d) => d.id).parentId((d) => d.parent)(DATA.treemap);
    rootNode.sum((d) => d.value || 0);
    rootNode.sort((a, b) => b.value - a.value);
    d3.treemap().size([WIDTH, HEIGHT]).paddingInner(2)
      .paddingTop((d) => (d.depth > 0 ? 16 : 4)).paddingLeft(3).paddingRight(3).paddingBottom(3).round(true)(rootNode);
    return rootNode;
  }
  function renderTreemap(selectedMetric) {
    refreshRamps();
    clear(svgTM.node());
    if (!files.length || !DATA.treemap || !DATA.treemap.length) {
      svgTM.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40).text("No analyzable files found.");
      return;
    }
    let rootNode;
    try { rootNode = buildHierarchy(); }
    catch (err) {
      svgTM.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40).text(`Treemap error: ${err.message}`);
      return;
    }
    const dirs = rootNode.descendants().filter((d) => d.children && d.depth > 0);
    const dirGroups = svgTM.selectAll("g.dir").data(dirs).join("g").attr("class", "dir");
    dirGroups.append("rect").attr("class", "dir-rect")
      .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
      .attr("width", (d) => Math.max(0, d.x1 - d.x0)).attr("height", (d) => Math.max(0, d.y1 - d.y0))
      .on("mousemove", (event, d) => showDirTooltip(event, d, selectedMetricNow())).on("mouseleave", hideTooltip);
    dirGroups.append("text").attr("class", "dir-label")
      .attr("x", (d) => d.x0 + 4).attr("y", (d) => d.y0 + 12).text((d) => truncate(d.data.label, d.x1 - d.x0 - 8));

    const leaves = rootNode.leaves().filter((d) => d.data.file_index !== undefined && d.data.file_index !== null);
    const groups = svgTM.selectAll("g.leaf").data(leaves).join("g").attr("class", "leaf");
    leafSelection = groups.append("rect").attr("class", "tile")
      .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
      .attr("width", (d) => Math.max(0, d.x1 - d.x0)).attr("height", (d) => Math.max(0, d.y1 - d.y0))
      .attr("fill", (d) => currentTileFill(files[d.data.file_index], selectedMetric))
      .on("mousemove", (event, d) => showTooltip(event, files[d.data.file_index], selectedMetricNow())).on("mouseleave", hideTooltip)
      .on("click", (event, d) => selectFile(d.data.file_index, event.currentTarget));

    groups.filter((d) => d.x1 - d.x0 > 56 && d.y1 - d.y0 > 16).append("text").attr("class", "tile-label")
      .attr("x", (d) => d.x0 + 4).attr("y", (d) => d.y0 + 12).text((d) => truncate(d.data.label, d.x1 - d.x0 - 8));

    const badged = groups.filter((d) => (files[d.data.file_index].violations || []).length > 0);
    badged.append("circle").attr("class", "badge").attr("cx", (d) => d.x1 - 9).attr("cy", (d) => d.y0 + 9).attr("r", 7);
    badged.append("text").attr("class", "badge-text").attr("x", (d) => d.x1 - 9).attr("y", (d) => d.y0 + 12)
      .text((d) => files[d.data.file_index].violations.length);

    // re-mark the currently selected tile after a re-render.
    if (currentSelectedIndex !== null) {
      leafSelection.filter((d) => d.data.file_index === currentSelectedIndex).each(function () {
        selectedTile = this; this.classList.add("selected");
      });
    }
  }
  function truncate(label, width) {
    const maxChars = Math.floor(width / 6.2);
    if (maxChars <= 1) return "";
    return label.length > maxChars ? label.slice(0, Math.max(1, maxChars - 1)) + "…" : label;
  }
  function recolorTreemap(selectedMetric) {
    refreshRamps();
    if (leafSelection) leafSelection.attr("fill", (d) => currentTileFill(files[d.data.file_index], selectedMetric));
  }

  // ===== dependency graph (SOLID focus) ===================================
  // Relational metrics (coupling, instability) don't aggregate by area, so
  // SOLID gets a force-directed module graph instead of the treemap. Nodes are
  // grouped by package and collapse/expand for the layered-architecture drill:
  // start at high-level components, click a dashed node to open its submodules.
  function orEmptyGraph(g) { return g && g.edges ? g : { modules: {}, edges: [] }; }
  const importGraph = orEmptyGraph(DATA.import_graph);
  const GW = 960, GH = 560;

  function commonPrefix(names) {
    if (!names.length) return "";
    let parts = names[0].split(".");
    for (const n of names) {
      const p = n.split(".");
      let i = 0;
      while (i < parts.length && i < p.length && parts[i] === p[i]) i++;
      parts = parts.slice(0, i);
    }
    return parts.join(".");
  }
  const graphRoot = commonPrefix(Object.keys(importGraph.modules));
  let graphExpanded = new Set();
  let graphMode = "graph";

  function visibleNode(module) {
    const parts = module.split(".");
    let prefix = parts[0];
    for (let i = 1; i < parts.length; i++) {
      if (!graphExpanded.has(prefix)) return prefix;
      prefix += "." + parts[i];
    }
    return prefix;
  }
  function solidMetric(subject, type) {
    for (const u of buckets.solid) if (u.subject === subject && u.type === type) return u.value;
    return null;
  }
  function meanMemberMetric(members, type) {
    const vals = members.map((m) => solidMetric(m, type)).filter((v) => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }
  // members = the modules that collapse into this visible node (one per module),
  // so a package's size/aggregates never double-count its own visible children.
  function graphNode(id, members) {
    const sloc = members.reduce((s, m) => s + (importGraph.modules[m].sloc || 0), 0);
    const dist = solidMetric(id, "distance_from_main_sequence");
    const inst = solidMetric(id, "instability");
    return {
      id, members: members.length, sloc,
      expandable: members.length > 1 || members[0] !== id,
      dist: dist != null ? dist : meanMemberMetric(members, "distance_from_main_sequence"),
      inst: inst != null ? inst : meanMemberMetric(members, "instability"),
      abst: solidMetric(id, "abstractness"),
      ce: solidMetric(id, "efferent_coupling"), ca: solidMetric(id, "afferent_coupling"),
    };
  }
  function graphModel() {
    const membersByNode = new Map();
    for (const m of Object.keys(importGraph.modules)) {
      const v = visibleNode(m);
      if (!membersByNode.has(v)) membersByNode.set(v, []);
      membersByNode.get(v).push(m);
    }
    const nodes = [...membersByNode].map(([id, members]) => graphNode(id, members));
    const linkMap = new Map();
    for (const [s, t] of importGraph.edges) {
      const a = visibleNode(s), b = visibleNode(t);
      if (a === b) continue;
      const key = a + " " + b;
      const cur = linkMap.get(key) || { source: a, target: b, weight: 0 };
      cur.weight++;
      linkMap.set(key, cur);
    }
    return { nodes, links: [...linkMap.values()] };
  }
  function nodeRadius(d) { return clamp(Math.sqrt(Math.max(1, d.sloc)) * 0.9, 7, 46); }
  function distSeverity(d) {
    if (d == null) return "none";
    if (d > SOFT.distance_tolerance) return "bad";
    if (d > 0.3) return "warn";
    return "good";
  }
  function runGraphSim(model) {
    const sim = d3.forceSimulation(model.nodes)
      .force("link", d3.forceLink(model.links).id((d) => d.id).distance(92).strength(0.35))
      .force("charge", d3.forceManyBody().strength(-280))
      .force("center", d3.forceCenter(GW / 2, GH / 2))
      .force("collide", d3.forceCollide().radius((d) => nodeRadius(d) + 7))
      .stop();
    for (let i = 0; i < 240; i++) sim.tick();
  }
  function drawGraphDefs(svg) {
    const marker = svg.append("defs").append("marker")
      .attr("id", "dep-arrow").attr("viewBox", "0 -5 10 10").attr("refX", 9).attr("refY", 0)
      .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto");
    marker.append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", cssVar("--faint"));
  }
  function linkIsSdv(l) {
    return l.source.inst != null && l.target.inst != null && l.target.inst - l.source.inst > 0.2;
  }
  function linkPath(l) {
    const s = l.source, t = l.target;
    const dx = t.x - s.x, dy = t.y - s.y, len = Math.hypot(dx, dy) || 1;
    const tr = nodeRadius(t) + 8;
    const ex = t.x - (dx / len) * tr, ey = t.y - (dy / len) * tr;
    return `M${s.x.toFixed(1)},${s.y.toFixed(1)} L${ex.toFixed(1)},${ey.toFixed(1)}`;
  }
  function drawGraphLinks(svg, links) {
    const maxW = Math.max(1, ...links.map((l) => l.weight));
    svg.append("g").selectAll("path").data(links).join("path")
      .attr("class", (l) => "dep-link" + (linkIsSdv(l) ? " sdv" : ""))
      .attr("stroke-width", (l) => 0.8 + (l.weight / maxW) * 3.6)
      .attr("marker-end", "url(#dep-arrow)")
      .attr("d", linkPath);
  }
  function graphNodeLabel(d) {
    const short = d.id.split(".").pop();
    return short.length > 15 ? short.slice(0, 14) + "…" : short;
  }
  function drawGraphNodes(svg, nodes) {
    const g = svg.append("g").selectAll("g").data(nodes).join("g")
      .attr("class", (d) => "dep-node" + (d.expandable ? " group" : ""))
      .attr("transform", (d) => `translate(${d.x.toFixed(1)},${d.y.toFixed(1)})`)
      .on("mousemove", (e, d) => showGraphTooltip(e, d))
      .on("mouseleave", hideTooltip)
      .on("click", (e, d) => onGraphNodeClick(d));
    g.append("circle").attr("r", nodeRadius).attr("fill", (d) => cssVar("--sev-" + distSeverity(d.dist)));
    g.filter((d) => nodeRadius(d) > 13).append("text")
      .attr("text-anchor", "middle").attr("dy", "0.32em").text(graphNodeLabel);
  }
  function onGraphNodeClick(d) {
    if (!d.expandable) return;
    graphExpanded.add(d.id);
    renderDepGraph();
  }
  function resetGraph() {
    graphExpanded = new Set(graphRoot ? [graphRoot] : []);
    renderDepGraph();
  }
  function graphTooltipRow(table, key, value) {
    const tr = el("tr");
    tr.append(el("td", null, key));
    tr.append(el("td", null, value));
    table.append(tr);
  }
  function showGraphTooltip(event, d) {
    clear(tooltip);
    tooltip.append(el("div", { class: "tt-path" }, d.id));
    const table = el("table");
    if (d.members > 1) graphTooltipRow(table, "Modules", String(d.members));
    graphTooltipRow(table, "SLOC", fmt(d.sloc));
    for (const [label, v] of [["Instability", d.inst], ["Abstractness", d.abst],
      ["Distance (D)", d.dist], ["Efferent (Ce)", d.ce], ["Afferent (Ca)", d.ca]]) {
      if (v != null) graphTooltipRow(table, label, fmt(v));
    }
    tooltip.append(table);
    if (d.expandable) tooltip.append(el("div", { class: "tt-note" }, "Click to drill into submodules"));
    tooltip.hidden = false;
    positionTooltip(event);
  }
  function renderDepGraph() {
    const svg = d3.select("#depgraph");
    clear(svg.node());
    refreshRamps();
    const model = graphModel();
    if (!model.nodes.length) {
      svg.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40)
        .text("No dependency data — needs Python import facts.");
      updateGraphChrome();
      return;
    }
    runGraphSim(model);
    drawGraphDefs(svg);
    drawGraphLinks(svg, model.links);
    drawGraphNodes(svg, model.nodes);
    updateGraphChrome();
  }
  function mainSeqPoints() {
    const by = {};
    for (const u of buckets.solid) {
      if (u.type !== "instability" && u.type !== "abstractness") continue;
      (by[u.subject] = by[u.subject] || {})[u.type] = u.value;
    }
    return Object.entries(by).map(([s, o]) => ({ s, x: o.instability, y: o.abstractness }))
      .filter((p) => p.x != null && p.y != null);
  }
  function drawMainSeqFrame(svg, px, py) {
    svg.append("rect").attr("x", px(0)).attr("y", py(1)).attr("width", px(1) - px(0))
      .attr("height", py(0) - py(1)).attr("fill", "none").attr("stroke", cssVar("--line"));
    svg.append("line").attr("x1", px(0)).attr("y1", py(1)).attr("x2", px(1)).attr("y2", py(0))
      .attr("stroke", cssVar("--faint")).attr("stroke-dasharray", "6 4");
    svg.append("text").attr("x", px(0.02)).attr("y", py(0.05)).attr("class", "empty-note")
      .attr("font-size", 12).text("zone of pain");
    svg.append("text").attr("x", px(0.7)).attr("y", py(0.96)).attr("class", "empty-note")
      .attr("font-size", 12).text("zone of uselessness");
  }
  function drawMainSeqPoints(svg, pts, px, py) {
    const g = svg.append("g").selectAll("g").data(pts).join("g")
      .attr("transform", (p) => `translate(${px(p.x).toFixed(1)},${py(p.y).toFixed(1)})`);
    g.append("circle").attr("r", 5)
      .attr("fill", (p) => cssVar("--sev-" + distSeverity(Math.abs(p.x + p.y - 1))))
      .attr("stroke", cssVar("--surface")).attr("stroke-width", 1)
      .append("title").text((p) => `${p.s} — I=${fmt(p.x)} A=${fmt(p.y)} D=${fmt(Math.abs(p.x + p.y - 1))}`);
  }
  function renderMainSequence() {
    const svg = d3.select("#depgraph");
    clear(svg.node());
    const pts = mainSeqPoints();
    if (!pts.length) {
      svg.append("text").attr("class", "empty-note").attr("x", 24).attr("y", 40)
        .text("No instability / abstractness data.");
      updateGraphChrome();
      return;
    }
    const pad = 46;
    const px = (x) => pad + x * (GW - 2 * pad);
    const py = (y) => (GH - pad) - y * (GH - 2 * pad);
    drawMainSeqFrame(svg, px, py);
    drawMainSeqPoints(svg, pts, px, py);
    updateGraphChrome();
  }
  function renderGraphToggle() {
    const box = byId("graph-mode");
    if (!box) return;
    clear(box);
    for (const [id, label] of [["graph", "Graph"], ["sequence", "Main sequence"]]) {
      const b = el("button", { type: "button" }, label);
      if (graphMode === id) b.classList.add("active");
      b.addEventListener("click", () => { graphMode = id; renderGraphMode(); });
      box.append(b);
    }
  }
  function renderGraphLegend() {
    const box = byId("graph-legend");
    if (!box) return;
    clear(box);
    const items = graphMode === "sequence"
      ? [["good", "near main sequence"], ["warn", "drifting"], ["bad", "zone of pain/uselessness"]]
      : [["good", "stable"], ["warn", "drifting"], ["bad", "off main sequence"]];
    for (const [sev, label] of items) {
      const gl = el("span", { class: "gl" });
      const dot = el("span", { class: "dot" });
      dot.style.background = cssVar("--sev-" + sev);
      gl.append(dot);
      gl.append(document.createTextNode(label));
      box.append(gl);
    }
    if (graphMode === "graph") renderGraphEdgeLegend(box);
  }
  function renderGraphEdgeLegend(box) {
    const gl = el("span", { class: "gl edge" });
    const dot = el("span", { class: "dot" });
    dot.style.background = cssVar("--sev-bad");
    gl.append(dot);
    gl.append(document.createTextNode("import → less-stable module"));
    box.append(gl);
  }
  function updateGraphChrome() {
    const btn = byId("graph-reset");
    if (btn) btn.hidden = graphMode !== "graph" || graphExpanded.size <= (graphRoot ? 1 : 0);
    const foot = byId("graph-foot");
    if (foot) {
      foot.textContent = graphMode === "sequence"
        ? "Each dot is a module: x = instability, y = abstractness. The dashed diagonal is Martin's main sequence (A + I = 1); distance from it is the SOLID pressure."
        : "Node area ∝ SLOC · color = distance from main sequence · arrows = imports · click a dashed (package) node to drill into its submodules.";
    }
  }
  function renderGraphMode() {
    renderGraphToggle();
    renderGraphLegend();
    if (graphMode === "sequence") renderMainSequence();
    else renderDepGraph();
  }
  function initGraph() {
    graphExpanded = new Set(graphRoot ? [graphRoot] : []);
    const btn = byId("graph-reset");
    if (btn) btn.addEventListener("click", resetGraph);
  }
  // Choose the right spatial viz for the current focus: treemap for everything
  // except SOLID (relational → dependency graph).
  function renderTreemapView() {
    const m = selectedMetricNow();
    renderTreemap(m);
    renderLegend(m);
    renderCoverageChips(m);
  }
  function renderSpatialViz() {
    const solid = focusedCat === "solid" && importGraph.edges.length > 0;
    byId("treemap-panel").hidden = solid;
    byId("graph-panel").hidden = !solid;
    byId("metric-picker-wrap").hidden = solid;
    byId("spatial-title").textContent = solid ? "Dependency map" : "Spatial map";
    const note = byId("spatial-note");
    if (note) note.hidden = solid;
    if (solid) renderGraphMode();
    else renderTreemapView();
  }

  // ===== coverage chips + legend ==========================================
  function renderCoverageChips(selectedMetric) {
    const box = byId("coverage-chips");
    clear(box);
    if (selectedMetric === PRESSURE_METRIC) return;
    for (const [lang, metrics] of Object.entries(coverage)) {
      const has = metrics.includes(selectedMetric);
      const chip = el("span", { class: `chip ${has ? "" : "missing"}` },
        has ? `${lang} · ${metrics.length} metrics` : `${lang} · no ${metricLabel(selectedMetric).toLowerCase()}`);
      chip.title = `${lang} coverage: ${metrics.map(metricLabel).join(", ")}`;
      box.append(chip);
    }
  }
  function renderLegend(selectedMetric) {
    const th = thresholds[selectedMetric];
    const low = byId("legend-low"), high = byId("legend-high"), bar = byId("legend-bar");
    bar.classList.toggle("delta", baselineMode && Boolean(baseline));
    byId("tm-metric-name").textContent = metricLabel(selectedMetric).toLowerCase();
    if (baselineMode && baseline) { low.textContent = "improved"; high.textContent = "regressed vs baseline"; return; }
    if (selectedMetric === PRESSURE_METRIC) { low.textContent = "safe"; high.textContent = "over threshold"; return; }
    if (th && th.threshold > 0) {
      low.textContent = th.direction === "min" ? "high (good)" : "low (good)";
      high.textContent = `${th.direction === "min" ? "below" : "over"} threshold (${fmt(th.threshold)})`;
    } else { low.textContent = "low"; high.textContent = "high (relative scale, no threshold)"; }
  }

  // ===== tooltip ===========================================================
  const tooltip = byId("tooltip");
  function tooltipMetricsTable(fileEntry) {
    const table = el("table");
    const addRow = (label, value, over) => {
      const tr = el("tr");
      tr.append(el("td", null, label));
      const td = el("td", over ? { class: "over" } : null, value);
      tr.append(td); table.append(tr);
    };
    addRow("Language", fileEntry.language);
    for (const key of CANONICAL_METRICS) {
      if (key in fileEntry.metrics) addRow(metricLabel(key), fmt(fileEntry.metrics[key]), isOverThreshold(key, fileEntry.metrics[key]));
    }
    return table;
  }
  function baselineTooltipNote(fileEntry, selectedMetric) {
    if (!baselineMode || !baseline) return null;
    if (baselineAddedFiles.has(fileEntry.path)) return el("div", { class: "tt-note" }, "New file — not in baseline");
    const dm = selectedMetric === PRESSURE_METRIC ? "cyclomatic_complexity" : selectedMetric;
    const delta = baselineDelta(fileEntry, dm);
    const label = metricLabel(dm).toLowerCase();
    return el("div", { class: "tt-note" },
      delta === undefined || delta === null ? `No ${label} change vs baseline` : `Δ ${label} vs baseline: ${fmtDelta(delta)}`);
  }
  function positionTooltip(event) {
    const pad = 14, rect = tooltip.getBoundingClientRect();
    let x = event.clientX + pad, y = event.clientY + pad;
    if (x + rect.width > window.innerWidth - 8) x = event.clientX - rect.width - pad;
    if (y + rect.height > window.innerHeight - 8) y = event.clientY - rect.height - pad;
    tooltip.style.left = `${Math.max(4, x)}px`;
    tooltip.style.top = `${Math.max(4, y)}px`;
  }
  function showDirTooltip(event, node, selectedMetric) {
    const agg = node.data.aggregate;
    if (!agg) return;
    clear(tooltip);
    tooltip.append(el("div", { class: "tt-path" }, node.data.parent === null ? node.data.label : node.data.id));
    const table = el("table");
    const addRow = (label, value, over) => {
      const tr = el("tr"); tr.append(el("td", null, label));
      tr.append(el("td", over ? { class: "over" } : null, value)); table.append(tr);
    };
    addRow("Files", String(agg.files));
    addRow("Total size", `${fmt(agg.value)} lines`);
    if (agg.violations > 0) addRow("Violations", String(agg.violations));
    const worstKey = selectedMetric === PRESSURE_METRIC ? "cyclomatic_complexity" : selectedMetric;
    const worst = agg.metrics_max ? agg.metrics_max[worstKey] : undefined;
    if (worst) addRow(`Worst ${metricLabel(worstKey).toLowerCase()}`, `${fmt(worst.value)} — ${baseName(worst.path)}`, isOverThreshold(worstKey, worst.value));
    tooltip.append(table);
    if (agg.violations > 0) tooltip.append(el("div", { class: "tt-alert" }, `${agg.violations} threshold violation(s) in this directory`));
    tooltip.hidden = false; positionTooltip(event);
  }
  function showTooltip(event, fileEntry, selectedMetric) {
    clear(tooltip);
    tooltip.append(el("div", { class: "tt-path" }, fileEntry.path));
    tooltip.append(tooltipMetricsTable(fileEntry));
    const note = baselineTooltipNote(fileEntry, selectedMetric);
    if (note) tooltip.append(note);
    if (selectedMetric !== PRESSURE_METRIC && !(selectedMetric in fileEntry.metrics))
      tooltip.append(el("div", { class: "tt-note" }, `No ${metricLabel(selectedMetric).toLowerCase()} data for ${fileEntry.language} — shown neutral`));
    if ((fileEntry.violations || []).length) tooltip.append(el("div", { class: "tt-alert" }, `${fileEntry.violations.length} threshold violation(s)`));
    if (fileEntry.error) tooltip.append(el("div", { class: "tt-alert" }, `Analysis error: ${fileEntry.error}`));
    tooltip.hidden = false; positionTooltip(event);
  }
  function hideTooltip() { tooltip.hidden = true; }

  // ===== deltas / sortable tables =========================================
  function fmtDelta(value) {
    if (value === null || value === undefined) return "—";
    const text = fmt(Math.abs(value));
    return value >= 0 ? `+${text}` : `−${text}`;
  }
  function renderSortableTable(table, columns, rows, onRowClick) {
    const state = { key: null, desc: true };
    const renderHead = () => {
      const thead = table.querySelector("thead"); clear(thead);
      const tr = el("tr");
      for (const col of columns) {
        const th = el("th", { class: col.numeric ? "num" : "" }, col.label);
        if (state.key === col.key) th.append(el("span", { class: "arrow" }, state.desc ? "▼" : "▲"));
        th.addEventListener("click", () => {
          state.desc = state.key === col.key ? !state.desc : true; state.key = col.key; renderBody(); renderHead();
        });
        tr.append(th);
      }
      thead.append(tr);
    };
    const compareRows = (a, b) => {
      const av = a[state.key], bv = b[state.key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const dir = state.desc ? -1 : 1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    };
    const cellText = (col, value) => col.delta ? fmtDelta(value) : (col.numeric ? fmt(value) : (value ?? "—"));
    const buildCell = (col, value) => {
      const td = el("td", { class: col.numeric ? "num" : "" }, cellText(col, value));
      if (col.metric && isOverThreshold(col.metric, value)) td.classList.add("cell-over");
      if (col.delta && typeof value === "number" && value !== 0) td.classList.add(value > 0 ? "delta-pos" : "delta-neg");
      return td;
    };
    const buildRow = (row) => {
      const tr = el("tr");
      for (const col of columns) tr.append(buildCell(col, row[col.key]));
      if (onRowClick) tr.addEventListener("click", () => onRowClick(row));
      return tr;
    };
    const renderBody = () => {
      const tbody = table.querySelector("tbody"); clear(tbody);
      const sorted = [...rows];
      if (state.key !== null) sorted.sort(compareRows);
      for (const row of sorted) tbody.append(buildRow(row));
    };
    renderHead(); renderBody();
  }

  // ===== detail panel ======================================================
  let currentSelectedIndex = null;
  function scrollToDetail() { byId("detail-panel").scrollIntoView({ behavior: "smooth", block: "nearest" }); }
  function markSelectedTile(fileIndex, tileNode) {
    if (selectedTile) selectedTile.classList.remove("selected");
    selectedTile = null;
    if (tileNode) { selectedTile = tileNode; selectedTile.classList.add("selected"); }
    else if (leafSelection) {
      leafSelection.filter((d) => d.data.file_index === fileIndex).each(function () { selectedTile = this; this.classList.add("selected"); });
    }
  }
  function renderDetailMeta(fileEntry) {
    const meta = byId("detail-meta"); clear(meta);
    for (const key of CANONICAL_METRICS) {
      if (!(key in fileEntry.metrics)) continue;
      meta.append(el("span", { class: "k" }, metricLabel(key)));
      const v = el("span", { class: "v" }, fmt(fileEntry.metrics[key]));
      if (isOverThreshold(key, fileEntry.metrics[key])) v.classList.add("cell-over");
      meta.append(v);
    }
  }
  function renderDetailViolations(fileEntry) {
    const violationsBox = byId("detail-violations"); clear(violationsBox);
    if ((fileEntry.violations || []).length) {
      const ul = el("ul", { class: "violation-list" });
      for (const violation of fileEntry.violations) ul.append(el("li", null, violation.message));
      violationsBox.append(ul);
    }
    if (fileEntry.error) violationsBox.append(el("p", { class: "violation-list" }, `Analysis error: ${fileEntry.error}`));
  }
  function renderDetailFunctions(fileEntry) {
    const rows = (fileEntry.functions || []).map((fn) => ({
      name: fn.name, line: fn.line,
      cyclomatic_complexity: fn.metrics.cyclomatic_complexity ?? null,
      cognitive_complexity: fn.metrics.cognitive_complexity ?? null,
      halstead_volume: fn.metrics.halstead_volume ?? null,
      halstead_difficulty: fn.metrics.halstead_difficulty ?? null,
    }));
    renderSortableTable(byId("function-table"), [
      { key: "name", label: "Function" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyclomatic_complexity", label: "Cyc", numeric: true, metric: "cyclomatic_complexity" },
      { key: "cognitive_complexity", label: "Cog", numeric: true, metric: "cognitive_complexity" },
      { key: "halstead_volume", label: "Volume", numeric: true },
      { key: "halstead_difficulty", label: "Difficulty", numeric: true },
    ], rows);
  }
  function selectFile(fileIndex, tileNode) {
    currentSelectedIndex = fileIndex;
    markSelectedTile(fileIndex, tileNode);
    const fileEntry = files[fileIndex];
    byId("detail-section").hidden = false;
    byId("detail-placeholder").hidden = true;
    byId("detail-body").hidden = false;
    byId("detail-path").textContent = `${fileEntry.path} (${fileEntry.language})`;
    renderDetailMeta(fileEntry);
    renderDetailViolations(fileEntry);
    renderDetailFunctions(fileEntry);
  }

  // ===== hotspots + arch watchlist + risk breakdown ========================
  function collectWorst() {
    const rows = [];
    files.forEach((fileEntry, index) => {
      for (const fn of fileEntry.functions || []) {
        const cyc = fn.metrics.cyclomatic_complexity, cog = fn.metrics.cognitive_complexity;
        const candidates = [cyc, cog].filter((v) => v !== undefined && v !== null);
        if (!candidates.length) continue;
        rows.push({
          score: Math.max(...candidates), name: fn.name, path: fileEntry.path, line: fn.line,
          cyclomatic_complexity: cyc ?? null, cognitive_complexity: cog ?? null,
          halstead_volume: fn.metrics.halstead_volume ?? null, fileIndex: index,
        });
      }
    });
    rows.sort((a, b) => b.score - a.score || a.path.localeCompare(b.path));
    return rows;
  }
  function renderWorstFunctions() {
    const rows = collectWorst();
    const top = rows.slice(0, 50);
    byId("worst-total").textContent = rows.length > 50 ? `(top 50 of ${rows.length})` : `(${rows.length})`;
    renderSortableTable(byId("worst-table"), [
      { key: "score", label: "Score", numeric: true },
      { key: "name", label: "Function" },
      { key: "path", label: "File" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyclomatic_complexity", label: "Cyc", numeric: true, metric: "cyclomatic_complexity" },
      { key: "cognitive_complexity", label: "Cog", numeric: true, metric: "cognitive_complexity" },
      { key: "halstead_volume", label: "Volume", numeric: true },
    ], top, (row) => { selectFile(row.fileIndex, null); scrollToDetail(); });

    // hotspots rail — top 6.
    const box = byId("hotspots"); clear(box);
    byId("worst-count").textContent = rows.length ? `${Math.min(6, rows.length)} of ${rows.length}` : "";
    if (!rows.length) { box.append(el("div", { class: "rank-empty" }, "No function complexity data.")); return; }
    const rank = el("div", { class: "rank" });
    for (const r of rows.slice(0, 6)) {
      const t = r.score > 15 ? "bad" : r.score > 10 ? "warn" : "good";
      const row = el("div", { class: "rank-row" }); row.dataset.sev = t;
      row.append(el("span", { class: "r-dot" }));
      const main = el("div", { class: "r-main" });
      main.append(el("div", { class: "r-name" }, r.name));
      main.append(el("div", { class: "r-sub" }, `${baseName(r.path)}:${r.line}`));
      row.append(main);
      row.append(el("span", { class: "r-val" }, fmt(r.score)));
      row.title = `${r.path}:${r.line} — cyc ${fmt(r.cyclomatic_complexity)} · cog ${fmt(r.cognitive_complexity)}`;
      row.addEventListener("click", () => { selectFile(r.fileIndex, null); scrollToDetail(); });
      rank.append(row);
    }
    box.append(rank);
  }
  function renderArchWatchlist() {
    const box = byId("archlist"); clear(box);
    const dist = buckets.solid.filter((u) => u.type === "distance_from_main_sequence" && u.value != null)
      .sort((a, b) => b.value - a.value).slice(0, 6);
    if (!dist.length) {
      box.append(el("div", { class: "rank-empty" }, project.length ? "No main-sequence data." : "n/a — no architecture data for this project."));
      return;
    }
    const rank = el("div", { class: "rank" });
    for (const u of dist) {
      const t = u.value > SOFT.distance_tolerance ? (u.value >= 0.9 ? "bad" : "warn") : "good";
      const row = el("div", { class: "rank-row" }); row.dataset.sev = t;
      row.append(el("span", { class: "r-dot" }));
      const main = el("div", { class: "r-main" });
      main.append(el("div", { class: "r-name" }, baseName(u.subject.replace(/\./g, "/"))));
      main.append(el("div", { class: "r-sub" }, u.subject));
      row.append(main);
      row.append(el("span", { class: "r-val" }, "D " + fmt(u.value)));
      row.title = `${u.subject} — distance from main sequence ${fmt(u.value)}`;
      rank.append(row);
    }
    box.append(rank);
  }
  function renderRiskBreakdown() {
    const box = byId("viol-break"); clear(box);
    const byType = summary.violations_by_type || {};
    const entries = Object.entries(byType)
      .filter(([type]) => !focusedCat || categoryOf(type) === focusedCat)
      .sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
      box.append(el("div", { class: "rank-empty" },
        focusedCat ? `No ${CAT_BY_ID[focusedCat].name} violations.` : "No threshold violations."));
      return;
    }
    const max = Math.max(...entries.map((e) => e[1]));
    for (const [type, count] of entries) {
      const row = el("div", { class: "vb-row" });
      row.append(el("div", { class: "vb-lab" }, metricLabel(type)));
      row.append(el("div", { class: "vb-num" }, String(count)));
      const track = el("div", { class: "vb-track" });
      const fill = el("div", { class: "vb-fill" });
      fill.style.width = `${(count / max) * 100}%`;
      track.append(fill); row.append(track);
      box.append(row);
    }
  }

  // ===== baseline tables ===================================================
  function baselineFunctionRow(entry, pathIndex) {
    const cyc = entry.deltas.cyclomatic_complexity, cog = entry.deltas.cognitive_complexity;
    return {
      score_delta: entry.score_delta, name: (entry.new_violation ? "⚠ " : "") + entry.name,
      path: entry.path, line: entry.line,
      cyc_delta: cyc ? cyc.delta : null, cog_delta: cog ? cog.delta : null,
      fileIndex: pathIndex.has(entry.path) ? pathIndex.get(entry.path) : null,
    };
  }
  function renderBaselineFunctionTable(tableId, countId, entries, pathIndex) {
    const rows = entries.slice(0, 50).map((entry) => baselineFunctionRow(entry, pathIndex));
    byId(countId).textContent = entries.length > 50 ? `(top 50 of ${entries.length})` : `(${entries.length})`;
    renderSortableTable(byId(tableId), [
      { key: "score_delta", label: "Δ score", numeric: true, delta: true },
      { key: "name", label: "Function" },
      { key: "path", label: "File" },
      { key: "line", label: "Line", numeric: true },
      { key: "cyc_delta", label: "Δ cyc", numeric: true, delta: true },
      { key: "cog_delta", label: "Δ cog", numeric: true, delta: true },
    ], rows, (row) => { if (row.fileIndex === null) return; selectFile(row.fileIndex, null); scrollToDetail(); });
  }
  function renderBaselineTables() {
    if (!baseline) return;
    byId("regressions-section").hidden = false;
    const pathIndex = new Map(files.map((entry, index) => [entry.path, index]));
    renderBaselineFunctionTable("regressions-table", "regressions-count", baseline.regressions, pathIndex);
    renderBaselineFunctionTable("improvements-table", "improvements-count", baseline.improvements, pathIndex);
  }

  // ===== footer ============================================================
  function renderFooter() {
    byId("foot").textContent = `antipasta v${DATA.tool_version} · schema v${DATA.schema_version} · analyzed ${DATA.root} at ${DATA.generated_at}`;
  }

  // ===== theme toggle ======================================================
  function reRenderThemedVisuals() {
    drawGauge(byId("overall-gauge"), OVERALL, { r: 40, w: 10 });
    renderKPIs();
    renderCategoryGrid();
    renderSpatialViz();
    renderRiskBreakdown();
    renderArchWatchlist();
  }
  function initTheme() {
    const root = document.documentElement;
    try { const saved = localStorage.getItem("antipasta-theme"); if (saved) root.dataset.theme = saved; } catch (e) { /* offline / no storage */ }
    byId("theme-toggle").addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("antipasta-theme", next); } catch (e) { /* ignore */ }
      reRenderThemedVisuals();
    });
  }

  // ===== boot ==============================================================
  const metricSelect = byId("metric-select");
  function selectedMetricNow() { return metricSelect.value; }

  function availableMetrics() {
    const seen = new Set();
    for (const f of files) {
      for (const k of Object.keys(f.metrics)) seen.add(k);
      for (const fn of f.functions || []) for (const k of Object.keys(fn.metrics)) seen.add(k);
    }
    const ordered = CANONICAL_METRICS.filter((k) => seen.has(k));
    for (const k of [...seen].sort()) if (!ordered.includes(k)) ordered.push(k);
    return ordered;
  }

  // ===== focus mode ========================================================
  // Focusing a bucket scopes the treemap + color-by + fix list + risk to that
  // one category and collapses the grid to its dial; "All" restores the global
  // view. Buckets with no data (DRYness/Test quality/VCS) are non-focusable.
  function fileLevelMetricKeys() {
    const seen = new Set();
    for (const f of files) for (const k of Object.keys(f.metrics)) seen.add(k);
    return seen;
  }
  function focusMetricOptions() {
    if (!focusedCat) return [PRESSURE_METRIC, ...availableMetrics()];
    const inCat = [...fileLevelMetricKeys()].filter((k) => categoryOf(k) === focusedCat);
    const ordered = CANONICAL_METRICS.filter((k) => inCat.includes(k))
      .concat(inCat.filter((k) => !CANONICAL_METRICS.includes(k)).sort());
    return [PRESSURE_METRIC, ...ordered];
  }
  function focusOptionLabel(key) {
    if (key === PRESSURE_METRIC) return focusedCat ? `${CAT_BY_ID[focusedCat].name} pressure` : "Pressure (composite)";
    return metricLabel(key);
  }
  function rebuildMetricOptions() {
    clear(metricSelect);
    for (const key of focusMetricOptions()) metricSelect.append(el("option", { value: key }, focusOptionLabel(key)));
    metricSelect.value = PRESSURE_METRIC;
  }
  function focusPill(label, catId, active, disabled, title) {
    const pill = el("button", { class: "fpill", type: "button" }, label);
    if (active) pill.classList.add("active");
    if (disabled) { pill.classList.add("disabled"); pill.disabled = true; }
    if (title) pill.title = title;
    if (!disabled) pill.addEventListener("click", () => setFocus(catId));
    return pill;
  }
  function renderFocusBar() {
    const bar = byId("focus-bar");
    if (!bar) return;
    clear(bar);
    bar.append(focusPill("All", null, focusedCat === null, false, "Show every metric bucket"));
    for (const c of CATS) {
      const has = HEALTH[c.id].health !== null;
      bar.append(focusPill(c.name, c.id, focusedCat === c.id, !has, has ? `Focus on ${c.name}` : `${c.name} — no data this run`));
    }
  }
  const FOCUS_SECTIONS = [
    { id: "hotspots-panel", cats: ["complexity", "readability"] },
    { id: "arch-watchlist-panel", cats: ["solid"] },
  ];
  function applySectionFocus() {
    for (const s of FOCUS_SECTIONS) {
      const node = byId(s.id);
      if (node) node.hidden = focusedCat !== null && !s.cats.includes(focusedCat);
    }
    const note = byId("cat-focus-note");
    if (note) {
      note.textContent = focusedCat
        ? `focused on ${CAT_BY_ID[focusedCat].name} — click the panel or “All” to clear`
        : "click a dial to focus on one bucket";
    }
  }
  function applyFocus() {
    renderFocusBar();
    renderCategoryGrid();
    rebuildMetricOptions();
    renderSpatialViz();
    renderFixList();
    renderRiskBreakdown();
    applySectionFocus();
  }
  function setFocus(catId) {
    focusedCat = catId;
    applyFocus();
  }
  // Lock the fix-list to its initial (All) height so focusing a bucket — which
  // usually yields fewer rows — doesn't shove the sections below it up/down.
  function lockFixListHeight() {
    const ol = byId("fix-list");
    if (ol) ol.style.minHeight = ol.offsetHeight + "px";
  }
  function initFocusFromHash() {
    const m = /(?:^#|[#&])focus=([a-z]+)/.exec(location.hash || "");
    const id = m ? m[1] : null;
    if (id && CAT_BY_ID[id] && HEALTH[id] && HEALTH[id].health !== null) setFocus(id);
  }

  function boot() {
    initTheme();
    initGraph();
    renderTopbar();
    renderHero();
    renderKPIs();
    renderFixList();
    lockFixListHeight();
    renderFocusBar();
    renderCategoryGrid();

    rebuildMetricOptions();
    metricSelect.addEventListener("change", () => {
      const metric = selectedMetricNow();
      recolorTreemap(metric); renderLegend(metric); renderCoverageChips(metric);
    });

    if (baseline) {
      const wrap = byId("baseline-toggle-wrap"), toggle = byId("baseline-toggle");
      wrap.hidden = false; toggle.checked = baselineMode;
      toggle.addEventListener("change", () => {
        baselineMode = toggle.checked;
        recolorTreemap(selectedMetricNow()); renderLegend(selectedMetricNow());
        renderHero();
      });
    }

    renderSpatialViz();
    renderArchWatchlist();
    renderRiskBreakdown();
    renderBaselineTables();
    renderWorstFunctions();
    applySectionFocus();
    renderFooter();
    initFocusFromHash();
  }

  boot();
})();
