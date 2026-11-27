"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { spawnSync } = require("node:child_process");
const model = require("./model");

const root = path.join(__dirname, "..");
const deal = JSON.parse(fs.readFileSync(path.join(root, "data/deal.json"), "utf8"));
const DEFAULT_PY = "C:\\Users\\DomBa\\.uv-python\\cpython-3.12-windows-x86_64-none\\python.exe";

function runPython() {
  const candidates = [process.env.PYTHON, DEFAULT_PY, "python", "python3"].filter(Boolean);
  for (const exe of candidates) {
    const r = spawnSync(exe, ["model.py"], { cwd: root, encoding: "utf8" });
    if (!r.error && r.status === 0) return JSON.parse(r.stdout);
  }
  throw new Error("Could not run model.py. Set the PYTHON environment variable.");
}

const TOL = 1e-9;
let compared = 0;
function compare(js, py, where) {
  if (py === null || typeof py === "string" || typeof py === "boolean") {
    assert.equal(js, py, where);
  } else if (typeof py === "number") {
    assert.equal(typeof js, "number", where);
    assert.ok(Math.abs(js - py) <= TOL, `${where}: js ${js} vs py ${py}`);
    compared++;
  } else if (Array.isArray(py)) {
    assert.ok(Array.isArray(js), where);
    assert.equal(js.length, py.length, where + " length");
    py.forEach((v, i) => compare(js[i], v, `${where}[${i}]`));
  } else {
    assert.deepEqual(Object.keys(js).sort(), Object.keys(py).sort(), where + " keys");
    for (const k of Object.keys(py)) compare(js[k], py[k], `${where}.${k}`);
  }
}

test("JS model matches model.py output within 1e-9", () => {
  const py = runPython();
  const js = model.buildResults(deal);
  compare(js, py, "results");
  assert.ok(compared > 200, "expected to compare every number, compared " + compared);
  assert.equal(py.cases.length, 3);
  assert.equal(py.grid_gap_m.flat(2).length + py.cap_grid_gap_m.flat().length, 108 + 36);
});

test("headline figures", () => {
  const r = model.buildResults(deal);
  assert.equal(r.cases[0].cushion_m.toFixed(1), "0.6");
  assert.equal(r.cases[1].gap_m.toFixed(1), "102.1");
  assert.equal(r.cases[1].existing_coverage.toFixed(2), "1.93");
});

test("min_renewal is null when unreachable", () => {
  const s = { ...deal.scenarios[0], rent_reset: 0.5, cap_rate: 0.11 };
  assert.equal(model.runScenario(deal.facts, deal.presale_rollover, deal.sizing_rules, s).min_renewal, null);
});

test("validation rejects bad inputs", () => {
  const f = deal.facts, ro = deal.presale_rollover, rules = deal.sizing_rules;
  const b = deal.scenarios[0];
  assert.throws(() => model.runScenario(f, ro, rules, { ...b, renewal: 1.1 }));
  assert.throws(() => model.runScenario(f, ro, rules, { ...b, rate: -0.01 }));
  assert.throws(() => model.runScenario(f, ro, rules, { ...b, fee: 1 }));
  assert.throws(() => model.runScenario(f, ro, { ...rules, max_ltv: 1.2 }, b));
});

test("web/deal-data.js matches data/deal.json exactly", () => {
  const ctx = {};
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "deal-data.js"), "utf8"), ctx);
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.dealData)), deal);
});
