"use strict";
(function () {
  const deal = globalThis.dealData;
  const M = globalThis.DealModel;
  const $ = id => document.getElementById(id);
  const facts = deal.facts, rollover = deal.presale_rollover, rules = deal.sizing_rules;
  const presets = deal.scenarios;
  const fixed = { flow_through: presets[0].flow_through, amort_years: presets[0].amort_years, fee: presets[0].fee };

  // key, label, hint, min, max, step, decimals, display factor, unit
  const controls = [
    ["renewal", "CH3 renewal", "Share of expiring CH3 rent that renews", 0, 100, 1, 0, 100, "%"],
    ["backfill", "Backfill of non-renewed space", "Share of the rest re-leased by maturity", 0, 100, 1, 0, 100, "%"],
    ["rent_reset", "CH3 rent reset", "100% = flat rent on occupied space", 50, 120, 1, 0, 100, "%"],
    ["rate", "Refinance coupon", "Sets the DSCR limit", 4, 12, 0.05, 2, 100, "%"],
    ["cap_rate", "Exit cap rate", "Sets value, and so the LTV limit", 6, 13, 0.05, 2, 100, "%"],
    ["extra_reserve_m", "Extra annual reserve", "Deducted from NCF", 0, 10, 0.1, 1, 1, "$m"],
  ];

  const money = x => "$" + x.toFixed(1) + "m";
  const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
  const bindName = { "LTV": "Value (LTV)", "DSCR": "DSCR", "Debt yield": "Debt yield" };
  const ruleText = {
    "LTV": () => pct(rules.max_ltv, 0) + " of value at the exit cap rate",
    "DSCR": () => rules.min_dscr.toFixed(2) + "x on a 30-year constant",
    "Debt yield": () => pct(rules.min_debt_yield, 0) + " of NCF",
  };

  let state = Object.assign({}, presets[0]);
  let activePreset = "Base";
  const inputs = {};

  function current(overrides) { return Object.assign({}, state, fixed, overrides, { name: "Custom" }); }
  function run(overrides) { return M.runScenario(facts, rollover, rules, current(overrides)); }

  function buildControls() {
    const host = $("control-list");
    for (const [key, label, hint, min, max, step, dec, factor, unit] of controls) {
      const div = document.createElement("div");
      div.className = "ctl";
      const id = "c-" + key;
      div.innerHTML =
        '<div class="ctl-head"><label for="' + id + '-n">' + label + '</label>' +
        '<span class="num"><input id="' + id + '-n" type="number" inputmode="decimal" min="' + min + '" max="' + max + '" step="' + step + '">' + unit + '</span></div>' +
        '<input id="' + id + '-r" type="range" min="' + min + '" max="' + max + '" step="' + step + '" aria-label="' + label + ' slider">' +
        '<p class="hint">' + hint + '</p>';
      host.appendChild(div);
      const num = div.querySelector('input[type="number"]'), rng = div.querySelector('input[type="range"]');
      inputs[key] = { num, rng, dec, factor, min, max };
      const apply = raw => {
        let v = parseFloat(raw);
        if (!isFinite(v)) return;
        v = Math.min(max, Math.max(min, v));
        state[key] = Math.round(v / step) * step / factor;
        state[key] = +state[key].toFixed(6);
        activePreset = null;
        render(key);
      };
      rng.addEventListener("input", () => apply(rng.value));
      num.addEventListener("input", () => { if (num.value !== "") apply(num.value); });
      num.addEventListener("blur", () => syncInputs());
    }
  }

  function syncInputs(skip) {
    for (const key of Object.keys(inputs)) {
      const c = inputs[key], v = (state[key] * c.factor);
      c.rng.value = v;
      if (key !== skip) c.num.value = v.toFixed(c.dec);
    }
  }

  function buildPresets() {
    const host = $("scenarios");
    for (const p of presets) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = p.name;
      b.dataset.name = p.name;
      b.addEventListener("click", () => { state = Object.assign({}, p); activePreset = p.name; render(); });
      host.appendChild(b);
    }
  }

  // Lowest coupon at which DSCR, not LTV, sets proceeds, holding the other drivers.
  function dscrCrossover() {
    if (run({ rate: 0.25 }).binding === "LTV") return null;
    let lo = 0, hi = 0.25;
    for (let i = 0; i < 50; i++) {
      const mid = (lo + hi) / 2;
      if (run({ rate: mid }).binding === "LTV") lo = mid; else hi = mid;
    }
    return hi;
  }

  function renderTiles(r) {
    $("t-ncf").textContent = money(r.ncf_m);
    $("t-ncf-sub").textContent = "vs $" + facts.kncf_2026_m.toFixed(1) + "m KBRA 2026 anchor";
    $("t-cov").textContent = r.existing_coverage.toFixed(2) + "x";
    $("t-net").textContent = money(r.net_m);
    $("t-net-sub").textContent = "After " + pct(fixed.fee, 0) + " fees, vs $" + facts.principal_m.toFixed(0) + "m payoff";
    const tile = $("tile-gap");
    if (r.gap_m > 0) {
      tile.className = "tile gap";
      $("t-gap-h").textContent = "Funding gap";
      $("t-gap").textContent = money(r.gap_m);
      $("t-gap-sub").textContent = "Cash needed beyond proceeds";
    } else {
      tile.className = "tile cushion";
      $("t-gap-h").textContent = "Payoff cushion";
      $("t-gap").textContent = money(r.cushion_m);
      $("t-gap-sub").textContent = "Proceeds above the payoff";
    }
    $("t-bind").textContent = bindName[r.binding];
    $("t-bind-sub").textContent = ruleText[r.binding]();
    if (r.min_renewal === null) {
      $("t-be").textContent = "Not reachable";
      $("t-be-sub").textContent = "Even 100% renewal falls short";
    } else {
      $("t-be").textContent = pct(r.min_renewal);
      $("t-be-sub").textContent = "Renewal needed to cover payoff";
    }
  }

  function renderSizing(r) {
    const target = facts.principal_m / (1 - fixed.fee);
    const keys = ["LTV", "DSCR", "Debt yield"];
    const max = Math.max(target, ...keys.map(k => r.limits_m[k])) * 1.06;
    const at = v => (100 * v / max).toFixed(2) + "%";
    $("sizing").innerHTML = keys.map(k =>
      '<div class="srow' + (k === r.binding ? " binding" : "") + '">' +
      '<div class="name">' + bindName[k] + '<small>' + ruleText[k]() + '</small></div>' +
      '<div class="track"><div class="fill" style="width:' + at(r.limits_m[k]) + '"></div><div class="payoff" style="left:' + at(target) + '"></div></div>' +
      '<div class="val">' + money(r.limits_m[k]) + '</div></div>').join("");
    $("sizing-alt").textContent = keys.map(k => bindName[k] + " limit " + money(r.limits_m[k])).join(", ") +
      ". Payoff plus fees " + money(target) + ". " + bindName[r.binding] + " binds.";
    const x = dscrCrossover();
    let note = "Dashed line: the $450m payoff grossed up for fees (" + money(target) + "). ";
    if (r.binding === "LTV") {
      note += x === null ? "Value sets proceeds at every coupon up to 25%, so the coupon does not matter here; the cap rate does."
        : "Value sets proceeds. The refinance coupon would have to reach " + pct(x, 2) + " before the DSCR test binds instead.";
    } else if (r.binding === "DSCR") {
      note += "The coupon is the binding constraint here: it caps proceeds through the DSCR test" + (x !== null ? ", and has done since about " + pct(x, 2) + "." : ".");
    } else {
      note += "Debt yield (NCF alone) is the tightest test, so neither the coupon nor the cap rate changes proceeds.";
    }
    $("sizing-note").textContent = note;
  }

  function heat(gap) {
    if (gap <= 0.00001) return ["#e3efe7", "#215e4f", "—"];
    const t = Math.min(1, gap / 250);
    const l = 92 - 48 * t;
    return ["hsl(14, 58%, " + l.toFixed(1) + "%)", l < 62 ? "#fff" : "#4a1d10", gap.toFixed(1)];
  }
  const nearest = (arr, v) => arr.reduce((b, x, i) => Math.abs(x - v) < Math.abs(arr[b] - v) ? i : b, 0);

  function renderGrid(id, colKey, cols, colLabel, held) {
    const g = deal.grid;
    const ci = nearest(cols, state[colKey]), ri = nearest(g.renewals, state.renewal);
    let html = '<thead><tr><th scope="col" class="corner">CH3 renewal ↓ / ' + colLabel + ' →</th>' +
      cols.map(c => '<th scope="col">' + pct(c, 2) + '</th>').join("") + '</tr></thead><tbody>';
    g.renewals.forEach((renewal, i) => {
      html += '<tr><th scope="row">' + pct(renewal, 0) + '</th>';
      cols.forEach((c, j) => {
        const gap = run({ renewal, [colKey]: c }).gap_m;
        const [bg, fg, text] = heat(gap);
        html += '<td' + (i === ri && j === ci ? ' class="now" aria-label="' + text + ', nearest to current drivers"' : "") +
          ' style="background:' + bg + ';color:' + fg + '">' + text + '</td>';
      });
      html += '</tr>';
    });
    $(id).innerHTML = html + '</tbody>';
    $(id.replace("grid", "g") + "-held").textContent = held;
  }

  function renderGrids() {
    const common = "CH3 rent reset " + pct(state.rent_reset, 0) + ", backfill " + pct(state.backfill, 0) +
      ", extra reserve " + money(state.extra_reserve_m);
    renderGrid("grid1", "rate", deal.grid.rates, "refinance coupon",
      "Held fixed: " + common + ", exit cap rate " + pct(state.cap_rate, 2) + ".");
    renderGrid("grid2", "cap_rate", deal.grid.cap_rates, "exit cap rate",
      "Held fixed: " + common + ", refinance coupon " + pct(state.rate, 2) + ".");
  }

  function renderDiligence() {
    const base = Object.assign({}, presets[0], { name: "Probe" });
    const iso = { renewal: 1, backfill: 0, rent_reset: 1, other_realization: 1 };
    const probes = [
      ["Full CH3 rent retained", iso], ["No CH3 renewal or replacement", { renewal: 0 }],
      ["CH3 rent resets 25% lower", { rent_reset: 0.75 }], ["$5m annual NCF reserve increase", { extra_reserve_m: 5 }],
    ];
    $("dil").innerHTML = '<thead><tr><th scope="col">Shock</th><th scope="col">NCF</th><th scope="col">Net takeout</th><th scope="col">Funding gap</th></tr></thead><tbody>' +
      probes.map(([label, o]) => {
        const r = M.runScenario(facts, rollover, rules, Object.assign({}, base, iso, o));
        return '<tr><th scope="row">' + label + '</th><td>' + money(r.ncf_m) + '</td><td>' + money(r.net_m) + '</td><td>' +
          (r.gap_m > 0 ? money(r.gap_m) : "—") + '</td></tr>';
      }).join("") + '</tbody>';
  }

  function render(skip) {
    syncInputs(skip);
    for (const b of $("scenarios").children) b.setAttribute("aria-pressed", String(b.dataset.name === activePreset));
    $("preset-note").textContent = activePreset ? activePreset + " preset" : "Custom";
    $("held-note").textContent = "Held fixed: other-space rent realization " + pct(state.other_realization, 0) +
      " (set by preset), " + pct(fixed.flow_through, 0) + " flow-through, " + fixed.amort_years + "-year amortization, " + pct(fixed.fee, 0) + " fees.";
    try {
      const r = run();
      $("error").hidden = true;
      renderTiles(r); renderSizing(r); renderGrids();
    } catch (e) {
      $("error").textContent = e.message; $("error").hidden = false;
    }
  }

  function headline() {
    const res = M.buildResults(deal);
    $("h-base").textContent = money(res.cases[0].cushion_m);
    $("h-down").textContent = money(res.cases[1].gap_m);
  }

  buildControls(); buildPresets(); headline(); renderDiligence(); render();
})();
