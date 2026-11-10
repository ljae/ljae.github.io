import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
function surface(html=fs.readFileSync(process.env.MAP_SOURCE || 'app/web/index.html','utf8')) {
 const start=html.indexOf('window.hakwonMap =');const end=html.indexOf('})();',start)+5;
 const timers=new Map(); let next=1;
 class Point {constructor(lat,lng){this.lat=lat;this.lng=lng}}
 class Bounds {constructor(a,b){this.points=[a,b]} extend(p){this.points.push(p)}}
 class MapStub {constructor(el,o){this.center=o.center;this.zoom=o.zoom;this.opts={};this.calls=[]}setOptions(o){Object.assign(this.opts,o)}setCenter(p){this.calls.push({center:p,bounds:this.opts.maxBounds});this.center=p}setZoom(z){this.zoom=z}getZoom(){return this.zoom}getBounds(){return {center:this.center}}fitBounds(b){this.fit=b}getProjection(){return null}}
 class Marker {constructor(o){this.o=o}setMap(){}setIcon(){}getPosition(){return this.o.position}}
 const naver={maps:{Map:MapStub,LatLng:Point,Point,LatLngBounds:Bounds,InfoWindow:class{},Marker,Polygon:class{},Position:{TOP_RIGHT:1},Event:{addListener:()=>1,removeListener(){},trigger(){}}}};
 const ctx={window:{naver},naver,document:{getElementById:()=>({}),addEventListener(){},removeEventListener(){}},setInterval:f=>{timers.set(next,f);return next++},clearInterval:id=>timers.delete(id),setTimeout:()=>1};vm.runInNewContext(html.slice(start,end),ctx);return {api:ctx.window.hakwonMap,timers};
}
test('switching to a region with no markers clears the old bounds before centering',()=>{
 const {api}=surface();const payload=JSON.stringify({markers:[{lat:37.49,lng:127.06},{lat:37.51,lng:127.07}]});api.init('a',37.5,127.06,15,payload);const map=api.get('a');map.setOptions({maxBounds:'daechi',minZoom:15});api.init('a',37.53,126.87,15,'{"markers":[]}');assert.equal(map.calls.at(-1).bounds,null);assert.equal(map.__fit,null);assert.equal(map.center.lng,126.87);
});
test('removing a regional map clears its periodic resize watcher and registry entry',()=>{const {api,timers}=surface();api.init('a',37.5,127,15,'{"markers":[]}');assert.equal(timers.size,1);api.destroy('a');assert.equal(timers.size,0);assert.equal(api.get('a'),undefined);api.destroy('a')});
