import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../../../app/web/analytics.js', import.meta.url),'utf8').replace(/const ID = '[^']+';/, "const ID = 'G-TEST123';");
function browser(href='https://openedu4u.com/', stored=null){
 const events={}; const elements=[]; const scripts=[];
 class El {
  constructor(tag){this.tagName=tag;this.hidden=false;this.listeners={};this.dataset={};this.children=[];}
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  focus(){}
  append(...x){this.children.push(...x);elements.push(...x);}
  appendChild(x){this.append(x);if(x.tagName==='script')scripts.push(x);}
  querySelectorAll(){return this.buttons ||= ['granted','denied'].map(choice=>{const b=new El('button');b.dataset.choice=choice;return b;});}
  querySelector(){return this.buttons?.[0] || new El('button');}
 }
 const document={readyState:'complete',referrer:'https://www.google.com/search?q=private',createElement:t=>new El(t),head:new El('head'),body:new El('body')};
 const window={addEventListener:(k,f)=>events[k]=f};
 const storage=new Map(stored?[['openedu.analytics.v1',stored]]:[]);
 const context={window,document,location:new URL(href),URL,URLSearchParams,Date,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
 vm.runInNewContext(code,context);
 const route=url=>{context.location=new URL(url);events.hashchange();};
 const choose=choice=>elements.find(e=>e.id==='oe-analytics').querySelectorAll().find(b=>b.dataset.choice===choice).listeners.click();
 return {window,document,context,events,elements,scripts,storage,route,choose};
}
test('no Google request before consent, including unknown/denied choices',()=>{
 for(const consent of [null,'denied','unexpected']){
  const b=browser('https://openedu4u.com/',consent);
  assert.equal(b.scripts.length,0);assert.equal(b.window.dataLayer,undefined);
 }
});
test('public locations are sanitized and ads disabled',()=>{
 const b=browser('https://openedu4u.com/#/academy/123?email_hint=hidden','granted');
 assert.equal(b.scripts.length,1);assert.equal(b.scripts[0].referrerPolicy,'origin');
 const rows=b.window.dataLayer;const config=rows.find(r=>r[0]==='config')[2];
 assert.equal('debug_mode' in config,false);
 assert.equal(config.send_page_view,false);assert.equal(config.allow_google_signals,false);assert.equal(config.allow_ad_personalization_signals,false);
 const event=rows.find(r=>r[0]==='event')[2];
 assert.equal('debug_mode' in event,false);
 assert.equal(event.page_location,'https://openedu4u.com/a/123.html');
 assert.equal(event.page_referrer,'https://www.google.com');assert.equal(JSON.stringify(rows).includes('hidden'),false);
});
test('account routes and login credentials never load Google',()=>{
 for(const url of ['https://openedu4u.com/#/admin/growth','https://openedu4u.com/#access_token=secret','https://openedu4u.com/?code=secret','https://openedu4u.com/openedu/private']){
  const b=browser(url,'granted');assert.equal(b.scripts.length,0);assert.equal(b.window.dataLayer,undefined);
 }
});
test('route changes deduplicate filters and disable private tracking',()=>{
 const b=browser('https://openedu4u.com/#/rank?region=mokdong','granted');
 b.route('https://openedu4u.com/#/rank?region=banpo');
 assert.equal(b.window.dataLayer.filter(r=>r[0]==='event').length,1);
 b.route('https://openedu4u.com/#/admin');assert.equal(b.window['ga-disable-G-TEST123'],true);
 b.route('https://openedu4u.com/#/compare?ids=123,456');
 assert.equal(b.window['ga-disable-G-TEST123'],false);
 const rows=JSON.stringify(b.window.dataLayer);assert.equal(rows.includes('ids='),false);assert.equal(rows.includes('admin'),false);
});
test('QA events carry debug marker and never echo the QA query',()=>{
 const b=browser('https://openedu4u.com/?analytics_debug=1','granted');
 const e=b.window.dataLayer.find(r=>r[0]==='event')[2];
 assert.equal(e.debug_mode,true);assert.equal(e.page_location,'https://openedu4u.com/');
});

test('user consent gates first request and revocation disables collection',()=>{
 const b=browser();assert.equal(b.scripts.length,0);
 b.choose('granted');assert.equal(b.scripts.length,1);
 assert.equal(b.storage.get('openedu.analytics.v1'),'granted');
 b.choose('denied');assert.equal(b.window['ga-disable-G-TEST123'],true);
 const count=b.window.dataLayer.filter(r=>r[0]==='event').length;
 b.route('https://openedu4u.com/#/academy/123');
 assert.equal(b.window.dataLayer.filter(r=>r[0]==='event').length,count);
 b.choose('granted');assert.equal(b.window['ga-disable-G-TEST123'],false);
 assert.equal(b.scripts.length,1);
});
test('development hosts never create analytics UI or third-party requests',()=>{
 const b=browser('http://127.0.0.1:8796/','granted');
 assert.equal(b.scripts.length,0);assert.equal(b.elements.length,0);
});

test('the Google command queue uses the documented arguments-object contract',()=>{
 const b=browser('https://openedu4u.com/','granted');
 for(const command of b.window.dataLayer) assert.equal(Object.prototype.toString.call(command),'[object Arguments]');
 assert.ok(b.window.dataLayer.some(r=>r[0]==='config'));
 assert.ok(b.window.dataLayer.some(r=>r[0]==='event' && r[1]==='page_view'));
});
