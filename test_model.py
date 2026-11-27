import json
import unittest
from dataclasses import replace

from model import ROOT, Scenario, SizingRules, build_results, mortgage_constant, run_scenario

CONFIG = json.loads((ROOT / "data/deal.json").read_text(encoding="utf-8"))
BASE = Scenario(**CONFIG["scenarios"][0])
RULES = SizingRules(**CONFIG["sizing_rules"])


def size(**overrides):
    return run_scenario(CONFIG["facts"], CONFIG["presale_rollover"], RULES,
                        replace(BASE, **overrides))


class RefinanceTest(unittest.TestCase):
    def test_base_matches_hand_calculation(self):
        # $30.8m x 2.5% missing rent x 85% = $0.6545m NCF loss.
        answer = size()
        self.assertAlmostEqual(answer["ncf_m"], 59.4455)
        self.assertAlmostEqual(answer["net_m"], 59.4455 / .0875 * .67 * .99)
        self.assertAlmostEqual(answer["annual_existing_interest_m"], 25.875)
        self.assertEqual(answer["binding"], "LTV")

    def test_break_even_hits_principal(self):
        threshold = size()["min_renewal"]
        self.assertAlmostEqual(size(renewal=threshold)["net_m"], 450)
        self.assertGreater(size(renewal=threshold - .01)["gap_m"], 0)
        self.assertEqual(size(renewal=threshold + .01)["gap_m"], 0)

    def test_high_coupon_switches_to_dscr_limit(self):
        self.assertEqual(size(rate=.10)["binding"], "DSCR")
        self.assertAlmostEqual(size(rate=.10)["gap_m"], 36.0416768984)

    def test_zero_rate_and_negative_cash_flow(self):
        self.assertAlmostEqual(mortgage_constant(0, 30), 1/30)
        self.assertEqual(size(extra_reserve_m=100)["net_m"], 0)
        self.assertEqual(size(extra_reserve_m=100)["gap_m"], 450)

    def test_grid_monotonic_and_base_tie(self):
        panels = build_results(CONFIG)["grid_gap_m"]
        self.assertEqual(panels[1][4][1], size()["gap_m"])
        for panel in panels:
            for row in panel:
                self.assertEqual(row, sorted(row))
            for column in zip(*panel):
                self.assertEqual(list(column), sorted(column, reverse=True))

    def test_invalid_renewal_and_impossible_threshold(self):
        with self.assertRaises(ValueError):
            size(renewal=1.1)
        self.assertIsNone(size(backfill=1, rent_reset=.5)["min_renewal"])


if __name__ == "__main__":
    unittest.main()
