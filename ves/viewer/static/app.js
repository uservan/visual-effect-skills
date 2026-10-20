"use strict";
// VES trajectory viewer: reads data/index.js (window.VES_INDEX) and data/runs/<key>.js (window.VES_RUNS[key]).
// Works from file:// -- run data is loaded with <script> tags, images by relative path.

const IDX = window.VES_INDEX || [];
const BY_KEY = Object.fromEntries(IDX.map(r => [r.key, r]));
const state = { model: "", condition: "", task: "", outcome: "", q: "" };
const panes = [null, null];  // {run, frames, i, mode}

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === undefined || kid === null || kid === false) continue;
    e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return e;
}
const uniq = key => [...new Set(IDX.map(r => r[key]))].filter(v => v !== undefined && v !== null).sort();
const outcomeOf = r => r.status !== "completed" ? "not completed" : (r.success ? "success" : "failure");
const outcomeEl = r => {
  const o = outcomeOf(r);
  return h("span", { class: o === "success" ? "ok" : o === "failure" ? "bad" : "warn" }, o === "not completed" ? r.status : o);
};
const fmtK = n => (n === undefined || n === null) ? "" : (n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n));

function filtered(ignore = []) {
  return IDX.filter(r =>
    (ignore.includes("model") || !state.model || r.model === state.model) &&
    (ignore.includes("condition") || !state.condition || r.condition === state.condition) &&
    (!state.task || r.task_id === state.task) &&
    (ignore.includes("outcome") || !state.outcome || outcomeOf(r) === state.outcome) &&
    (!state.q || JSON.stringify(r).toLowerCase().includes(state.q.toLowerCase())));
}

// ---------- filters, matrix, table ----------
function renderFilters() {
  const sel = (key, label, values) => h("label", {}, label + " ",
    h("select", { onchange: e => { state[key] = e.target.value; renderAll(); } },
      h("option", { value: "" }, "all"), values.map(v => h("option", { value: v, selected: state[key] === v }, v))));
  const box = document.getElementById("filters");
  box.replaceChildren(
    sel("model", "model", uniq("model")), sel("condition", "condition", uniq("condition")),
    sel("task", "task", uniq("task_id")), sel("outcome", "outcome", ["success", "failure", "not completed"]),
    h("input", { type: "search", placeholder: "search", value: state.q,
                 oninput: e => { state.q = e.target.value; renderMatrix(); renderTable(); } }));
}

function latestCompleted(runs) {
  const done = runs.filter(r => r.status === "completed");
  done.sort((a, b) => String(a.finished_at).localeCompare(String(b.finished_at)));
  return done.length ? done[done.length - 1] : null;
}

function renderMatrix() {
  const rows = filtered(["condition", "outcome"]);  // the matrix always shows every condition and outcome
  const conds = uniq("condition");
  const models = [...new Set(rows.map(r => r.model))].sort();
  const box = document.getElementById("matrix");
  const tables = models.map(model => {
    const mrows = rows.filter(r => r.model === model);
    const tasks = [...new Set(mrows.map(r => r.task_id))].sort();
    const head = h("tr", {}, h("th", {}, model), conds.map(c => h("th", {}, c)), h("th", {}, "compare"));
    const body = tasks.map(t => {
      const cells = conds.map(c => {
        const runs = mrows.filter(r => r.task_id === t && r.condition === c);
        const r = latestCompleted(runs);
        if (!runs.length) return h("td", {}, "");
        if (!r) return h("td", { class: "cell warn", title: "no completed attempt",
                                 onclick: e => openRun(runs[runs.length - 1].key, e.shiftKey ? 1 : 0) }, "…");
        return h("td", { class: "cell " + (r.success ? "ok" : "bad"), title: `${r.run_id} score ${r.score}`,
                         onclick: e => openRun(r.key, e.shiftKey ? 1 : 0) }, r.success ? "✓" : "✗");
      });
      const c2 = latestCompleted(mrows.filter(r => r.task_id === t && r.condition === "C2"));
      const c3 = latestCompleted(mrows.filter(r => r.task_id === t && r.condition === "C3"));
      const cmp = (c2 && c3) ? h("button", { onclick: () => { openRun(c2.key, 0); openRun(c3.key, 1); } }, "C2 | C3") : "";
      return h("tr", {}, h("td", {}, t), cells, h("td", {}, cmp));
    });
    return h("div", { class: "scroll" }, h("table", {}, h("thead", {}, head), h("tbody", {}, body)));
  });
  box.replaceChildren(...(tables.length ? tables : [h("span", { class: "muted" }, "no runs")]));
}

function renderTable() {
  const rows = filtered();
  document.getElementById("counts").textContent = `${rows.length} of ${IDX.length} runs`;
  const cols = ["model", "condition", "task", "run", "outcome", "score", "actions", "turns", "skill", "invalid",
                "prompt tok", "runtime s", "stop", "first error", "tags", "open"];
  const body = rows.map(r => h("tr", {},
    h("td", {}, r.model), h("td", {}, r.condition), h("td", {}, r.task_id), h("td", {}, r.run_id), h("td", {}, outcomeEl(r)),
    h("td", {}, r.score ?? ""), h("td", {}, `${r.actions ?? ""}/${r.max_steps ?? ""}`), h("td", {}, r.model_turns ?? ""),
    h("td", {}, r.skill_calls ?? ""), h("td", {}, r.invalid_actions ?? ""), h("td", {}, fmtK((r.tokens || {}).prompt)),
    h("td", {}, r.runtime_s ?? ""), h("td", {}, r.stop_reason ?? ""), h("td", {}, r.first_error_step ?? ""),
    h("td", {}, (r.failure_tags || []).join("; ")),
    h("td", {}, h("button", { onclick: () => openRun(r.key, 0) }, "A"), " ",
               h("button", { onclick: () => openRun(r.key, 1) }, "B"))));
  document.getElementById("table").replaceChildren(h("div", { class: "scroll" },
    h("table", {}, h("thead", {}, h("tr", {}, cols.map(c => h("th", {}, c)))), h("tbody", {}, body))));
}

function renderAll() { renderFilters(); renderMatrix(); renderTable(); }

// ---------- run panes ----------
function loadRun(key) {
  return new Promise((resolve, reject) => {
    if (window.VES_RUNS && window.VES_RUNS[key]) return resolve(window.VES_RUNS[key]);
    const s = document.createElement("script");
    s.src = `data/runs/${key}.js`;
    s.onload = () => resolve(window.VES_RUNS[key]);
    s.onerror = () => reject(new Error("cannot load " + s.src));
    document.body.append(s);
  });
}

function buildFrames(run) {
  const f = [];
  const t0 = run.trace.length ? run.trace[0].t : 0;
  for (const ev of run.trace) {
    const rel = ev.t !== undefined ? (ev.t - t0).toFixed(1) + " s" : "";
    if (ev.type === "init") f.push({ kind: "initial", img: ev.screenshot, rel, ev });
    else if (ev.type === "step") f.push({ kind: "step", img: ev.after, before: ev.before, after: ev.after, step: ev.step, turn: ev.turn, rel, ev });
    else if (ev.type === "observe") f.push({ kind: "observe", img: ev.screenshot, turn: ev.turn, rel, ev });
    else if (["skill", "invalid_action", "error", "agent_done", "stop", "verifier", "env_ready"].includes(ev.type))
      f.push({ kind: ev.type, turn: ev.turn, rel, ev });
  }
  if ((run.result || {}).status === "completed") f.push({ kind: "final", img: "screenshots/final.png", ev: {} });
  // non-image frames show the last screenshot before them
  let last = null;
  for (const fr of f) { if (fr.img) last = fr.img; else fr.carry = last; }
  return f;
}

async function openRun(key, slot) {
  const run = await loadRun(key);
  panes[slot] = { run, frames: buildFrames(run), i: 0, mode: "after" };
  renderPane(slot);
  document.getElementById("pane" + slot).scrollIntoView({ behavior: "smooth", block: "start" });
}

function setFrame(slot, i, fromSync) {
  const p = panes[slot];
  if (!p) return;
  p.i = Math.max(0, Math.min(p.frames.length - 1, i));
  renderPane(slot);
  const other = panes[1 - slot];
  if (!fromSync && other && document.getElementById("sync").checked) {
    const fr = p.frames[p.i];
    let j = p.i;
    if (fr.kind === "step") {
      const k = other.frames.findIndex(x => x.kind === "step" && x.step === fr.step);
      j = k >= 0 ? k : other.frames.length - 1;
    } else if (fr.kind === "final") j = other.frames.length - 1;
    else if (fr.kind === "initial") j = 0;
    setFrame(1 - slot, j, true);
  }
}

function jumpFirstError(slot) {
  const p = panes[slot];
  if (!p) return;
  const raw = String((p.run.annotation || {}).first_error_step ?? "").trim();
  if (!/^\d+$/.test(raw)) return alert("no annotated first error step");
  const n = Number(raw);
  const k = p.frames.findIndex(x => x.kind === "step" && x.step === n);
  if (k < 0) return alert("step " + n + " not found in the trace");
  setFrame(slot, k);
}

function renderPane(slot) {
  const box = document.getElementById("pane" + slot);
  const p = panes[slot];
  if (!p) { box.replaceChildren(); return; }
  const run = p.run, r = run.result || {}, idx = BY_KEY[run.key] || {}, a = run.annotation || {};
  const fr = p.frames[p.i];
  const base = run.path + "/";
  const imgRel = fr.kind === "step" ? (p.mode === "before" ? fr.before : fr.after) : (fr.img || fr.carry);
  const eff = fr.kind === "step" ? (fr.ev.effect || {}) : {};
  const effPaths = eff.paths || null;
  let main = imgRel ? base + imgRel : null;
  if (fr.kind === "step" && p.mode === "diff") main = effPaths ? base + effPaths.diff : null;
  const resp = (fr.turn !== undefined && fr.turn !== null) ? (run.responses || []).find(x => x.turn === fr.turn) : null;
  const ver = r.verifier || {};

  const modeRadio = m => h("label", {}, h("input", { type: "radio", name: "mode" + slot, checked: p.mode === m,
    disabled: m === "diff" && !effPaths && fr.kind === "step", onchange: () => { p.mode = m; renderPane(slot); } }), " " + m);

  box.replaceChildren(
    h("h2", {}, `${idx.model} · ${idx.condition} · ${idx.task_id} · ${idx.run_id}`),
    h("div", { class: "meta" },
      h("span", {}, "outcome: ", outcomeEl(idx)), h("span", {}, `score ${r.score ?? "-"}`),
      h("span", {}, `stop: ${r.stop_reason ?? "-"}`), h("span", {}, `actions ${r.actions}/${r.max_steps}`),
      h("span", {}, `turns ${r.model_turns}`), h("span", {}, `skill calls ${r.skill_calls}`),
      h("span", {}, `prompt tokens ${fmtK((r.tokens || {}).prompt)}`), h("span", {}, `runtime ${(r.runtime || {}).total_s ?? "-"} s`)),
    h("div", { class: "meta" }, h("span", {}, "verifier: " + (ver.program || "-")),
      h("span", {}, "feedback: " + (ver.feedback || r.error || "-"))),
    a.failure_tags ? h("div", { class: "meta" }, "annotation: ", a.failure_tags.split(";").map(t => h("span", { class: "tag" }, t)),
      a.notes ? h("span", { class: "muted" }, a.notes) : "") : "",
    h("div", { class: "instr" }, (run.task || {}).instruction || ""),
    h("div", { class: "nav" },
      h("button", { onclick: () => setFrame(slot, p.i - 1) }, "◀ prev"),
      h("input", { type: "range", min: 0, max: p.frames.length - 1, value: p.i, oninput: e => setFrame(slot, Number(e.target.value)) }),
      h("button", { onclick: () => setFrame(slot, p.i + 1) }, "next ▶"),
      h("span", {}, `${p.i + 1}/${p.frames.length}`),
      h("button", { onclick: () => jumpFirstError(slot) }, "first error step"),
      h("button", { onclick: () => { panes[slot] = null; renderPane(slot); } }, "close")),
    h("div", { class: "nav" }, h("span", { class: "frame-kind" },
      fr.kind === "step" ? `step ${fr.step} (turn ${fr.turn})` : fr.kind + (fr.turn !== undefined ? ` (turn ${fr.turn})` : "")),
      h("span", { class: "muted" }, fr.rel || ""),
      fr.kind === "step" ? h("span", {}, modeRadio("before"), " ", modeRadio("after"), " ", modeRadio("diff")) : ""),
    fr.kind === "step" ? h("pre", {}, `${fr.ev.action_text}\n${fr.ev.tool}(${JSON.stringify(fr.ev.arguments)})` +
      (eff.changed_fraction !== undefined ? `\nchanged pixels: ${(100 * (eff.changed_fraction || 0)).toFixed(2)}%` : "")) : "",
    ["skill", "invalid_action", "error", "agent_done", "stop", "verifier", "env_ready"].includes(fr.kind)
      ? h("pre", {}, JSON.stringify(fr.ev, null, 1)) : "",
    main ? h("div", { class: "shot" }, h("a", { href: main, target: "_blank" }, h("img", { src: main, alt: fr.kind, loading: "lazy" })))
         : h("div", { class: "muted" }, fr.kind === "step" && p.mode === "diff" ? "no difference image (change below threshold)" : "no image"),
    effPaths ? h("div", { class: "thumbs" }, ["before", "after", "diff"].map(k =>
      h("figure", {}, h("a", { href: base + effPaths[k], target: "_blank" }, h("img", { src: base + effPaths[k], loading: "lazy" })),
        h("figcaption", {}, `effect ${k} (crop ${JSON.stringify(eff.bbox)})`)))) : "",
    resp ? h("details", { open: true }, h("summary", {}, `model turn ${resp.turn} (${resp.latency_s}s, ${resp.usage.prompt_tokens} prompt tokens)`),
      h("pre", {}, (resp.content || "(no text)") + "\n" + resp.tool_calls.map(c => `→ ${c.name}(${c.arguments})`).join("\n"))) : ""
  );
}

// ---------- task report ----------
function exportReport() {
  const p = panes[0];
  const task = p ? (BY_KEY[p.run.key] || {}).task_id : state.task;
  if (!task) return alert("open a run in pane A (or choose a task filter) first");
  const runs = IDX.filter(r => r.task_id === task).sort((a, b) => (a.model + a.condition + a.run_id).localeCompare(b.model + b.condition + b.run_id));
  const lines = [`# Task report: ${task}`, "", `Instruction: ${runs[0] ? runs[0].instruction : ""}`, "",
    "| model | condition | run | status | success | score | actions | stop | first error step | failure tags |",
    "|---|---|---|---|---|---|---|---|---|---|"];
  for (const r of runs) lines.push(`| ${r.model} | ${r.condition} | ${r.run_id} | ${r.status} | ${r.success} | ${r.score ?? ""} | ` +
    `${r.actions}/${r.max_steps} | ${r.stop_reason ?? ""} | ${r.first_error_step ?? ""} | ${(r.failure_tags || []).join("; ")} |`);
  for (const r of runs) {
    lines.push("", `## ${r.model} ${r.condition} ${r.run_id}`, `- verifier feedback: ${r.feedback ?? ""}`,
      `- initial screenshot: ${r.path}/screenshots/initial.png`, `- final screenshot: ${r.path}/screenshots/final.png`,
      `- trace: ${r.path}/trace.jsonl`);
    if (r.first_error_step !== null && r.first_error_step !== undefined) {
      const s = String(r.first_error_step).padStart(3, "0");
      lines.push(`- first error step ${r.first_error_step}: ${r.path}/screenshots/step_${s}_before.png -> ${r.path}/screenshots/step_${s}_after.png`);
    }
  }
  const url = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/markdown" }));
  const link = h("a", { href: url, download: `${task}_report.md` });
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

document.getElementById("export").addEventListener("click", exportReport);
document.addEventListener("keydown", e => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (e.key === "ArrowRight") setFrame(0, (panes[0] || { i: 0 }).i + 1);
  if (e.key === "ArrowLeft") setFrame(0, (panes[0] || { i: 0 }).i - 1);
});
renderAll();
