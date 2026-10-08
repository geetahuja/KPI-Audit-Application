import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import {webcrypto} from 'node:crypto';
import assert from 'node:assert/strict';
import {readWorkbook,reportXlsx} from '../dist/xlsx.mjs';
import {audit} from '../dist/engine.mjs';
const root=new URL('../',import.meta.url);
vm.runInThisContext(fs.readFileSync(new URL('dist/vendor/jszip.min.js',root),'utf8'));
if(!globalThis.crypto)Object.defineProperty(globalThis,"crypto",{value:webcrypto});
class Node {
 constructor(n){this.localName=n.name;this.attrs=n.attrs;this.own=n.text;this.tail=n.tail;this.children=n.children.map(x=>new Node(x));}
 get textContent(){return this.own+this.children.map(c=>c.textContent+c.tail).join('');}
 getAttribute(n){return this.attrs[n]??this.attrs['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'+n.replace('r:','')]??null;}
 getAttributeNS(ns,n){return this.attrs[`{${ns}}${n}`]??null;}
 getElementsByTagNameNS(ns,n){return this.children.flatMap(c=>[...(c.localName===n?[c]:[]),...c.getElementsByTagNameNS(ns,n)]);}
}
globalThis.DOMParser=class {parseFromString(text){const q=spawnSync('python',[new URL('tests/xml_dom.py',root).pathname],{input:text,encoding:'utf8',maxBuffer:100*1024*1024});if(q.status!==0)throw Error(q.stderr);return new Node({name:'document',attrs:{},text:'',tail:'',children:[JSON.parse(q.stdout)]});}};
const folder=process.argv[2];if(!folder)throw Error('Supply reference workbook folder');const books=[];
for(const name of fs.readdirSync(folder).filter(n=>n.endsWith('.xlsx'))){const b=fs.readFileSync(folder+'/'+name);const w=await readWorkbook({name,size:b.length,arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)});books.push(w);assert(w.sheets.length>10);assert(w.sheets.some(s=>s.name==='Data Add Sheet'));console.log(name,w.sheets.length,'sheets parsed via browser parser');}
const result=audit(books,{patterns:JSON.parse(fs.readFileSync(new URL('dist/reference-patterns.json',root),'utf8'))});for(const r of result.results){assert(r.kpis.length>=18);assert(r.coverage.verified>0);}
for(const r of result.results.filter(r=>r.company==='Entech Controls'))assert(!r.issues.some(i=>i.severity==='Critical'&&['Formula','KPI Logic'].includes(i.type)),'Clean Entech must not gain critical formula errors');
const output=process.argv[3];if(output){fs.writeFileSync(output,JSON.stringify(result,null,2));const xlsx=await reportXlsx(result.results[0]);fs.writeFileSync(output+'.xlsx',Buffer.from(await xlsx.arrayBuffer()));}
console.log('Browser parser and report integration passed for',books.length,'workbooks.');
