"""Open the workbook in Excel (COM), recalculate, and compare every output to model.py.

    uv run --with pywin32 --with pymupdf --with pillow python scripts/verify_workbook.py [--render] [--no-save]

Checks: Summary metrics, all stress-grid panels (coupon and exit cap rate), the isolated
diligence shocks on Sizing, the DSCR switch coupon, and two input-sensitivity cases.
Unless --no-save, saves the workbook from Excel after a full recalculation so it carries cached
values, then re-patches fullCalcOnLoad and re-verifies from the saved file.
--render writes one PNG per sheet to .qa/ and docs/stress-grid.png (needs Excel + PyMuPDF + Pillow).
"""

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "output" / "Data_Center_Debt_Stress_Test.xlsx"
TOL = 1e-6
stats = {"checked": 0, "max_diff": 0.0, "fail": []}


def expected():
    out = subprocess.run([sys.executable, str(ROOT / "model.py")], capture_output=True, text=True,
                         check=True, cwd=ROOT).stdout
    return json.loads(out)


def close(actual, target, label):
    stats["checked"] += 1
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        stats["fail"].append(f"{label}: got {actual!r}, expected {target}")
        return
    d = abs(actual - target)
    stats["max_diff"] = max(stats["max_diff"], d)
    if d > TOL:
        stats["fail"].append(f"{label}: got {actual}, expected {target}")


def check(cond, label):
    stats["checked"] += 1
    if not cond:
        stats["fail"].append(label)


def compare(wb, exp):
    sm, sg, sz = (wb.Worksheets(n) for n in ("Summary", "Stress Grid", "Sizing"))
    metrics = ["ncf_m", "existing_coverage", "net_m", "cushion_m", "gap_m", "binding", "min_renewal"]
    for i, case in enumerate(exp["cases"]):
        for j, k in enumerate(metrics):
            addr = f"{'BCD'[i]}{5 + j}"
            v = sm.Range(addr).Value2
            if k == "binding":
                check(v == case[k], f"Summary!{addr}: {v!r} != {case[k]}")
            elif k == "min_renewal" and case[k] is None:
                check(v == "Not reachable", f"Summary!{addr}: {v!r}, expected 'Not reachable'")
            else:
                close(v, case[k], f"Summary!{addr}")
    for i, panel in enumerate(exp["grid_gap_m"]):
        for j, row in enumerate(panel):
            for k, gap in enumerate(row):
                a = f"{'CDEFGH'[k]}{7 + i * 9 + j}"
                close(sg.Range(a).Value2, gap, f"Stress Grid!{a}")
    for j, row in enumerate(exp["cap_grid_gap_m"]):
        for k, gap in enumerate(row):
            a = f"{'CDEFGH'[k]}{37 + j}"
            close(sg.Range(a).Value2, gap, f"Stress Grid!{a}")
    for i, row in enumerate(exp["diligence"]):
        close(sz.Range(f"D{31 + i}").Value2, row["gap_m"], f"Sizing!D{31 + i}")
    close(sg.Range("G48").Value2, exp["dscr_binding_rate"], "Stress Grid!G48 (DSCR switch coupon)")


def with_excel(fn):
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        return fn(xl)
    finally:
        xl.Quit()


def patch_fullcalc(path):
    """Excel drops fullCalcOnLoad when it saves; put it back so viewers recalculate on open."""
    tmp = Path(tempfile.mkdtemp()) / "patched.xlsx"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/workbook.xml":
                text = data.decode("utf-8")
                if "fullCalcOnLoad" not in text:
                    if "<calcPr" in text:
                        text = text.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
                    else:
                        text = text.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
                data = text.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)


def run_checks(xl, exp, save):
    wb = xl.Workbooks.Open(str(XLSX))
    xl.CalculateFull()
    compare(wb, exp)
    a, sm = wb.Worksheets("Assumptions"), wb.Worksheets("Summary")
    base = a.Range("B5").Value2
    a.Range("B5").Value2 = 0
    xl.CalculateFull()
    check(isinstance(sm.Range("B9").Value2, float) and sm.Range("B9").Value2 > 90,
          f"renewal=0 should give base gap > 90, got {sm.Range('B9').Value2!r}")
    a.Range("B5").ClearContents()
    xl.CalculateFull()
    check(sm.Range("B9").Value2 == "Check inputs",
          f"blank renewal should show 'Check inputs', got {sm.Range('B9').Value2!r}")
    a.Range("B5").Value2 = base
    xl.CalculateFull()
    close(sm.Range("B9").Value2, exp["cases"][0]["gap_m"], "restored Summary!B9")
    if save:
        wb.Worksheets("Summary").Activate()
        wb.Save()
    wb.Close(SaveChanges=False)


def render(xl):
    import fitz  # PyMuPDF
    from PIL import Image, ImageChops

    qa, docs = ROOT / ".qa", ROOT / "docs"
    qa.mkdir(exist_ok=True)
    docs.mkdir(exist_ok=True)
    wb = xl.Workbooks.Open(str(XLSX))
    tmp = Path(tempfile.mkdtemp())
    for ws in wb.Worksheets:
        pdf = tmp / f"{ws.Name}.pdf"
        ws.ExportAsFixedFormat(0, str(pdf))
        page = fitz.open(pdf)[0]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        bg = Image.new("RGB", img.size, (255, 255, 255))
        box = ImageChops.difference(img, bg).getbbox()
        img = img.crop(box)
        img.save(qa / f"{ws.Name}.png")
        if ws.Name == "Stress Grid":
            w = 1200
            img.resize((w, round(img.height * w / img.width)), Image.LANCZOS).save(docs / "stress-grid.png")
    wb.Close(SaveChanges=False)


def main():
    exp = expected()
    save = "--no-save" not in sys.argv

    with_excel(lambda xl: run_checks(xl, exp, save))
    if save:
        patch_fullcalc(XLSX)
        # Re-verify the saved file (fresh recalc plus cached-value read without recalculation).
        with_excel(lambda xl: run_checks(xl, exp, False))
        def cached(xl):
            wb = xl.Workbooks.Open(str(XLSX))
            compare(wb, exp)  # no CalculateFull: reads whatever values Excel loaded
            wb.Close(SaveChanges=False)
        with_excel(cached)
    if "--render" in sys.argv:
        with_excel(render)

    print(f"cells/conditions checked: {stats['checked']}  max abs diff: {stats['max_diff']:.3e}")
    if stats["fail"]:
        print("FAILURES:")
        print("\n".join(stats["fail"]))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
