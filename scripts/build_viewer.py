"""Generate an offline trajectory viewer using relative screenshot paths."""
import argparse,json,os
from pathlib import Path
from html import escape

def build(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);runs=[]
    for result_path in sorted((root/'runs').rglob('result.json')):
        run=result_path.parent;r=json.loads(result_path.read_text())
        steps=[]
        if (run/'trace.jsonl').exists():
            for line in (run/'trace.jsonl').read_text().splitlines():
                s=json.loads(line)
                for key in ['before','after']:
                    s[key]=os.path.relpath(run/s[key],root)
                steps.append(s)
        runs.append({'id':os.path.relpath(run,root),'result':r,'steps':steps})
    data=json.dumps(runs,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><meta charset="utf-8"><title>GUI trajectory inspection</title>
<style>body{font:15px system-ui;margin:24px;background:#f6f7f9;color:#18212c}select,button,input{margin:5px}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}.panel{background:white;padding:16px;min-width:0}img{width:100%;border:1px solid #ccd2da}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ccd2da}a{color:#1459b5}</style>
<h1>Recorded GUI experiments</h1><p>Original screenshots and actions. Invalid infrastructure runs are separate from completed failures. A = no skill; B = original skill.</p>
<div id="summary"></div><main><div class="panel" id="left"></div><div class="panel" id="right"></div></main>
<script>const runs=DATA;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.querySelector('#summary').innerHTML='<table><tr><th>Task</th><th>Condition</th><th>Status</th><th>Success</th><th>Actions</th></tr>'+runs.map(x=>'<tr>'+[x.result.task_id,x.result.condition,x.result.status,x.result.success,x.result.actions].map(y=>'<td>'+esc(y)+'</td>').join('')+'</tr>').join('')+'</table>'+(runs.length?'':'<p>No completed or invalid recorded episodes yet.</p>');
for(const side of ['left','right']){
 const p=document.getElementById(side);p.innerHTML='<select class="run"></select><br><button class="prev">Previous</button><button class="next">Next</button><input type="range" min="0" value="0" class="step"><button class="failure">First annotated error</button><div class="view"></div><button class="export">Export report</button>';
 const sel=p.querySelector('.run'),slider=p.querySelector('.step');sel.innerHTML=runs.map((r,i)=>'<option value="'+i+'">'+esc(r.result.task_id+' / '+r.result.condition+' / '+r.id)+'</option>').join('');
 if(side==='right'&&runs.length>1)sel.value='1';
 function draw(){const run=runs[Number(sel.value)];if(!run)return;slider.max=Math.max(0,run.steps.length-1);const s=run.steps[Number(slider.value)];p.querySelector('.view').innerHTML='<pre>'+esc(JSON.stringify(run.result,null,2))+'</pre>'+(s?'<h3>Step '+s.step+'</h3><a target="_blank" href="'+esc(s.before)+'">Before: full resolution</a><img src="'+esc(s.before)+'"><pre>'+esc(JSON.stringify(s.events,null,2))+'</pre><a target="_blank" href="'+esc(s.after)+'">After: full resolution</a><img src="'+esc(s.after)+'">':'<p>No step screenshots recorded.</p>');}
 sel.onchange=()=>{slider.value=0;draw()};slider.oninput=draw;
 p.querySelector('.prev').onclick=()=>{slider.value=Math.max(0,Number(slider.value)-1);draw()};p.querySelector('.next').onclick=()=>{slider.value=Math.min(Number(slider.max),Number(slider.value)+1);draw()};
 p.querySelector('.failure').onclick=()=>{const r=runs[Number(sel.value)];if(r?.result.first_error_step!=null){slider.value=r.result.first_error_step;draw()}};
 p.querySelector('.export').onclick=()=>{const r=runs[Number(sel.value)];if(!r)return;const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=r.result.task_id+'_'+r.result.condition+'_report.json';a.click();URL.revokeObjectURL(url)};draw();}
</script>'''.replace('DATA',data)
    (root/'index.html').write_text(page);print(root/'index.html')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact_root',nargs='?',default='/scratch/pioneer/jobs/wxy320/save/visual-effect-skills');build(p.parse_args().artifact_root)
