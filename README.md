# Data Center Debt Stress Test

How much can a new lender advance against two Chicago-area data centers when their $450 million mortgage comes due in August 2033? This project sizes the takeout using the lowest of three lender limits and shows the cash a sponsor would need to supply at closing.

| Case | Existing interest coverage | Net proceeds | Payoff cushion | Funding gap |
| --- | ---: | ---: | ---: | ---: |
| Base | 2.30x | $450.6m | $0.6m | $0 |
| Downside | 1.93x | $347.9m | — | $102.1m |
| Severe | 1.54x | $252.0m | — | $198.0m |

[Excel model](output/Data_Center_Debt_Stress_Test.xlsx) · [Two-page credit memo](output/DATA_2023_CNTR_Credit_Memo.pdf) · [Public inputs and assumptions](data/deal.json)

## Try the model

Open **Summary**, then change the blue cells on **Assumptions**. On **Stress Grid**, compare the 95% renewal row at the 7.25% and 10.00% refinance coupons with flat CH3 rent. The payoff moves from a small surplus to a $36.0m gap. **Sizing** traces the value, coverage and debt-yield constraints and shows which one binds. **Sources** gives the disclosure dates and page numbers.

The presale CH3 cohorts represent 27 MW and $30.8m of annual base rent scheduled to expire in 2026–27 as of the original disclosure. The model measures a rent shock against KBRA's July 2026 campus cash-flow anchor. The new rent roll and signed amendments are the highest-priority diligence items because the public surveillance release does not establish individual lease terms through the 2033 payoff. No default probability, sponsor liquidity or bond waterfall is assumed.

## Reproduce

```text
python model.py
python -m unittest -v
```

The calculations use the Python standard library. To regenerate the memo, install ReportLab and run `python build_memo.py`. The workbook generator uses the Codex runtime's Node and `@oai/artifact-tool`. With those available, run `node build_workbook.mjs --render`. Set `CODEX_PRIMARY_RUNTIME_NODE_MODULES` to the runtime package directory if the module is not resolvable, and set `CODEX_PRIMARY_RUNTIME_PYTHON` if needed. The checked-in Excel file opens without a build.

## Review notes

- Reconciled the 2023 CH3 and campus lease cohorts and kept them separate from July 2026 surveillance. The 2026 cash-flow anchor and old suite exposure cannot be reconciled at lease level from those disclosures. Treat the NCF bridge as a sensitivity proxy.
- Checked a hand-calculated base, break-even, monotonicity, negative NCF, and a rate shock that changes the binding lender test. The workbook builder compares the named cases, 108 stress-grid cells and four diligence cases against Python and exercises changed and missing inputs.
- [AbsBox](https://github.com/yellowbean/AbsBox) is relevant prior art for certificate waterfall analysis. This project ends at mortgage payoff proceeds, so the core has no waterfall dependency. The memo and outputs are illustrative underwriting research.
