# Data Center Debt Stress Test

This loan-level credit surveillance case study models the August 2033 maturity of DATA 2023-CNTR, a $450 million mortgage secured by two Chicago-area data centers. The downside covers current interest **1.93x** but leaves a **$102.1 million refinancing gap**. That gap is the cash the sponsor would need to raise beyond the modeled net proceeds, before any credit for sponsor liquidity.

[Read the two-page credit memo](output/DATA_2023_CNTR_Credit_Memo.pdf) · [Download the editable Excel model](output/Data_Center_Debt_Stress_Test.xlsx) · [Inspect deal inputs](data/deal.json)

| Case | Existing interest coverage | Net proceeds | Payoff cushion | Funding gap |
| --- | ---: | ---: | ---: | ---: |
| Base | 2.30x | $450.6m | $0.6m | $0 |
| Downside | 1.93x | $347.9m | — | $102.1m |
| Severe | 1.54x | $252.0m | — | $198.0m |

## Try the model

Open **Stress Grid** and find the 95% CH3 renewal row in the flat-rent panel. At a 7.25% refinance coupon, the model shows a $0.6m payoff cushion. At 10.00%, the gap is $36.0m and the binding constraint switches from loan-to-value to debt-service coverage. The grid shows a dash when no funding gap remains. To run your own case, edit the blue cells on **Assumptions**, then trace the proceeds on **Sizing**.

The 2023 presale identifies 27 MW and $30.8m in annual base rent at CH3 scheduled to expire in 2026–27. The model uses that cohort to size a rent shock against KBRA's July 2026 campus cash-flow estimate. The priority diligence request is the current rent roll and signed amendments showing which CH3 suites pay contracted rent through August 2033. The workbook's **Sources** tab and the memo identify the vintage and location of each disclosure.

## Reproduce

```text
python model.py
python -m unittest -v
```

The Python report returns three named scenarios, a 108-cell sensitivity grid and four diligence shocks. In the downside JSON entry, `gap_m` is approximately `102.08`. The model and six tests use the Python standard library. The checked-in Excel and PDF artifacts open without a build.

To regenerate the memo, install ReportLab and run `python build_memo.py`. To regenerate the workbook, run `node build_workbook.mjs --render` with the Codex runtime's Node and `@oai/artifact-tool`. If needed, set `CODEX_PRIMARY_RUNTIME_NODE_MODULES` and `CODEX_PRIMARY_RUNTIME_PYTHON` to the runtime module directory and Python executable.

## Review notes

- Reconciled the 2023 CH3 and campus lease cohorts and kept them separate from July 2026 surveillance. The 2026 cash-flow anchor and old suite exposure cannot be reconciled at lease level from those disclosures. Treat the NCF bridge as a sensitivity proxy.
- Checked a hand-calculated base, break-even, monotonicity, negative NCF, and a rate shock that changes the binding lender test. The workbook builder compares the named cases, 108 stress-grid cells and four diligence cases against Python and exercises changed and missing inputs.
- [AbsBox](https://github.com/yellowbean/AbsBox) is relevant prior art for certificate waterfall analysis. This project ends at mortgage payoff proceeds, so the core has no waterfall dependency. The memo and outputs are illustrative underwriting research.
