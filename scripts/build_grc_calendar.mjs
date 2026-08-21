import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const root = process.cwd();
const tmpDir = path.join(root, ".tmp-grc-calendar-xlsx");
const outputDir = path.join(root, "assets", "tools");
const outputFile = path.join(outputDir, "grc-calendar-2026.xlsx");

const ns = {
  main: "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
  rel: "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function excelDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = Date.UTC(year, month - 1, day);
  const epoch = Date.UTC(1899, 11, 30);
  return Math.round((date - epoch) / 86400000);
}

function colName(index) {
  let name = "";
  let n = index;
  while (n >= 0) {
    name = String.fromCharCode((n % 26) + 65) + name;
    n = Math.floor(n / 26) - 1;
  }
  return name;
}

function cellRef(row, col) {
  return `${colName(col)}${row + 1}`;
}

function textCell(row, col, value, style = 0) {
  return `<c r="${cellRef(row, col)}" t="inlineStr" s="${style}"><is><t>${esc(value)}</t></is></c>`;
}

function numberCell(row, col, value, style = 0) {
  return `<c r="${cellRef(row, col)}" s="${style}"><v>${value}</v></c>`;
}

function rowXml(index, cells, height = null) {
  const ht = height ? ` ht="${height}" customHeight="1"` : "";
  return `<row r="${index + 1}"${ht}>${cells.join("")}</row>`;
}

function worksheetXml({ columns, rows, freezeRow = 1, autoFilter = null }) {
  const colXml = columns
    .map((width, idx) => `<col min="${idx + 1}" max="${idx + 1}" width="${width}" customWidth="1"/>`)
    .join("");
  const pane = freezeRow
    ? `<sheetViews><sheetView workbookViewId="0"><pane ySplit="${freezeRow}" topLeftCell="A${freezeRow + 1}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>`
    : `<sheetViews><sheetView workbookViewId="0"/></sheetViews>`;
  const filter = autoFilter ? `<autoFilter ref="${autoFilter}"/>` : "";
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="${ns.main}" xmlns:r="${ns.rel}">
${pane}
<sheetFormatPr defaultRowHeight="18"/>
<cols>${colXml}</cols>
<sheetData>${rows.join("")}</sheetData>
${filter}
<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>`;
}

const calendarHeaders = [
  "Due date",
  "Month",
  "Cadence",
  "Activity",
  "Primary owner",
  "Framework / driver",
  "Output / evidence",
  "Priority",
  "Status",
  "Notes",
];

const calendarRows = [
  ["2026-01-15", "January", "Annual", "Confirm GRC operating calendar, reporting cadence, and control owners", "CISO / GRC Lead", "ISO 27001, NIS2, DORA, internal governance", "Approved GRC calendar and RACI", "High", "Planned", "Run before annual planning locks."],
  ["2026-01-31", "January", "Annual", "Refresh risk appetite, risk taxonomy, and board-level cyber risk themes", "CISO / Enterprise Risk", "Board governance, ISO 27001 clause 6", "Updated risk appetite and top risk themes", "High", "Planned", "Useful input for board reporting."],
  ["2026-02-15", "February", "Quarterly", "Update information asset and critical service inventory", "IT Risk / Service Owners", "NIS2, DORA, ISO 27001 A.5.9", "Inventory export and owner attestation", "High", "Planned", "Include outsourced and SaaS dependencies."],
  ["2026-02-28", "February", "Quarterly", "Review critical supplier list and tiering", "TPRM Lead / Procurement", "NIS2 supply chain, DORA ICT third-party risk", "Critical supplier register", "High", "Planned", "Check concentration and nth-party dependencies."],
  ["2026-03-15", "March", "Quarterly", "Review open audit findings, risk acceptances, and remediation aging", "GRC Lead / Control Owners", "Internal audit, ISO 27001 improvement", "Remediation tracker and overdue actions", "High", "Planned", "Highlight aging exceptions for leadership."],
  ["2026-03-31", "March", "Quarterly", "Prepare Q1 cyber and GRC board report", "CISO", "Board reporting, NIS2 management accountability", "Board pack and decision log", "High", "Planned", "Focus on decisions, not operational noise."],
  ["2026-04-15", "April", "Semi-annual", "Run access governance review for privileged and critical business systems", "IAM Lead / System Owners", "ISO 27001 A.5.15, A.5.18", "Access review evidence and exceptions", "High", "Planned", "Include third-party and admin accounts."],
  ["2026-04-30", "April", "Quarterly", "Test incident escalation and regulatory notification workflow", "Security Operations / Legal", "NIS2, DORA incident reporting", "Exercise results and improvement actions", "High", "Planned", "Tabletop is enough if evidence is captured."],
  ["2026-05-15", "May", "Annual", "Review cybersecurity policies and control ownership", "CISO / Policy Owners", "ISO 27001 policy framework", "Policy review log and approvals", "Medium", "Planned", "Prioritize policies with audit relevance."],
  ["2026-05-31", "May", "Quarterly", "Review vulnerability and patch SLA performance", "Security Operations / IT Operations", "ISO 27001 A.8.8, operational resilience", "Patch KPI report and exceptions", "High", "Planned", "Show trend and unresolved critical items."],
  ["2026-06-15", "June", "Semi-annual", "Validate backup, recovery, and resilience evidence", "IT Operations / BCM", "DORA, NIS2, ISO 27001 A.5.30", "Recovery test record and gaps", "High", "Planned", "Connect to critical services."],
  ["2026-06-30", "June", "Quarterly", "Prepare Q2 board report and regulatory readiness update", "CISO / GRC Lead", "Board governance, compliance readiness", "Board pack and readiness heatmap", "High", "Planned", "Include supplier and incident-readiness view."],
  ["2026-07-15", "July", "Quarterly", "Refresh AI / shadow IT register", "CIO / CISO / Data Governance", "AI governance, data protection, third-party risk", "AI use case register", "Medium", "Planned", "Capture owner, data type, provider, approval state."],
  ["2026-07-31", "July", "Quarterly", "Review security awareness and phishing metrics", "Security Awareness Lead", "ISO 27001 A.6.3, management reporting", "Awareness KPI report", "Medium", "Planned", "Tie poor results to targeted actions."],
  ["2026-08-15", "August", "Quarterly", "Review supplier incidents, risk signals, and watchlist", "TPRM Lead / Security Operations", "Continuous monitoring, NIS2 supply chain", "Supplier watchlist and actions", "High", "Planned", "Use public incidents, ratings, questionnaires, issues."],
  ["2026-08-31", "August", "Annual", "Plan autumn audit and evidence collection sprint", "GRC Lead / Internal Audit", "ISO 27001, SOC 2, internal audit", "Evidence collection plan", "Medium", "Planned", "Reduce last-minute audit pressure."],
  ["2026-09-15", "September", "Semi-annual", "Run business continuity and crisis communication tabletop", "BCM / CISO / Legal / Comms", "DORA, NIS2, operational resilience", "Exercise report and action plan", "High", "Planned", "Include supplier breach scenario."],
  ["2026-09-30", "September", "Quarterly", "Prepare Q3 board report and budget/risk trade-off view", "CISO / CIO", "Board reporting, risk treatment", "Board pack and risk decision list", "High", "Planned", "Connect risks to investment decisions."],
  ["2026-10-15", "October", "Annual", "Review cyber insurance, contractual clauses, and supplier audit rights", "Legal / Procurement / CISO", "TPRM, DORA contractual requirements", "Contractual control review", "Medium", "Planned", "Prioritize critical ICT and data suppliers."],
  ["2026-10-31", "October", "Quarterly", "Review exceptions, accepted risks, and expiring risk decisions", "Enterprise Risk / GRC Lead", "Risk management, ISO 27001 clause 6", "Risk acceptance register", "High", "Planned", "Escalate expired or repeatedly extended exceptions."],
  ["2026-11-15", "November", "Annual", "Refresh next-year GRC roadmap and maturity objectives", "CISO / CIO / GRC Lead", "Strategic planning", "GRC roadmap draft", "Medium", "Planned", "Use lessons from incidents and audits."],
  ["2026-11-30", "November", "Annual", "Confirm control testing plan for next year", "GRC Lead / Internal Audit", "ISO 27001, internal control system", "Control testing plan", "Medium", "Planned", "Align with audit and regulatory calendar."],
  ["2026-12-15", "December", "Annual", "Close annual risk review and confirm top residual risks", "CISO / Enterprise Risk", "Board governance, ISO 27001 management review", "Annual risk review output", "High", "Planned", "Feed into management review."],
  ["2026-12-31", "December", "Annual", "Prepare year-end cyber, resilience, and third-party risk summary", "CISO / GRC Lead", "Board reporting, annual reporting", "Year-end executive summary", "High", "Planned", "Use as input for January planning."],
];

const backlogHeaders = ["Tool area", "Example artifact", "Use in practice", "Audience", "Publication status"];
const backlogRows = [
  ["Governance", "Board cyber report template", "Monthly or quarterly executive reporting", "CISO, CIO, board secretary", "Backlog"],
  ["Metrics", "Security KPI dashboard", "Operational metrics with leadership context", "CISO, SecOps, IT risk", "Backlog"],
  ["Third-party risk", "Vendor risk register", "Critical supplier tracking and review cadence", "TPRM, procurement, CISO", "Backlog"],
  ["AI governance", "AI use case and risk register", "Shadow AI discovery and approval workflow", "CIO, CISO, legal", "Backlog"],
  ["Incident response", "Supplier breach response checklist", "Clear actions when a vendor is compromised", "CISO, legal, comms", "Backlog"],
  ["Audit readiness", "ISO 27001 evidence tracker", "Evidence ownership and audit preparation", "ISMS manager, GRC", "Backlog"],
];

const cadenceHeaders = ["Cadence", "Typical activities", "Recommended output", "Leadership question answered"];
const cadenceRows = [
  ["Monthly", "Patch/vulnerability review, supplier watchlist, open findings aging", "Operational exception summary", "Where are we accumulating preventable risk?"],
  ["Quarterly", "Risk register update, board report, supplier tiering review, incident workflow check", "Executive GRC pack", "What decisions or escalations are needed?"],
  ["Semi-annual", "Access review, resilience tabletop, recovery evidence validation", "Control assurance evidence", "Can we prove the controls still work?"],
  ["Annual", "Risk appetite, policy refresh, control testing plan, year-end summary", "Management review package", "What should change next year?"],
];

function buildTableSheet(name, headers, data, widths) {
  const rows = [];
  rows.push(rowXml(0, headers.map((h, idx) => textCell(0, idx, h, 1)), 24));
  data.forEach((record, ridx) => {
    const rowIndex = ridx + 1;
    const cells = record.map((value, cidx) => {
      if (cidx === 0 && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
        return numberCell(rowIndex, cidx, excelDate(value), 3);
      }
      return textCell(rowIndex, cidx, value, cidx === 7 && value === "High" ? 4 : 2);
    });
    rows.push(rowXml(rowIndex, cells, 42));
  });
  const lastCol = colName(headers.length - 1);
  return worksheetXml({
    columns: widths,
    rows,
    freezeRow: 1,
    autoFilter: `A1:${lastCol}${data.length + 1}`,
  });
}

function readmeSheet() {
  const rows = [
    rowXml(0, [textCell(0, 0, "GRC Calendar 2026", 5)], 30),
    rowXml(1, [textCell(1, 0, "Purpose", 1), textCell(1, 1, "A practical governance, risk and compliance operating calendar for CIO/CISO/GRC teams.", 2)], 34),
    rowXml(2, [textCell(2, 0, "How to use", 1), textCell(2, 1, "Assign owners, adjust dates to your regulatory calendar, and review upcoming items in monthly leadership meetings.", 2)], 48),
    rowXml(3, [textCell(3, 0, "Best fit", 1), textCell(3, 1, "Mid-sized organizations that need a lightweight rhythm for GRC, third-party risk, resilience, and board reporting.", 2)], 48),
    rowXml(4, [textCell(4, 0, "Important note", 1), textCell(4, 1, "This is a planning aid, not legal advice. Align it with your exact sector, jurisdictions, regulators, and internal policies.", 2)], 48),
    rowXml(6, [textCell(6, 0, "Included sheets", 1), textCell(6, 1, "GRC Calendar 2026, Tool Backlog, Cadence Model", 2)], 30),
  ];
  return worksheetXml({ columns: [22, 100], rows, freezeRow: 0 });
}

const styles = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="${ns.main}">
<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/></numFmts>
<fonts count="3">
<font><sz val="10"/><color rgb="FF242424"/><name val="Aptos"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>
<font><b/><sz val="16"/><color rgb="FF1F4E79"/><name val="Aptos Display"/></font>
</fonts>
<fills count="5">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEAF2F8"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFE5CC"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD9E2EC"/></left><right style="thin"><color rgb="FFD9E2EC"/></right><top style="thin"><color rgb="FFD9E2EC"/></top><bottom style="thin"><color rgb="FFD9E2EC"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="6">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

const files = {
  "[Content_Types].xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`,
  "_rels/.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`,
  "docProps/core.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>GRC Calendar 2026</dc:title><dc:creator>Gabriel Hasik</dc:creator><cp:lastModifiedBy>Gabriel Hasik</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-08-21T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-08-21T00:00:00Z</dcterms:modified>
</cp:coreProperties>`,
  "docProps/app.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex</Application></Properties>`,
  "xl/workbook.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="${ns.main}" xmlns:r="${ns.rel}">
<sheets>
<sheet name="README" sheetId="1" r:id="rId1"/>
<sheet name="GRC Calendar 2026" sheetId="2" r:id="rId2"/>
<sheet name="Tool Backlog" sheetId="3" r:id="rId3"/>
<sheet name="Cadence Model" sheetId="4" r:id="rId4"/>
</sheets>
</workbook>`,
  "xl/_rels/workbook.xml.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>
<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>
<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`,
  "xl/styles.xml": styles,
  "xl/worksheets/sheet1.xml": readmeSheet(),
  "xl/worksheets/sheet2.xml": buildTableSheet("GRC Calendar 2026", calendarHeaders, calendarRows, [13, 12, 14, 42, 24, 31, 32, 11, 12, 42]),
  "xl/worksheets/sheet3.xml": buildTableSheet("Tool Backlog", backlogHeaders, backlogRows, [22, 32, 46, 30, 18]),
  "xl/worksheets/sheet4.xml": buildTableSheet("Cadence Model", cadenceHeaders, cadenceRows, [16, 56, 32, 42]),
};

async function writeFiles() {
  await fs.rm(tmpDir, { recursive: true, force: true });
  await fs.mkdir(tmpDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (const [relative, content] of Object.entries(files)) {
    const file = path.join(tmpDir, relative);
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, content, "utf8");
  }
  if (existsSync(outputFile)) {
    await fs.rm(outputFile);
  }
  await execFileAsync("zip", ["-qr", outputFile, "."], { cwd: tmpDir });
  await fs.rm(tmpDir, { recursive: true, force: true });
  console.log(outputFile);
}

await writeFiles();
