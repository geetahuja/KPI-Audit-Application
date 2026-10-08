import fs from 'node:fs';
import {audit} from '../dist/engine.mjs';
const {workbooks,settings}=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const patterns=JSON.parse(fs.readFileSync(new URL('../dist/reference-patterns.json',import.meta.url),'utf8'));
process.stdout.write(JSON.stringify(audit(workbooks,{...settings,patterns})));
