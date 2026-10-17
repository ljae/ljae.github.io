"""Self-contained private analysis view, usable before connecting Supabase."""
import json
from pathlib import Path


def render(reports: list[dict]) -> str:
    payload = json.dumps(reports, ensure_ascii=False).replace('<', '\\u003c')
    css = (Path(__file__).resolve().parents[1] / 'seo_templates/site.css').read_text()
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>검색 성장 · 비공개 분석 보고서</title><style>''' + css + '''
select{font:inherit;padding:12px;border-radius:8px;max-width:100%}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.metric{font-size:30px;font-weight:750}summary{cursor:pointer}.badge{background:var(--soft);padding:3px 8px}td{overflow-wrap:anywhere}
</style></head><body><header><span class="brand">학원실록 · 검색 성장</span></header>
<main><h1>실제 자료로 확인하는 검색 유입</h1><p class="sub">개인 작업용 분석 보고서 · 외부 전송 없음</p>
<label>관측 기간 <select id="period"></select></label><p id="meta" class="note"></p><div id="metrics" class="grid"></div>
<section class="panel"><h2>자료 범위</h2><p id="quality"></p><p id="warnings" class="note"></p></section>
<section class="panel"><h2>노출 추이</h2><svg id="chart" role="img" aria-label="일별 검색 노출" viewBox="0 0 800 200" style="width:100%;height:auto"></svg><details><summary>일별 수치 확인</summary><div id="daily"></div></details></section>
<section class="panel"><h2>개선 과제와 진단 근거</h2><div id="findings"></div></section>
<section class="panel"><h2>관측 검색어 · 상위 20개</h2><p class="note">검색어 표는 총계의 일부이며 시장 전체 검색량이 아닙니다.</p><div id="queries"></div></section>
<section class="panel"><h2>관측 페이지 · 상위 20개</h2><div id="pages"></div></section>
</main><script type="application/json" id="data">''' + payload + '''</script><script>
'use strict';const reports=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>v==null?'—':(v*100).toFixed(2)+'%';
function table(rows){return '<table><thead><tr><th>항목</th><th>클릭</th><th>노출</th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+esc(r.key??r.date)+'</td><td>'+r.clicks+'</td><td>'+r.impressions+'</td></tr>').join('')+'</tbody></table>';}
reports.forEach((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=r.period.start+' ~ '+r.period.end+' · '+r.source;$('period').append(o);});
function render(){const r=reports[Number($('period').value)],q=r.quality,t=r.totals;
$('meta').textContent=r.property+' · PT 일자 · 자료 추출 '+r.asOf;
$('metrics').innerHTML=[['검색 클릭',t.clicks],['검색 노출',t.impressions],['클릭률',pct(t.ctr)],['관측 페이지',(q.pageRowsTruncated?'≥':'')+r.pages.length]].map(v=>'<div class="panel"><span>'+v[0]+'</span><div class="metric">'+v[1]+'</div></div>').join('');
$('quality').textContent='검색어 클릭 가시성 '+pct(q.queryClickCoverage)+(q.pageRowsTruncated?' · 페이지 내보내기 상한 도달':'');
$('warnings').textContent=q.warnings.join(' / ');
$('daily').innerHTML=table(r.daily);$('queries').innerHTML=table(r.queries.slice(0,20));$('pages').innerHTML=table(r.pages.slice(0,20));
$('findings').innerHTML=r.findings.length?r.findings.map(f=>'<details><summary>'+esc(f.severity+' · '+f.title)+'</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(JSON.stringify(f,null,2))+'</pre></details>').join(''):'<p>이 기간에서 확인된 규칙 이상 없음. 소표본의 성과 개선 여부는 판정하지 않습니다.</p>';
const max=Math.max(1,...r.daily.map(d=>d.impressions)),start=new Date(r.daily[0].date),span=Math.max(1,(new Date(r.daily.at(-1).date)-start)/86400000);let previous=null,path='';
for(const d of r.daily){const day=new Date(d.date),x=10+(day-start)/86400000/span*780,y=185-d.impressions/max*170;path+=(previous&&day-previous===86400000?'L':'M')+x+','+y;previous=day;}
$('chart').innerHTML='<title>일별 노출, 최대 '+max+'회</title><path d="'+path+'" fill="none" stroke="#328467" stroke-width="3"/>';
} $('period').addEventListener('change',render);render();
</script></body></html>'''
