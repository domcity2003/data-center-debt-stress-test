"""Build output/Data_Center_Debt_Stress_Test.xlsx with live Excel formulas.

Inputs: data/deal.json (facts, scenarios, grid axes) and data/workbook_layout.json
(sheet blocks and formulas). Run:

    uv run --with openpyxl python build_workbook.py

Then check the numbers against model.py inside Excel:

    uv run --with pywin32 --with pymupdf --with pillow python scripts/verify_workbook.py --render
"""

import datetime as dt
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "Data_Center_Debt_Stress_Test.xlsx"

NAVY, LIGHT, INPUT_FILL, INPUT_INK = "122B40", "DCEAF4", "E8F4FF", "13598E"
GREEN = "E0F1EC"
MONEY = '#,##0.0;(#,##0.0);"-"'
RATIO = '0.00"x"'

WIDTHS = {
    "Summary": [38, 16, 16, 16],
    "Stress Grid": [25, 14, 12, 12, 12, 12, 12, 12],
    "Assumptions": [36, 16, 16, 16, 63],
    "Sizing": [40, 16, 16, 16, 63],
    "Sources": [37, 17, 17, 41],
}
# 1-based row numbers. dark = merged navy band, headers = light-blue row,
# notes = merged wrapped text, right = right-aligned cells (headers over numbers).
STYLE = {
    "Summary": dict(dark=[1, 13], notes=[2, 14, 15, 16, 17], headers=[4], emphasis="A7:D9",
                    gaps=["B9:D9"], right=["B4:D4", "B5:D11"]),
    "Stress Grid": dict(dark=[1], notes=[2, 3, 44], headers=[6, 15, 24, 36, 46],
                        inputs=["B5", "B14", "B23", "C6:H6", "A7:A12", "C36:H36"],
                        gaps=["C7:H12", "C16:H21", "C25:H30", "C37:H42"],
                        right=["B6", "B15", "B24", "B36", "G46"]),
    "Assumptions": dict(dark=[1], notes=[2], headers=[4, 16], inputs=["B5:D14", "B17:B19"],
                        right=["B4:D4", "B16", "B21:D21"]),
    "Sizing": dict(dark=[1, 29], notes=[2], headers=[4, 30], emphasis="A20:D22",
                   gaps=["B22:D22", "D31:D34"], right=["B4:D4", "B19:D19", "B27:D27", "B30:D30"]),
    "Sources": dict(dark=[1, 16, 24], notes=[2, 25, 26, 27], headers=[4, 17],
                    right=["B4", "B17:D17"]),
}
FORMAT = {
    "Summary": [(MONEY, "B5:D11"), (RATIO, "B6:D6"), ("0.0%", "B11:D11")],
    "Stress Grid": [
        (MONEY, "B7:H12", "B16:H21", "B25:H30", "B37:H42"),
        ("0.0%", "B5", "B14", "B23", "A7:A12", "A16:A21", "A25:A30", "A37:A42"),
        ("0.00%", "C6:H6", "C15:H15", "C24:H24", "B35", "C36:H36", "G47:H47", "G48:H48"),
        (RATIO, "C33:H33"),
    ],
    "Assumptions": [("0.0%", "B5:D9", "B14:D14", "B17", "B19"), (MONEY, "B10:D10"),
                    ("0.00%", "B11:D12"), (RATIO, "B18")],
    "Sizing": [(MONEY, "B5:D27", "B31:D34"), ("0.0%", "B7:D7", "B27:D27"),
               (RATIO, "B12:D12"), ("0.00%", "B13:D13")],
    "Sources": [(MONEY, "B5:B14", "B20:D22"), ("0.00%", "B6"), ("mmm d, yyyy", "B7"),
                ("#,##0", "B9", "B18:D19"), ("0.0%", "B14")],
}
PRINT = {"Summary": "A1:D17", "Stress Grid": "A1:H49", "Assumptions": "A1:E21",
         "Sizing": "A1:E34", "Sources": "A1:D27"}

# Added to the Stress Grid: exit cap rate panel and the DSCR/LTV switch coupon.
# Panel NCF = same expression as the coupon panels, at Base rent reset and Base coupon.
_NCF = ("MAX(0,Sources!$B$12+(Sizing!$B$5*(($A{r}+(1-$A{r})*Assumptions!$B$6)*Assumptions!$B$7-1)"
        "+Sizing!$B$9)*Assumptions!$B$9-Assumptions!$B$10)")
_OK = 'Assumptions!$B$21="OK"'


def cap_grid_blocks(deal):
    caps, renewals = deal["grid"]["cap_rates"], deal["grid"]["renewals"]
    rows = [["Refinance coupon (Base)", "=Assumptions!B11", "Columns vary the exit cap rate"],
            ["CH3 renewal", "NCF ($m)", *caps]]
    for i in range(len(renewals)):
        r = 37 + i
        line = [f'=IF(ISNUMBER(A${7 + i}),A${7 + i},"")',
                f'=IF(AND({_OK},ISNUMBER($A{r}),$A{r}>=0,$A{r}<=1),{_NCF.format(r=r)},"")']
        for col in "CDEFGH":
            line.append(
                f'=IF(AND(ISNUMBER($B{r}),ISNUMBER({col}$36),{col}$36>0,ISNUMBER(Sizing!$B$13)),'
                f"MAX(0,Sources!$B$5-(1-Assumptions!$B$14)*$B{r}*MIN(Assumptions!$B$17/{col}$36,"
                f"1/(Sizing!$B$13*Assumptions!$B$18),1/Assumptions!$B$19)),\"\")")
        rows.append(line)
    return [
        ["Stress Grid", 34, 0, rows[:2]],
        ["Stress Grid", 36, 0, rows[2:]],
        ["Stress Grid", 43, 0, [[
            '="Exit cap rate panel: the Base case uses the KBRA July 2026 implied cap rate '
            "(60.1 / 686.5 = 8.75%). LTV binds, so value, not coupon, sets proceeds at any coupon below "
            '"&TEXT(G48,"0.00%")&"."']]],
        ["Stress Grid", 45, 0, [["Binding-test switch (Base)", None, None, None, None, None, "Value"]]],
        ["Stress Grid", 46, 0, [[
            "Target mortgage constant (cap rate ÷ (max LTV × min DSCR))", None, None, None, None, None,
            f'=IF({_OK},Assumptions!B12/(Assumptions!B17*Assumptions!B18),"")']]],
        ["Stress Grid", 47, 0, [[
            "Coupon at which DSCR replaces LTV as the binding test (Base)", None, None, None, None, None,
            f'=IF(AND({_OK},ISNUMBER(G47)),12*RATE(Assumptions!B13*12,-G47/12,1,0,0,0.0075),"")']]],
    ]


def put(ws, row, col, value):
    ws.cell(row=row, column=col).value = value


def cells(ws, spec):
    return ws[spec] if ":" in spec else ws[spec:spec]


def build():
    deal = json.loads((ROOT / "data/deal.json").read_text(encoding="utf-8"))
    blocks = json.loads((ROOT / "data/workbook_layout.json").read_text(encoding="utf-8"))
    blocks += cap_grid_blocks(deal)

    wb = Workbook()
    wb.remove(wb.active)
    sheets = {name: wb.create_sheet(name) for name in WIDTHS}

    for name, row0, col0, values in blocks:
        for i, line in enumerate(values):
            for j, value in enumerate(line):
                if value is not None:
                    put(sheets[name], row0 + i + 1, col0 + j + 1, value)

    # Source facts and editable defaults come from the same inputs as the Python model.
    s = sheets["Sources"]
    fact_keys = ["principal_m", "coupon", "maturity", "campus_mw", "campus_sf", "kncf_2025_m",
                 "value_2025_m", "kncf_2026_m", "value_2026_m", "kltv_2026"]
    for i, key in enumerate(fact_keys):
        value = deal["facts"][key]
        if key == "maturity":
            value = dt.date.fromisoformat(value)
        put(s, 5 + i, 2, value)
    for i, row in enumerate(deal["presale_rollover"]):
        for r, k in [(18, "campus_kw"), (19, "ch3_kw"), (20, "campus_rent_m"), (21, "ch3_rent_m")]:
            put(s, r, 2 + i, row[k])
    drivers = ["renewal", "backfill", "rent_reset", "other_realization", "flow_through",
               "extra_reserve_m", "rate", "cap_rate", "amort_years", "fee"]
    a = sheets["Assumptions"]
    for i, scenario in enumerate(deal["scenarios"]):
        for r, key in enumerate(drivers):
            put(a, 5 + r, 2 + i, scenario[key])
    for i, key in enumerate(["max_ltv", "min_dscr", "min_debt_yield"]):
        put(a, 17 + i, 2, deal["sizing_rules"][key])
    g = sheets["Stress Grid"]
    for i, value in enumerate(deal["grid"]["rates"]):
        put(g, 6, 3 + i, value)
    for i, value in enumerate(deal["grid"]["renewals"]):
        put(g, 7 + i, 1, value)
    for i, value in enumerate(deal["grid"]["rent_resets"]):
        put(g, 5 + i * 9, 2, value)

    fill = lambda color: PatternFill("solid", start_color=color, end_color=color)
    for name, widths in WIDTHS.items():
        ws, st = sheets[name], STYLE[name]
        last = len(widths)
        lastc = get_column_letter(last)
        for row in range(1, 51):
            ws.row_dimensions[row].height = 19
            for col in range(1, last + 1):
                ws.cell(row=row, column=col).font = Font(name="Calibri", size=11, color=NAVY)
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = "A4" if name == "Stress Grid" else "A5"
        for i, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(i + 1)].width = w

        def band(rows, color, ink, merge):
            for row in rows:
                if merge:
                    ws.merge_cells(f"A{row}:{lastc}{row}")
                for col in range(1, last + 1):
                    c = ws.cell(row=row, column=col)
                    c.fill = fill(color)
                    c.font = Font(name="Calibri", size=16 if row == 1 else 11, bold=True, color=ink)
                    c.alignment = Alignment(vertical="center")
                ws.row_dimensions[row].height = 33 if row == 1 else 24

        band(st["dark"], NAVY, "FFFFFF", True)
        band(st["headers"], LIGHT, NAVY, False)
        for row in st["notes"]:
            ws.merge_cells(f"A{row}:{lastc}{row}")
            ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="center")
            ws.row_dimensions[row].height = 32
        for spec in st.get("inputs", []):
            for c in (x for row in cells(ws, spec) for x in row):
                c.fill = fill(INPUT_FILL)
                c.font = Font(name="Calibri", size=11, bold=c.font.bold, color=INPUT_INK)
        if "emphasis" in st:
            for row in cells(ws, st["emphasis"]):
                for c in row:
                    c.fill = fill(GREEN)
                    c.font = Font(name="Calibri", size=11, bold=True, color=NAVY)
        for spec in st.get("gaps", []):
            first = spec.split(":")[0]
            ws.conditional_formatting.add(spec, FormulaRule(
                formula=[f"AND(ISNUMBER({first}),{first}>0.005)"],
                fill=fill("FBE7DF"), font=Font(bold=True, color="8A321E")))
        for spec in st.get("right", []):
            for row in cells(ws, spec):
                for c in row:
                    c.alignment = Alignment(horizontal="right", vertical="center")
        for mask, *specs in FORMAT[name]:
            for spec in specs:
                for row in cells(ws, spec):
                    for c in row:
                        c.number_format = mask
        ws.print_area = PRINT[name]
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        ws.print_options.horizontalCentered = True

    for name, spec in (("Sizing", "E4:E34"), ("Assumptions", "E4:E21"), ("Sources", "C4:D14")):
        for row in sheets[name][spec]:
            for c in row:
                c.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=c.alignment.wrap_text)

    # Stress Grid extras: merged label/value cells in the switch block.
    for row in (46, 47, 48):
        g.merge_cells(f"A{row}:F{row}")
        g.merge_cells(f"G{row}:H{row}")
    g.merge_cells("C35:H35")
    g["C35"].alignment = Alignment(horizontal="left", vertical="bottom", indent=1)
    g["B35"].font = Font(name="Calibri", size=11, color=NAVY)
    g["G48"].font = Font(name="Calibri", size=11, bold=True, color=NAVY)
    g["A48"].font = Font(name="Calibri", size=11, bold=True, color=NAVY)
    for row in (47, 48):
        g.cell(row=row, column=1).alignment = Alignment(vertical="center")

    wb.properties.creator = "Dominic Bavuso"
    wb.properties.lastModifiedBy = "Dominic Bavuso"
    wb.properties.title = "DATA 2023-CNTR debt stress test"
    wb.calculation.fullCalcOnLoad = True
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
