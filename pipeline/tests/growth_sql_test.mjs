// Run with PGLITE_MODULE pointing at an installed @electric-sql/pglite entrypoint.
// All data is synthetic; this never connects to an external database.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const db = new PGlite();
const admin = '00000000-0000-0000-0000-000000000001';
await db.exec(`
  create role anon; create role authenticated; create role service_role;
  create schema auth;
  create function auth.uid() returns uuid language sql stable as
    $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
  create function auth.role() returns text language sql stable as
    $$ select current_setting('request.jwt.claim.role',true) $$;
  create function public.is_admin() returns boolean language sql stable security definer as
    $$ select coalesce(auth.uid()='${admin}'::uuid,false) $$;
`);
const migration = await readFile(new URL('../../supabase/15_search_growth.sql', import.meta.url),'utf8');
await db.exec(migration);
await db.exec(migration); // Safe to apply twice.
const role = async (name, user='') => {
  await db.exec('reset role');
  await db.query("select set_config('request.jwt.claim.role',$1,false), set_config('request.jwt.claim.sub',$2,false)",[name,user]);
  await db.exec(`set role ${name}`);
};
const snapshot={property:'sc-domain:openedu4u.com',source:'gsc_csv',kind:'performance',searchType:'Web (text-based)',
  period:{start:'2026-09-17',end:'2026-10-14'},totals:{clicks:5,impressions:188}};
const report={...snapshot,pages:[],queries:[],findings:[{ruleId:'traffic.drop',subjectKey:'2026-09-03',title:'검색 노출 급감',severity:'P0',evidence:{cause:'unknown'}}]};
await role('service_role');
await db.query('select growth_publish($1,$2,$3)',['snapshot-one',snapshot,report]);
const duplicate=await db.query('select growth_publish($1,$2,$3) as result',['snapshot-one',snapshot,report]);
assert.equal(duplicate.rows[0].result.published,false);
await role('anon');
await assert.rejects(()=>db.query('select * from growth_reports'),/permission denied/);
await assert.rejects(()=>db.query("select growth_overview('snapshot-one')"),/permission denied/);
await role('authenticated','00000000-0000-0000-0000-000000000002');
assert.equal((await db.query('select * from growth_reports')).rows.length,0);
await assert.rejects(()=>db.query("select growth_overview('snapshot-one')"),/ADMIN_REQUIRED/);
await assert.rejects(()=>db.query("update growth_tasks set state='verified'"),/permission denied/);
await role('authenticated',admin);
assert.equal((await db.query('select * from growth_reports')).rows.length,1);
assert.equal((await db.query("select growth_overview('snapshot-one') as result")).rows[0].result.pageCount,0);
const task=(await db.query('select * from growth_tasks')).rows[0];
assert.equal(task.version,1);
const transition=(state,version)=>db.query('select growth_transition_task($1,$2,$3,$4) as task',[task.id,version,state,'검증 메모']);
await transition('ready',1);
await assert.rejects(()=>transition('in_progress',1),/VERSION_CONFLICT/);
await transition('in_progress',2);
await assert.rejects(()=>transition('deployed',3),/DEPLOY_VERIFICATION_REQUIRED/);
await db.query('select growth_record_change($1,$2,$3,$4)',[task.id,'1234567','test-deploy','https://openedu4u.com/a/100.html']);
await transition('deployed',3);
await transition('observing',4);
await transition('verified',5);
await assert.rejects(()=>db.query('select growth_create_experiment($1,$2,$3,$4,$5)',
  ['sc-domain:openedu4u.com','충분한 길이의 검증 가설',['https://openedu4u.com/a/1.html'],['https://openedu4u.com/a/1.html'],'clicks']),/COHORT_OVERLAP/);
await db.query('select growth_create_experiment($1,$2,$3,$4,$5)',
  ['sc-domain:openedu4u.com','충분한 길이의 검증 가설',['https://openedu4u.com/a/1.html'],[],'clicks']);
assert.equal((await db.query('select * from growth_experiments')).rows.length,1);
await role('authenticated','00000000-0000-0000-0000-000000000002');
assert.equal((await db.query('select * from growth_experiments')).rows.length,0);
console.log('PASS: migration idempotency, publishing deduplication, RLS, RPC authorization, optimistic locking, deployment gate, cohort isolation.');
await db.close();
