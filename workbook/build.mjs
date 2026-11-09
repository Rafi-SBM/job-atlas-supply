import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const sample = args.includes('--sample');
const input = process.env.JOB_ATLAS_EXPORT_DIR ? path.resolve(process.env.JOB_ATLAS_EXPORT_DIR) : path.join(root, 'outputs/job-atlas');
const manifest = JSON.parse(await fs.readFile(path.join(input, 'manifest.json'), 'utf8'));
const output = sample ? path.join(root, 'artifacts/workbook-qa') : path.join(input, 'workbooks');
await fs.mkdir(output, { recursive: true });
const maxSheets = Number(process.env.WORKBOOK_MAX_SHEETS || 150);
const maxRows = Number(process.env.WORKBOOK_MAX_ROWS || 15000);
const platformArg = args.indexOf('--platforms');
const platforms = platformArg >= 0 ? args[platformArg+1].split(',') : null;
const selected = (sample ? manifest.companies.slice(0, 3) : manifest.companies).filter(c=>!platforms || platforms.includes(c.platform));
const groups = [];
let group = [], rows = 0;
for (const c of [...selected].sort((a,b)=>a.platform.localeCompare(b.platform)||a.company.localeCompare(b.company))) {
  if (group.length && (group[0].platform !== c.platform || group.length >= maxSheets || rows + c.jobs > maxRows)) { groups.push(group); group = []; rows = 0; }
  group.push(c); rows += c.jobs;
}
if (group.length) groups.push(group);
function volumeName(g) {
  const platform = groups[g][0].platform;
  const n = groups.slice(0,g+1).filter(x=>x[0].platform===platform).length;
  return `${platform}-${String(n).padStart(3,'0')}.xlsx`;
}
if (!sample && !args.includes('--child')) {
  // A separate process per volume releases the workbook engine's native memory.
  let next = 0;
  const failures = [];
  const concurrency = Math.max(1,Math.min(4,Number(process.env.WORKBOOK_CONCURRENCY || 3)));
  await Promise.all(Array.from({length:concurrency},async()=>{
    while(next<groups.length) {
      const g = next++;
      try {
        await new Promise((resolve,reject)=>{
          const child = spawn(process.execPath,[import.meta.filename,...args,'--child',String(g)],{stdio:'inherit',env:process.env});
          child.once('error',reject);
          child.once('exit',code=>code===0?resolve():reject(new Error(`Volume ${g+1} failed (${code})`)));
        });
      } catch(error) { failures.push(error); }
    }
  }));
  if(failures.length) throw failures[0];
  const all = [];
  const expectedFiles = new Set(groups.map((_,g)=>volumeName(g)+'.index.json'));
  for(const entry of (await fs.readdir(output)).filter(x=>x.endsWith('.xlsx.index.json')).sort()) {
    if(!expectedFiles.has(entry)) continue;
    const part = JSON.parse(await fs.readFile(path.join(output,entry),'utf8'));
    all.push(...part.index);
  }
  await writeIndex(all);
  console.log(`Complete: ${all.length} company sheets, ${all.reduce((s,c)=>s+c.jobs,0)} jobs.`);
  process.exit(0);
}
const index = [];
const columns = [
  ['title','Job title',64], ['location','Location',46], ['workplace','Work arrangement',20],
  ['department','Department',36], ['employment_type','Employment type',22],
  ['published_at','Published at (UTC)',22], ['updated_at','Updated at (UTC)',22],
  ['salary_min','Salary minimum',18], ['salary_max','Salary maximum',18],
  ['salary_currency','Currency',12], ['salary_interval','Pay interval',16], ['salary_text','Compensation supplied by source',55],
  ['url','Employer job URL',70], ['apply_url','Apply URL',70], ['checked_at','Checked at (UTC)',23],
  ['source_url','Source feed URL',70], ['date_note','Source date / coverage note',80],
  ['platform','Platform',20], ['board','Board identifier',42], ['job_id','Job ID',40],
  ['key','Unique posting key',65], ['company_key','Company key',45],
];
function clean(v) { return typeof v === 'string' && /^[\s]*[=+@-]/.test(v) ? `'${v}` : v ?? null; }
const dateColumns = new Set(['published_at','updated_at','checked_at']);
function excelDate(v) {
  if (!v) return null;
  const d = new Date(v);
  return Number.isNaN(d.valueOf()) ? null : (d.valueOf() / 86400000) + 25569;
}
function sheetName(c, used) {
  let name = c.company.replace(/[\\/*?:\[\]]/g,' ').replace(/^'+|'+$/g,'').trim() || 'Company';
  if (name.length > 31 || used.has(name.toLowerCase()) || name.toLowerCase() === 'index') {
    name = name.slice(0, 23) + ' ' + crypto.createHash('sha256').update(c.company_key).digest('hex').slice(0,7);
  }
  used.add(name.toLowerCase());
  return name;
}
function style(sheet, range, header) {
  sheet.showGridLines = false;
  const r = sheet.getRange(range);
  r.format.font.name = 'Arial';
  r.format.font.size = 10;
  r.format.font.color = '#27372D';
  r.format.verticalAlignment = 'center';
  r.format.rowHeight = 29;
  if (header) {
    const h = sheet.getRange(header);
    h.format.fill = '#203E32';
    h.format.font.color = '#FFFFFF';
    h.format.font.bold = true;
    h.format.wrapText = true;
    h.format.rowHeight = 34;
    h.format.horizontalAlignment = 'center';
  }
}

for (let g = 0; g < groups.length; g++) {
  if(args.includes('--child') && g!==Number(args[args.indexOf('--child')+1])) continue;
  const filename = volumeName(g);
  const signature = crypto.createHash('sha256').update('layout-v2|' + groups[g].map(c=>`${c.company_key}:${c.data_sha256||c.jobs}`).join('|')).digest('hex');
  if (!sample && args.includes('--resume')) {
    try {
      const existing = JSON.parse(await fs.readFile(path.join(output, filename + '.index.json'), 'utf8'));
      if (existing.signature === signature) {
        await fs.access(path.join(output, filename)); index.push(...existing.index); console.log(`Reused ${filename}`); continue;
      }
    } catch {}
  }
  const wb = Workbook.create();
  const cover = wb.worksheets.add('Index');
  const used = new Set(['index']);
  const companyRows = [];
  const sheetRecords = [];
  for (let i=0; i<groups[g].length; i++) {
    const company = groups[g][i];
    const data = JSON.parse(await fs.readFile(path.join(input,'company_data',company.data_file),'utf8'));
    if (data.rows.length !== company.jobs) throw new Error(`Count mismatch for ${company.company_key}`);
    const name = sheetName(company, used);
    const sh = wb.worksheets.add(name);
    sh.getRange('A2').values = [[company.company]];
    sh.getRange('A2:V3').format.font.name = 'Arial';
    sh.getRange('A2').format.font.size = 14;
    sh.getRange('A2').format.font.bold = true;
    sh.getRange('A3').values = [[`${company.jobs.toLocaleString()} listed jobs · ${company.platform}`]];
    sh.getRange('A3').format.font.color = '#738365';
    const values = [columns.map(c=>c[1]), ...data.rows.map(row => columns.map(([key]) => dateColumns.has(key) ? excelDate(row[key]) : clean(row[key])))];
    sh.getRangeByIndexes(4,0,values.length,columns.length).values = values;
    const end = values.length + 4;
    style(sh, `A5:V${end}`, 'A5:V5');
    sh.getRange(`A6:F${end}`).format.wrapText = true;
    // Fitted rows preserve full titles and long locations at readable font sizes.
    for (let r=0; r<data.rows.length; r++) {
      const j = data.rows[r];
      const lines = Math.max(1,Math.ceil(String(j.title||'').length/72),Math.ceil(String(j.location||'').length/50),Math.ceil(String(j.department||'').length/40));
      sh.getRangeByIndexes(r+5,0,1,columns.length).format.rowHeight = Math.min(409,Math.max(29,lines*15+9));
    }
    columns.forEach(([key,,width],col) => {
      sh.getRangeByIndexes(4,col,values.length,1).format.columnWidth = width;
      if (dateColumns.has(key)) sh.getRangeByIndexes(5,col,data.rows.length,1).setNumberFormat('dd mmm yyyy hh:mm');
      else if (key === 'salary_min' || key === 'salary_max') sh.getRangeByIndexes(5,col,data.rows.length,1).setNumberFormat('#,##0.00');
    });
    const table = sh.tables.add(`A5:V${end}`,true,`Company_${g+1}_${i+1}`);
    table.style = 'TableStyleLight1';
    table.showFilterButton = true;
    sh.freezePanes.freezeRows(5);
    sh.freezePanes.freezeColumns(1);
    companyRows.push([company.company, company.platform, company.jobs, name, company.company_key]);
    const item = {company:company.company,company_key:company.company_key,platform:company.platform,jobs:company.jobs,workbook:filename,sheet:name};
    index.push(item); sheetRecords.push({name,count:company.jobs,first:data.rows[0].title,last:data.rows.at(-1).title});
  }
  cover.tabColor = '#203E32';
  cover.getRange('A2').values = [[`Job Atlas · ${groups[g][0].platform} · ${filename.replace('.xlsx','')}`]];
  cover.getRange('A2').format.font.size = 14;
  cover.getRange('A2').format.font.bold = true;
  cover.getRange('A3').values = [[`Collected ${manifest.exported_at.slice(0,10)} · employer listings at check time`]];
  cover.getRange('A3').format.font.color = '#738365';
  cover.getRange('A4').values = [['Listed jobs in this volume']];
  cover.getRange('B4').formulas = [[`=SUM(C7:C${6+companyRows.length})`]];
  cover.getRange('B4').setNumberFormat('#,##0');
  cover.getRange('A6:E6').values = [['Company','Platform','Listed jobs','Worksheet','Company key']];
  cover.getRangeByIndexes(6,0,companyRows.length,5).values = companyRows;
  style(cover,`A6:E${6+companyRows.length}`,'A6:E6');
  for(const [col,width] of [['A',52],['B',22],['C',18],['D',36],['E',55]]) cover.getRange(`${col}6:${col}${6+companyRows.length}`).format.columnWidth = width;
  cover.getRange(`A7:A${6+companyRows.length}`).format.wrapText = true;
  cover.getRange('A2:E2').format.rowHeight = 27;
  cover.getRange('C7:C'+(6+companyRows.length)).setNumberFormat('#,##0');
  cover.tables.add(`A6:E${6+companyRows.length}`,true,`Index_${g+1}`).style = 'TableStyleLight1';
  cover.freezePanes.freezeRows(6);
  wb.recalculate();
  const total = groups[g].reduce((n,c)=>n+c.jobs,0);
  if (Number(cover.getRange('B4').values[0][0]) !== total) throw new Error('Workbook total does not reconcile');
  for (const record of sheetRecords) {
    const sh = wb.worksheets.getItem(record.name);
    if (sh.getRange('A6').values[0][0] !== clean(record.first) || sh.getRange('A'+(record.count+5)).values[0][0] !== clean(record.last)) throw new Error(`Sheet boundary mismatch ${record.name}`);
  }
  if (sample || g === 0 || g === groups.length-1) {
    const preview = await wb.render({sheetName:sheetRecords[0].name, range:'A1:F10',scale:1.4,format:'png'});
    await fs.writeFile(path.join(output,`preview-${g+1}.png`),new Uint8Array(await preview.arrayBuffer()));
    const coverPreview = await wb.render({sheetName:'Index',range:'A1:D12',scale:1.4,format:'png'});
    await fs.writeFile(path.join(output,`index-preview-${g+1}.png`),new Uint8Array(await coverPreview.arrayBuffer()));
    console.log((await wb.inspect({kind:'table',range:'Index!A4:C9',include:'values,formulas',tableMaxRows:6,tableMaxCols:3,maxChars:1200})).ndjson);
  }
  const file = await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(output,filename));
  await fs.unlink(path.join(output,filename+'.inspect.ndjson')).catch(error=>{if(error.code!=='ENOENT') throw error;});
  await fs.writeFile(path.join(output,filename+'.index.json'),JSON.stringify({signature,companies:groups[g].map(c=>c.company_key),rows:total,index:index.slice(-groups[g].length)}));
  console.log(`${g+1}/${groups.length} ${filename}: ${groups[g].length} companies, ${total.toLocaleString()} jobs`);
}
await writeIndex(index);
async function writeIndex(index) {
await fs.writeFile(path.join(output,'workbook-index.json'),JSON.stringify(index,null,2));
const csvCell = v => '"' + String(clean(v) ?? '').replaceAll('"','""') + '"';
await fs.writeFile(path.join(output,'workbook-index.csv'),'\ufeffcompany,company_key,platform,jobs,workbook,sheet\r\n'+index.map(c=>[c.company,c.company_key,c.platform,c.jobs,c.workbook,c.sheet].map(csvCell).join(',')).join('\r\n'));
}
if (sample) console.log(`Complete: ${index.length} company sheets, ${index.reduce((s,c)=>s+c.jobs,0)} jobs.`);
