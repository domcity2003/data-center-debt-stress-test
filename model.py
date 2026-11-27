"""Loan-level stress test. Dollar values are in USD millions."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SizingRules:
    max_ltv: float
    min_dscr: float
    min_debt_yield: float


@dataclass(frozen=True)
class Scenario:
    name: str
    renewal: float
    backfill: float
    rent_reset: float
    other_realization: float
    flow_through: float
    extra_reserve_m: float
    rate: float
    cap_rate: float
    amort_years: int
    fee: float


def mortgage_constant(rate, amort_years):
    """Annual payments per dollar of principal, based on monthly amortization."""
    monthly = rate / 12
    months = 12 * amort_years
    return 12 * monthly / (1 - (1 + monthly) ** -months) if rate else 12 / months


def run_scenario(facts, rollover, rules, s):
    if not all(0 <= x <= 1 for x in (s.renewal, s.backfill, s.flow_through)):
        raise ValueError("Renewal, backfill and flow-through must be between zero and one.")
    if min(s.rent_reset, s.other_realization, s.rate, s.extra_reserve_m) < 0:
        raise ValueError("Rent factors, rate and reserve must be nonnegative.")
    if not (s.cap_rate > 0 and s.amort_years > 0 and 0 <= s.fee < 1):
        raise ValueError("Cap rate and amortization must be positive. Fee must be below 100%.")
    if not (0 < rules.max_ltv <= 1 and rules.min_dscr > 0 and rules.min_debt_yield > 0):
        raise ValueError("Refinance lender constraints must be positive. LTV cannot exceed 100%.")

    principal = facts["principal_m"]
    ch3_rent = sum(x["ch3_rent_m"] for x in rollover)
    other_rent = sum(x["campus_rent_m"] - x["ch3_rent_m"] for x in rollover)
    occupied = s.renewal + (1 - s.renewal) * s.backfill
    ch3_delta = ch3_rent * (occupied * s.rent_reset - 1)
    other_delta = other_rent * (s.other_realization - 1)
    ncf = facts["kncf_2026_m"] + (ch3_delta + other_delta) * s.flow_through - s.extra_reserve_m
    constant = mortgage_constant(s.rate, s.amort_years)
    value = max(0, ncf) / s.cap_rate
    sizing = {
        "LTV": value * rules.max_ltv,
        "DSCR": max(0, ncf) / (constant * rules.min_dscr),
        "Debt yield": max(0, ncf) / rules.min_debt_yield,
    }
    binding = min(sizing, key=sizing.get)
    gross = sizing[binding]
    net = gross * (1 - s.fee)
    target = principal / (1 - s.fee)
    required_ncf = target * max(s.cap_rate / rules.max_ltv, constant * rules.min_dscr, rules.min_debt_yield)
    ncf_at_zero = ncf - ch3_rent * s.flow_through * s.rent_reset * (1 - s.backfill) * s.renewal
    renewal_slope = ch3_rent * s.flow_through * s.rent_reset * (1 - s.backfill)
    # Share of exposed CH3 rent that must renew for the takeout to cover the payoff.
    # None means even full renewal cannot cover it with the other drivers unchanged.
    if ncf_at_zero >= required_ncf:
        min_renewal = 0.0
    elif renewal_slope > 0 and (required_ncf - ncf_at_zero) / renewal_slope <= 1:
        min_renewal = (required_ncf - ncf_at_zero) / renewal_slope
    else:
        min_renewal = None
    return {
        "name": s.name, "ch3_occupied_share": occupied,
        "ch3_delta_m": ch3_delta, "other_delta_m": other_delta,
        "ncf_m": ncf, "value_m": value,
        "annual_existing_interest_m": principal * facts["coupon"],
        "existing_coverage": ncf / (principal * facts["coupon"]),
        "mortgage_constant": constant, "limits_m": sizing, "binding": binding,
        "gross_m": gross, "net_m": net, "cushion_m": net - principal,
        "gap_m": max(0, principal - net), "required_ncf_m": required_ncf,
        "min_renewal": min_renewal,
    }


def build_results(config):
    facts, rollover = config["facts"], config["presale_rollover"]
    rules = SizingRules(**config["sizing_rules"])
    scenarios = [Scenario(**x) for x in config["scenarios"]]

    def size(s, **kwargs):
        return run_scenario(facts, rollover, rules, replace(s, **kwargs))

    base = scenarios[0]
    grid = [
        [[size(base, renewal=renewal, rate=rate, rent_reset=rent)["gap_m"]
          for rate in config["grid"]["rates"]] for renewal in config["grid"]["renewals"]]
        for rent in config["grid"]["rent_resets"]
    ]
    cap_grid = [
        [size(base, renewal=renewal, cap_rate=cap)["gap_m"] for cap in config["grid"]["cap_rates"]]
        for renewal in config["grid"]["renewals"]
    ]
    # Lowest refinance coupon at which the DSCR test, not LTV, sets base-case proceeds.
    low, high = 0.0, 0.25
    if size(base, rate=high)["binding"] == "LTV":
        dscr_rate = None
    else:
        for _ in range(60):
            mid = (low + high) / 2
            low, high = (mid, high) if size(base, rate=mid)["binding"] == "LTV" else (low, mid)
        dscr_rate = high
    isolation = {"renewal": 1, "backfill": 0, "rent_reset": 1, "other_realization": 1}
    probes = [
        ("Full CH3 rent retained", isolation),
        ("No CH3 renewal or replacement", {**isolation, "renewal": 0}),
        ("CH3 rent resets 25% lower", {**isolation, "rent_reset": 0.75}),
        ("$5m annual NCF reserve increase", {**isolation, "extra_reserve_m": 5}),
    ]
    return {
        "cases": [size(s) for s in scenarios], "grid_gap_m": grid,
        "cap_grid_gap_m": cap_grid, "dscr_binding_rate": dscr_rate,
        "rules": asdict(rules),
        "diligence": [
            {"label": label, **{k: answer[k] for k in ("ncf_m", "net_m", "gap_m")}}
            for label, overrides in probes for answer in [size(base, **overrides)]
        ],
    }


if __name__ == "__main__":
    config = json.loads((ROOT / "data/deal.json").read_text(encoding="utf-8"))
    print(json.dumps(build_results(config), indent=2, allow_nan=False))
