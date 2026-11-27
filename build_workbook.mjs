import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const dep = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const { Workbook, SpreadsheetFile } = dep
  ? await import(pathToFileURL(path.join(dep, "@oai/artifact-tool/dist/artifact_tool.mjs")).href)
  : await import("@oai/artifact-tool");
const read = async name => JSON.parse(await fs.readFile(path.join(root, name), "utf8"));
const deal = await read("data/deal.json");
const blocks = await read("data/workbook_layout.json");
const python = process.env.CODEX_PRIMARY_RUNTIME_PYTHON || "python";
const expected = JSON.parse(execFileSync(python, [path.join(root, "model.py")], { encoding: "utf8" }));
const wb = Workbook.create();
const settings = {
  Summary: [38, 16, 16, 16],
  "Stress Grid": [25, 14, 12, 12, 12, 12, 12, 12],
  Assumptions: [36, 16, 16, 16, 63],
  Sizing: [40, 16, 16, 16, 63],
  Sources: [37, 17, 17, 41],
};
const sheet = Object.fromEntries(Object.keys(settings).map(n => [n, wb.worksheets.add(n)]));
const navy = "#122B40";
const money = '#,##0.0;(#,##0.0);"-"';
const ratio = '0.00"x"';
const c = (name, address) => sheet[name].getRange(address);
const write = (name, address, value) => { c(name, address).values = [[value]]; };
const readCell = (name, address) => c(name, address).values[0][0];

for (const [name, row, col, values] of blocks) {
  values.forEach((line, i) => line.forEach((value, j) => {
    if (value === null) return;
    const cell = sheet[name].getCell(row+i,col+j);
    if (typeof value === "string" && value.startsWith("=")) cell.formulas = [[value]];
    else cell.values = [[value]];
  }));
}

// Source facts and editable defaults come from the same inputs as the Python model.
const factKeys = ["principal_m","coupon","maturity","campus_mw","campus_sf",
  "kncf_2025_m","value_2025_m","kncf_2026_m","value_2026_m","kltv_2026"];
factKeys.forEach((key,i) => {
  let value = deal.facts[key];
  if (typeof value === "string") value = Math.round(Date.parse(value)/86400000)+25569;
  write("Sources",`B${5+i}`,value);
});
for (const [i, row] of deal.presale_rollover.entries()) {
  for (const [r,k] of [[18,"campus_kw"],[19,"ch3_kw"],[20,"campus_rent_m"],[21,"ch3_rent_m"]]) {
    write("Sources",`${"BC"[i]}${r}`,row[k]);
  }
}
const drivers = ["renewal","backfill","rent_reset","other_realization","flow_through",
  "extra_reserve_m","rate","cap_rate","amort_years","fee"];
for (const [i, scenario] of deal.scenarios.entries()) {
  drivers.forEach((key,r)=>write("Assumptions",`${"BCD"[i]}${5+r}`,scenario[key]));
}
["max_ltv","min_dscr","min_debt_yield"].forEach((key,i)=>
  write("Assumptions",`B${17+i}`,deal.sizing_rules[key]));
deal.grid.rates.forEach((value,i)=>write("Stress Grid",`${"CDEFGH"[i]}6`,value));
deal.grid.renewals.forEach((value,i)=>write("Stress Grid",`A${7+i}`,value));
deal.grid.rent_resets.forEach((value,i)=>write("Stress Grid",`B${5+i*9}`,value));

const style = {
  Summary: { dark:[1,13], notes:[2,14,15,16,17], headers:[4], emphasis:"A7:D9", gaps:["B9:D9"] },
  "Stress Grid": { dark:[1], notes:[2,3], headers:[6,15,24], inputs:["B5","B14","B23","C6:H6","A7:A12"], gaps:["C7:H12","C16:H21","C25:H30"] },
  Assumptions: { dark:[1], notes:[2], headers:[4,16], inputs:["B5:D14","B17:B19"] },
  Sizing: { dark:[1,29], notes:[2], headers:[4,30], emphasis:"A20:D22", gaps:["B22:D22","D31:D34"] },
  Sources: { dark:[1,16,24], notes:[2,25,26,27], headers:[4,17] },
};
const format = {
  Summary:[[money,"B5:D11"],[ratio,"B6:D6"],["0.0%","B11:D11"]],
  "Stress Grid":[[money,"B7:H12","B16:H21","B25:H30"],["0.0%","B5","B14","B23","A7:A12","A16:A21","A25:A30"],["0.00%","C6:H6","C15:H15","C24:H24"],[ratio,"C33:H33"]],
  Assumptions:[["0.0%","B5:D9","B14:D14","B17","B19"],[money,"B10:D10"],["0.00%","B11:D12"],[ratio,"B18"]],
  Sizing:[[money,"B5:D27","B31:D34"],["0.0%","B7:D7","B27:D27"],[ratio,"B12:D12"],["0.00%","B13:D13"]],
  Sources:[[money,"B5:B14","B20:D22"],["0.00%","B6"],["mmm d, yyyy","B7"],["#,##0","B9","B18:D19"],["0.0%","B14"]],
};

for (const [name, widths] of Object.entries(settings)) {
  const last = "ABCDEFGH"[widths.length-1];
  const full = c(name,`A1:${last}35`);
  full.format.font.name = "Calibri";
  full.format.font.color = navy;
  full.format.rowHeight = 19;
  sheet[name].showGridLines = false;
  sheet[name].freezePanes.freezeRows(name === "Stress Grid" ? 3 : 4);
  widths.forEach((width,i)=>c(name,`${"ABCDEFGH"[i]}1`).format.columnWidth=width);
  const paint = (rows,fill,ink,merge) => {
    for (const row of rows) {
      const band = c(name,`A${row}:${last}${row}`);
      if (merge) band.merge();
      band.format.fill=fill; band.format.font.color=ink; band.format.font.bold=true;
      band.format.rowHeight=row===1?33:24;
      if(row===1)band.format.font.size=16;
    }
  };
  const s=style[name];
  paint(s.dark,navy,"#FFFFFF",true);
  paint(s.headers,"#DCEAF4",navy,false);
  for(const row of s.notes) {
    const note=c(name,`A${row}:${last}${row}`);
    note.merge(); note.format.wrapText=true; note.format.rowHeight=32;
  }
  for(const address of s.inputs||[]) {
    c(name,address).format.fill="#E8F4FF";
    c(name,address).format.font.color="#13598E";
  }
  if(s.emphasis) {
    c(name,s.emphasis).format.fill="#E0F1EC";
    c(name,s.emphasis).format.font.bold=true;
  }
  for(const address of s.gaps||[])c(name,address).conditionalFormats.add("cellIs",{
    operator:"greaterThan",formula:0.005,format:{fill:"#FBE7DF",font:{color:"#8A321E",bold:true}},
  });
  for(const [mask,...addresses] of format[name])for(const address of addresses)c(name,address).setNumberFormat(mask);
}
wb.recalculate();
const close=(actual,target,label)=>assert.ok(typeof actual==="number"&&Math.abs(actual-target)<1e-7,
  `${label} actual ${actual}, expected ${target}`);
const metrics=["ncf_m","existing_coverage","net_m","cushion_m","gap_m","binding","min_renewal"];
for(const [i,row] of expected.cases.entries()) for(const [j,k] of metrics.entries()) {
  const a=`${"BCD"[i]}${5+j}`, value=readCell("Summary",a);
  if(k==="binding") assert.equal(value,row[k]); else close(value,row[k],a);
}
expected.grid_gap_m.forEach((panel,i)=>panel.forEach((row,j)=>row.forEach((gap,k)=>{
  const a=`${"CDEFGH"[k]}${7+i*9+j}`; close(readCell("Stress Grid",a),gap,a);
})));
expected.diligence.forEach((row,i)=>close(readCell("Sizing",`D${31+i}`),row.gap_m,row.label));
write("Assumptions","B5",0); wb.recalculate();
assert.ok(readCell("Summary","B9")>90);
write("Assumptions","B5",null); wb.recalculate();
assert.equal(readCell("Summary","B9"),"Check inputs");
write("Assumptions","B5",deal.scenarios[0].renewal); wb.recalculate();
close(readCell("Summary","B9"),0,"restored base case");
await fs.mkdir(path.join(root,"output"),{recursive:true});
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(root,"output/Data_Center_Debt_Stress_Test.xlsx"));
if(process.argv.includes("--render")) {
  const qa=path.join(root,".qa");
  await fs.mkdir(qa,{recursive:true});
  for(const [name,range] of Object.entries({
    Summary:"A1:D17","Stress Grid":"A1:H33",Assumptions:"A1:E21",Sizing:"A1:E34",Sources:"A1:D27",
  })) {
    const png=await wb.render({sheetName:name,range,scale:1,format:"png"});
    await fs.writeFile(path.join(qa,`${name}.png`),new Uint8Array(await png.arrayBuffer()));
  }
}
console.log("Verified named cases, 108 grid cells, diligence shocks and input recalculation.");
