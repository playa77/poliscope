import { it, expect } from 'vitest';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { ProviderController } from '../../desktop/main/providers';
import { WorkspaceController } from '../../desktop/main/workspace';

it('exports only civilization records even when its selected folder also contains the approved credential store', async () => {
  const directory=await mkdtemp(join(tmpdir(),'poliscope-provider-export-'));
  const canary='synthetic-provider-key-MUST-STAY-IN-MAIN';
  // Fixture ciphertext stands in for OS encryption; no plaintext serialization.
  const encrypted=Buffer.from('synthetic-opaque-encrypted-material');
  const providers=new ProviderController(directory,{isEncryptionAvailable:()=>true,getSelectedStorageBackend:()=> 'gnome_libsecret',encryptString:()=>encrypted,decryptString:()=>{throw new Error('not needed');}},async()=>200);
  try {
    const profile={id:'fixture',name:'Provider-only preference',kind:'openai-compatible',endpoint:'https://provider-only.example/v1',model:'private-provider-model',
      generation:{temperature:null,top_p:null,max_output_tokens:null},routing:{order:[],only:[],ignore:[],allow_fallbacks:false,require_parameters:true,data_collection:'deny'},
      capabilities:{text:'unknown',image:'unknown',audio:'unknown',video:'unknown',tools:'unknown',structured_output:'unknown',reasoning:'unknown'}};
    await providers.request({action:'save',profile,expected_revision:null});
    await providers.request({action:'replace-key',profile_id:'fixture',expected_revision:1,key:canary});
    const workspace=new WorkspaceController(false,resolve('.'),'');
    await workspace.choose(directory);
    await workspace.create({name:'Synthetic offline world',setup:'blank',scope_name:'Home',population:'14',land_area:null});
    const archive=join(directory,'history.poliscope');
    expect((await workspace.archive({action:'export'},async()=>archive)).status).toBe('complete');
    const {stdout}=await promisify(execFile)(resolve('.venv/bin/python'),['-I','-c',
      'import json,sys,zipfile\nwith zipfile.ZipFile(sys.argv[1]) as archive:\n print(json.dumps({n:archive.read(n).decode("utf-8") for n in archive.namelist()}))',archive],{encoding:'utf8',maxBuffer:2*1024*1024,timeout:10000});
    for(const forbidden of [canary,'credential-fixture','provider-only.example','private-provider-model',encrypted.toString(),encrypted.toString('base64')]) expect(stdout).not.toContain(forbidden);
    const database=await readFile(join(directory,'poliscope.sqlite3'));
    expect(database.includes(Buffer.from(canary))).toBe(false);expect(database.includes(encrypted)).toBe(false);
    expect(await readFile(join(directory,'providers/credential-fixture.bin'))).toEqual(encrypted);
  } finally {await providers.close();await rm(directory,{recursive:true,force:true});}
},30000);
