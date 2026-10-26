/** The Python ledger is the only spending writer. No credentials/prompts cross. */
import { execFile } from 'node:child_process';
import { join } from 'node:path';
import { engineCommand } from './engine';
import type { SpendReserve, SpendTransition, SpendObserve, SpendConfigure, SpendHistory, SpendReply } from '../../contracts/spending';
import schema from '../../contracts/spending.schema.json';
import { valid, type Schema } from './wire';
const defs=schema.$defs as Record<string,Schema>;
export type Spend = (query:SpendReserve|SpendTransition|SpendObserve|SpendConfigure|SpendHistory)=>Promise<SpendReply>;
export function spendingService(packaged:boolean,root:string,resources:string,userData:string):Spend {
  const command=engineCommand(packaged,root,resources);
  return query=>new Promise((resolve,reject)=> {
    if (!['SpendReserve','SpendTransition','SpendObserve','SpendConfigure','SpendHistory'].some(type=>valid(query,defs[type],defs))) {reject(new Error('Invalid spending request'));return;}
    const args=packaged?['--spending']:['-I','-m','poliscope_engine.spending_host'];
    const child=execFile(command.executable,[...args,'--database',join(userData,'assistant-private','spending.sqlite3')],{
      shell:false,windowsHide:true,encoding:'buffer',maxBuffer:1048576,timeout:15000,killSignal:'SIGKILL',
      env:Object.fromEntries(['SYSTEMROOT','WINDIR','TEMP','TMP','LANG','LC_ALL'].flatMap(k=>process.env[k]===undefined?[]:[[k,process.env[k]!]])),
    },(error,stdout)=> {
      try {
        if(error) throw error;
        const text=new TextDecoder('utf-8',{fatal:true}).decode(stdout);
        if (!text.endsWith('\n') || text.slice(0,-1).includes('\n')) throw new Error();
        const result:unknown=JSON.parse(text);
        if (!valid(result,defs.SpendReply,defs) || (result as SpendReply).dispatch_id!==query.binding.dispatch_id) throw new Error();
        resolve(result as SpendReply);
      }catch{reject(new Error('Spending service unavailable'));}
    });
    child.stdin?.on('error',()=>{});child.stdin?.end(JSON.stringify(query)+'\n');
  });
}
