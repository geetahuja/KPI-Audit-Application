import fs from 'node:fs';
import {audit} from '../dist/engine.mjs';
const paths=process.argv.slice(2);if(!paths.length){console.error('Usage: node scripts/audit.mjs parsed-workbook.json [...]');process.exit(1);}
const workbooks=paths.map(p=>JSON.parse(fs.readFileSync(p,'utf8')));
const report=audit(workbooks,{patterns:JSON.parse(fs.readFileSync(new URL('../dist/reference-patterns.json',import.meta.url),'utf8'))});
process.stdout.write(JSON.stringify(report,null,2));
