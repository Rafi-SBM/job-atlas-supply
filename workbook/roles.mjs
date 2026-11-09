import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
// Small native previews only. Full rows are exported by the bundled streaming
// writer after the Artifact exporter exceeded its heap limit on large sheets.
import {Workbook} from '@oai/artifact-tool';

const root=path.resolve(import.meta.dirname,'..');
const folderArg=process.argv.indexOf('--folder');
const folder=folderArg<0?path.join(root,'outputs/united_states/role_sheets'):path.resolve(process.argv[folderArg+1]);
const manifest=JSON.parse(await fs.readFile(path.join(folder,'manifest.json'),'utf8'));
const active=manifest.fields.includes('active_status');
const previews=path.join(folder,'previews');
await fs.mkdir(previews,{recursive:true});
const child=process.argv.indexOf('--sheet');
if(child<0){
  let baseline={};
  if(process.argv.includes('--reuse-unchanged')){
   try{baseline=JSON.parse(await fs.readFile(path.join(folder,'preview_baseline.json'),'utf8'));}catch{}
  }
  const queue=[-1];
  for(let i=0;i<manifest.groups.length;i++){
   const group=manifest.groups[i];
   if(baseline[group.name]===group.jobs){
    try{await fs.access(path.join(previews,group.part+'.png'));if(active)await fs.access(path.join(previews,group.part+'.verification.png'));console.log(`Reused reviewed preview: ${group.name}`);continue;}catch{}
   }
   queue.push(i);
  }
  let next=0;const failures=[];
  await Promise.all(Array.from({length:3},async()=>{
    while(next<queue.length){const i=queue[next++];
      try{await new Promise((resolve,reject)=>{const p=spawn(process.execPath,[import.meta.filename,'--folder',folder,'--sheet',String(i)],{stdio:'inherit'});p.on('error',reject);p.on('exit',code=>code===0?resolve():reject(new Error(`Sheet ${i}: ${code}`)));});}
      catch(e){failures.push(e.message);}
    }
  }));
  if(failures.length)throw new Error(failures.join('; '));
  console.log(`All ${manifest.groups.length} role previews and the Index are rendered.`);
  process.exit(0);
}
const i=Number(process.argv[child+1]);
const group=i<0?{name:'Index',part:'index.xlsx',jobs:0}:manifest.groups[i];
const data=i<0?null:JSON.parse(await fs.readFile(path.join(folder,group.file),'utf8'));
if(data)data.rows=data.rows.slice(0,4);
const wb=Workbook.create();const sh=wb.worksheets.add(group.name);sh.showGridLines=false;
const clean=v=>typeof v==='string'&&/^\s*[=+@-]/.test(v)?`'${v}`:v??null;
const columns=[
 ['title','Job title',74],['company','Company',36],['location','Location',52],['workplace','Work arrangement',20],
 ['employment_type','Employment type',22],['department','Department',36],
 ['salary_min','Salary minimum',18],['salary_max','Salary maximum',18],['salary_currency','Currency',13],['salary_interval','Pay interval',20],['salary_text','Compensation supplied by source',60],
 ['published_at','Published at',23],['updated_at','Updated at',23],['checked_at','Checked at (UTC)',23],
 ['url','Employer job URL',80],['apply_url','Application URL',80],['source_url','Source feed URL',80],
 ['country','Country',20],['us_location_evidence','US location evidence',46],['date_note','Source date or coverage note',85],
 ['platform','Platform',20],['board','Board identifier',44],['job_id','Job ID',44],['company_key','Company key',50],['key','Unique posting key',75],
];
const dates=new Set(['published_at','updated_at','checked_at']);
if(active){
 columns.splice(columns.length-1,0,
  ['active_status','Application status',42],['active_verified_at','Applications verified at (UTC)',28],
  ['verification_method','Verification method',60],['verification_url','Live verification URL',90],
  ['verification_evidence','Evidence of application availability',100]);
 dates.add('active_verified_at');
}
const lastCol=active?'AD':'Y';
function value(row,key){
 const v=row[key];
 if(dates.has(key)){if(!v)return null;const n=Date.parse(v);return Number.isNaN(n)?clean(v):n/86400000+25569;}
 if(key==='salary_min'||key==='salary_max'){return v===''||v==null?null:Number.isFinite(Number(v))?Number(v):clean(v);}
 return clean(v);
}
sh.getRange('A2').values=[[i<0?(active?'Active US jobs by role':'US jobs by role'):group.name]];
sh.getRange('A2').format={font:{name:'Arial',size:16,bold:true,color:'#203E32'},rowHeight:30};
sh.getRange('A3').values=[[i<0?'Original titles retained. One primary role family per job.':`${group.jobs.toLocaleString()} US jobs · sorted by title and company`]];
sh.getRange('A3').format={font:{name:'Arial',size:10,color:'#738365'},rowHeight:20};
if(i<0){
 sh.tabColor='#203E32';
 sh.getRange('A4').values=[[active?'Application-verified US jobs':'Total US jobs']];sh.getRange('B4').formulas=[[`=SUM(B8:B${7+manifest.groups.length})`]];sh.getRange('B4').setNumberFormat('#,##0');
 if(active&&manifest.verified_from){
  const start=new Date(manifest.verified_from);const end=new Date(manifest.verified_to);
  const date=start.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
  sh.getRange('A5').values=[[`Application checks: ${date}, ${start.toISOString().slice(11,16)} to ${end.toISOString().slice(11,16)} UTC`]];
  sh.getRange('A5').format.font={name:'Arial',size:10,color:'#738365'};
 }
 sh.getRange('A6').values=[['Grouping uses job titles, with department as fallback.']];sh.getRange('A6').format.font={name:'Arial',size:10,color:'#738365'};
 sh.getRange('A7:C7').values=[['Role family','Jobs','Share of jobs']];
 sh.getRangeByIndexes(7,0,manifest.groups.length,2).values=manifest.groups.map(g=>[g.name,g.jobs]);
 sh.getRangeByIndexes(7,2,manifest.groups.length,1).formulas=manifest.groups.map((_,n)=>[`=B${n+8}/$B$4`]);
 const end=7+manifest.groups.length;
 sh.getRange(`A7:C${end}`).format.font={name:'Arial',size:10,color:'#27372D'};
 sh.getRange(`A7:C${end}`).format.rowHeight=26;
 sh.getRange(`A7:A${end}`).format.columnWidth=46;sh.getRange(`B7:B${end}`).format.columnWidth=18;sh.getRange(`C7:C${end}`).format.columnWidth=20;
 sh.getRange(`B8:B${end}`).setNumberFormat('#,##0');sh.getRange(`C8:C${end}`).setNumberFormat('0.0%');
 sh.getRange('A7:C7').format={fill:'#203E32',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center'};
 sh.freezePanes.freezeRows(7);
}else{
 const matrix=[columns.map(c=>c[1]),...data.rows.map(row=>columns.map(([key])=>value(row,key)))];
 const end=5+data.rows.length;
 sh.getRangeByIndexes(4,0,matrix.length,columns.length).values=matrix;
 sh.getRange(`A5:${lastCol}${end}`).format.font={name:'Arial',size:10,color:'#27372D'};
 sh.getRange(`A5:${lastCol}${end}`).format.verticalAlignment='center';
 sh.getRange(`A5:${lastCol}${end}`).format.rowHeight=32;
 sh.getRange(`A6:F${end}`).format.wrapText=true;
 if(active)sh.getRange(`AC6:AC${end}`).format.wrapText=true;
 sh.getRange(`A5:${lastCol}5`).format={fill:'#203E32',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:36,horizontalAlignment:'center',wrapText:true};
 columns.forEach(([key,,width],col)=>{
  sh.getRangeByIndexes(4,col,matrix.length,1).format.columnWidth=width;
  if(dates.has(key))sh.getRangeByIndexes(5,col,data.rows.length,1).setNumberFormat('dd mmm yyyy hh:mm');
  if(key==='salary_min'||key==='salary_max')sh.getRangeByIndexes(5,col,data.rows.length,1).setNumberFormat('#,##0.00');
 });
 // Only unusually long text needs a taller row; the normal two-line height is shared.
 for(let r=0;r<data.rows.length;r++){
  const j=data.rows[r];const lines=Math.max(Math.ceil(j.title.length/90),Math.ceil(j.company.length/40),Math.ceil(j.location.length/58),Math.ceil(j.department.length/42));
  if(lines>2)sh.getRangeByIndexes(r+5,0,1,columns.length).format.rowHeight=Math.min(409,lines*15+6);
 }
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);
}
wb.recalculate();
if(i<0&&Number(sh.getRange('B4').values[0][0])!==manifest.total_jobs)throw new Error('Index total mismatch');
if(i>=0&&(sh.getRange(lastCol+'6').values[0][0]!==data.rows[0].key||sh.getRange(lastCol+(5+data.rows.length)).values[0][0]!==data.rows.at(-1).key))throw new Error('Data boundary mismatch');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:3},maxChars:600});
if(errors.ndjson.includes('"cell"'))console.log(errors.ndjson);
const preview=await wb.render({sheetName:group.name,range:i<0?'A1:C17':'A1:F9',scale:1.1,format:'png'});
await fs.writeFile(path.join(previews,group.part+'.png'),new Uint8Array(await preview.arrayBuffer()));
if(active&&i>=0){
 const proof=await wb.render({sheetName:group.name,range:'Y5:AC9',scale:1.1,format:'png'});
 await fs.writeFile(path.join(previews,group.part+'.verification.png'),new Uint8Array(await proof.arrayBuffer()));
}
console.log(`Rendered sample for ${group.name}: ${group.jobs.toLocaleString()} jobs`);
