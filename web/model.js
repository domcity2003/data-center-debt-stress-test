"use strict";
// JavaScript port of model.py. Dollar values are USD millions.
(function (root) {
  function mortgageConstant(rate, amortYears) {
    const monthly = rate / 12;
    const months = 12 * amortYears;
    return rate ? 12 * monthly / (1 - Math.pow(1 + monthly, -months)) : 12 / months;
  }

  function runScenario(facts, rollover, rules, s) {
    const inUnit = x => x >= 0 && x <= 1;
    if (![s.renewal, s.backfill, s.flow_through].every(inUnit)) {
      throw new Error("Renewal, backfill and flow-through must be between zero and one.");
    }
    if (Math.min(s.rent_reset, s.other_realization, s.rate, s.extra_reserve_m) < 0) {
      throw new Error("Rent factors, rate and reserve must be nonnegative.");
    }
    if (!(s.cap_rate > 0 && s.amort_years > 0 && s.fee >= 0 && s.fee < 1)) {
      throw new Error("Cap rate and amortization must be positive. Fee must be below 100%.");
    }
    if (!(rules.max_ltv > 0 && rules.max_ltv <= 1 && rules.min_dscr > 0 && rules.min_debt_yield > 0)) {
      throw new Error("Refinance lender constraints must be positive. LTV cannot exceed 100%.");
    }

    const principal = facts.principal_m;
    const ch3Rent = rollover.reduce((t, x) => t + x.ch3_rent_m, 0);
    const otherRent = rollover.reduce((t, x) => t + (x.campus_rent_m - x.ch3_rent_m), 0);
    const occupied = s.renewal + (1 - s.renewal) * s.backfill;
    const ch3Delta = ch3Rent * (occupied * s.rent_reset - 1);
    const otherDelta = otherRent * (s.other_realization - 1);
    const ncf = facts.kncf_2026_m + (ch3Delta + otherDelta) * s.flow_through - s.extra_reserve_m;
    const constant = mortgageConstant(s.rate, s.amort_years);
    const value = Math.max(0, ncf) / s.cap_rate;
    const limits = {
      "LTV": value * rules.max_ltv,
      "DSCR": Math.max(0, ncf) / (constant * rules.min_dscr),
      "Debt yield": Math.max(0, ncf) / rules.min_debt_yield,
    };
    let binding = "LTV";
    for (const k of Object.keys(limits)) if (limits[k] < limits[binding]) binding = k;
    const gross = limits[binding];
    const net = gross * (1 - s.fee);
    const target = principal / (1 - s.fee);
    const requiredNcf = target * Math.max(s.cap_rate / rules.max_ltv, constant * rules.min_dscr, rules.min_debt_yield);
    const ncfAtZero = ncf - ch3Rent * s.flow_through * s.rent_reset * (1 - s.backfill) * s.renewal;
    const renewalSlope = ch3Rent * s.flow_through * s.rent_reset * (1 - s.backfill);
    let minRenewal;
    if (ncfAtZero >= requiredNcf) minRenewal = 0;
    else if (renewalSlope > 0 && (requiredNcf - ncfAtZero) / renewalSlope <= 1) minRenewal = (requiredNcf - ncfAtZero) / renewalSlope;
    else minRenewal = null;
    return {
      name: s.name, ch3_occupied_share: occupied,
      ch3_delta_m: ch3Delta, other_delta_m: otherDelta,
      ncf_m: ncf, value_m: value,
      annual_existing_interest_m: principal * facts.coupon,
      existing_coverage: ncf / (principal * facts.coupon),
      mortgage_constant: constant, limits_m: limits, binding: binding,
      gross_m: gross, net_m: net, cushion_m: net - principal,
      gap_m: Math.max(0, principal - net), required_ncf_m: requiredNcf,
      min_renewal: minRenewal,
    };
  }

  function buildResults(config) {
    const facts = config.facts, rollover = config.presale_rollover;
    const rules = Object.assign({}, config.sizing_rules);
    const scenarios = config.scenarios;
    const size = (s, overrides) => runScenario(facts, rollover, rules, Object.assign({}, s, overrides));
    const base = scenarios[0];
    const g = config.grid;
    const grid = g.rent_resets.map(rent => g.renewals.map(renewal =>
      g.rates.map(rate => size(base, { renewal, rate, rent_reset: rent }).gap_m)));
    const capGrid = g.renewals.map(renewal =>
      g.cap_rates.map(cap => size(base, { renewal, cap_rate: cap }).gap_m));
    let low = 0, high = 0.25, dscrRate = null;
    if (size(base, { rate: high }).binding !== "LTV") {
      for (let i = 0; i < 60; i++) {
        const mid = (low + high) / 2;
        if (size(base, { rate: mid }).binding === "LTV") low = mid; else high = mid;
      }
      dscrRate = high;
    }
    const isolation = { renewal: 1, backfill: 0, rent_reset: 1, other_realization: 1 };
    const probes = [
      ["Full CH3 rent retained", isolation],
      ["No CH3 renewal or replacement", Object.assign({}, isolation, { renewal: 0 })],
      ["CH3 rent resets 25% lower", Object.assign({}, isolation, { rent_reset: 0.75 })],
      ["$5m annual NCF reserve increase", Object.assign({}, isolation, { extra_reserve_m: 5 })],
    ];
    return {
      cases: scenarios.map(s => size(s)), grid_gap_m: grid,
      cap_grid_gap_m: capGrid, dscr_binding_rate: dscrRate,
      rules: rules,
      diligence: probes.map(([label, o]) => {
        const a = size(base, o);
        return { label, ncf_m: a.ncf_m, net_m: a.net_m, gap_m: a.gap_m };
      }),
    };
  }

  const api = { mortgageConstant, runScenario, buildResults };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DealModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
