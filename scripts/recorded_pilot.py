"""Small open-weight GUI pilot with full step evidence; no arbitrary actor code.

Run on the allocated CPU desktop host, with a model server reachable by HTTP.
GIMP T1 is the first smoke pair; T4 is retained for verifier diagnostics.
A fresh QEMU disk overlay is booted separately for each condition by the caller.
"""
from __future__ import annotations
import argparse, base64, hashlib, importlib.util, io, json, os, re, shutil, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCES = Path('/scratch/pioneer/jobs/wxy320/visual_effect_sources')

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def append_json(path, data):
    with Path(path).open('a') as f: f.write(json.dumps(data, ensure_ascii=False) + '\n')

def image_block(raw):
    return {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(raw).decode()}}

class Desktop:
    def __init__(self, url):
        self.http = httpx.Client(base_url=url, timeout=120, trust_env=False)
    def execute(self, code):
        r=self.http.post('/execute',json={'command':['python3','-c',code],'shell':False})
        r.raise_for_status(); d=r.json()
        if d.get('returncode',0) or d.get('status')=='error': raise RuntimeError(str(d))
        return d
    def screenshot(self):
        r=self.http.get('/screenshot');r.raise_for_status()
        Image.open(io.BytesIO(r.content)).verify()
        return r.content
    def action(self, a):
        action=a['action']
        if action=='done': return {'done':True}
        prefix='import pyautogui as p,time; p.FAILSAFE=False; '
        if action in ['click','double_click','right_click','move','drag']:
            x,y=int(a['x']),int(a['y'])
            if not (0<=x<1280 and 0<=y<720): raise ValueError('Coordinates outside 1280x720')
            if action=='click': code=f'p.click({x},{y})'
            elif action=='double_click': code=f'p.doubleClick({x},{y},interval=0.15)'
            elif action=='right_click': code=f'p.click({x},{y},button="right")'
            elif action=='move': code=f'p.moveTo({x},{y},duration=0.2)'
            else: code=f'p.moveTo({int(a["from_x"])},{int(a["from_y"])});p.dragTo({x},{y},duration=0.8)'
        elif action=='type':
            text=a.get('text','')
            if len(text)>4000 or not text.isascii(): raise ValueError('Pilot typing supports <=4000 ASCII characters')
            code=f'p.write({text!r},interval=0.02)'
        elif action=='key':
            keys=[k.lower() if isinstance(k,str) else k for k in a.get('keys',[])]
            if not 1<=len(keys)<=4 or any(not isinstance(k,str) or len(k)>20 for k in keys): raise ValueError('Invalid keys')
            code=f'p.hotkey(*{keys!r})' if len(keys)>1 else f'p.press({keys[0]!r})'
        elif action=='scroll':code=f'p.scroll({max(-15,min(15,int(a.get("amount",0))))})'
        elif action=='wait':code=f'time.sleep({min(5,max(0,float(a.get("seconds",1))))})'
        else:raise ValueError('Unsupported action '+action)
        return self.execute(prefix+code+';time.sleep(0.5)')

TOOLS=[{'type':'function','function':{'name':'desktop','description':'Operate the isolated desktop. Coordinates are pixels in the 1280x720 screenshot. Use done when finished.','parameters':{'type':'object','properties':{'action':{'type':'string','enum':['click','double_click','right_click','move','drag','type','key','scroll','wait','done']},'x':{'type':'integer'},'y':{'type':'integer'},'from_x':{'type':'integer'},'from_y':{'type':'integer'},'text':{'type':'string'},'keys':{'type':'array','items':{'type':'string'},'description':'Lowercase key names, e.g. [ctrl,q] or [enter].'},'amount':{'type':'integer'},'seconds':{'type':'number'}},'required':['action']}}}]
LOAD_TOOL={'type':'function','function':{'name':'load_topic','description':'Load an original application skill guide and its reference figures. Pass the guide directory or guide.md path from the index.','parameters':{'type':'object','properties':{'topic':{'type':'string'}},'required':['topic']}}}

class Skill:
    def __init__(self,path):self.root=Path(path).resolve()
    def load(self, topic):
        p=(self.root/topic).resolve()
        if p.is_dir():p=p/'guide.md'
        if not p.is_relative_to(self.root) or not p.is_file() or p.suffix!='.md': raise ValueError('Unknown topic')
        text=p.read_text(); blocks=[{'type':'text','text':text}];files=[p]
        # Match both fig01.png code references and Markdown image references.
        for name in dict.fromkeys(re.findall(r'[\w./-]+\.(?:png|jpg|jpeg)',text)):
            img=(p.parent/name).resolve()
            if img.is_relative_to(self.root) and img.is_file():
                blocks.append(image_block(img.read_bytes()));files.append(img)
        return blocks, [{'path':str(f.relative_to(self.root)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]

def setup(desktop, task, out):
    records=[]
    desktop.execute("import subprocess; x=subprocess.check_output(['xrandr'],text=True); output=next(l.split()[0] for l in x.splitlines() if ' connected' in l); subprocess.run(['xrandr','--newmode','1280x720_60.00','74.50','1280','1344','1472','1664','720','723','728','748','-hsync','+vsync'],capture_output=True); subprocess.run(['xrandr','--addmode',output,'1280x720_60.00'],capture_output=True); subprocess.run(['xrandr','--output',output,'--mode','1280x720_60.00'],check=True)")
    desktop.execute("import pyautogui;pyautogui.FAILSAFE=False;pyautogui.moveTo(640,360)")
    time.sleep(2)
    if Image.open(io.BytesIO(desktop.screenshot())).size!=(1280,720):raise RuntimeError('Desktop resolution must be 1280x720')
    # Fixture-only commands below run in the disposable guest, never on host.
    desktop.execute("import subprocess; subprocess.run(['pkill','-x','gimp'],check=False);subprocess.run(['pkill','-x','gimp-2.10'],check=False)")
    for step in task['config']:
        kind, params=step['type'],step['parameters']
        if kind=='download':
            for item in params['files']:
                desktop.execute('import urllib.request,pathlib; p=pathlib.Path('+repr(item['path'])+');p.parent.mkdir(parents=True,exist_ok=True);urllib.request.urlretrieve('+repr(item['url'])+',p)')
        elif kind=='launch':
            r=desktop.http.post('/setup/launch',json=params);r.raise_for_status()
        else:raise ValueError('Unsupported fixture step '+kind)
        records.append(step)
    for attempt in range(60):
        windows=desktop.execute("import subprocess;print(subprocess.check_output(['wmctrl','-l'],text=True))").get('output','')
        if 'GIMP' in windows or 'GNU Image Manipulation Program' in windows:break
        time.sleep(2)
    else:raise RuntimeError('GIMP window did not become ready')
    time.sleep(2)
    (out/'screenshots'/'initial.png').write_bytes(desktop.screenshot())
    write_json(out/'setup.json',records)

def evaluate_t4(desktop, task, out):
    # Load the unchanged upstream metric functions without importing unrelated
    # cloud providers or evaluator modules.
    metric_path=SOURCES/'visualskill_pinned_gimp.py'
    spec=importlib.util.spec_from_file_location('upstream_gimp_metrics',metric_path)
    metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)
    scores=[]
    for i,name in enumerate(task['evaluator']['func']):
        result=task['evaluator']['result'][i]; expected=task['evaluator']['expected'][i]
        pred=out/result['dest'];gold=out/('reference_'+expected['dest'])
        r=desktop.http.post('/file',data={'file_path':result['path']})
        if r.status_code!=200:scores.append({'metric':name,'score':0,'reason':'Output file unavailable'});continue
        pred.write_bytes(r.content)
        with httpx.Client(follow_redirects=True,timeout=120) as c:
            r=c.get(expected['path']);r.raise_for_status();gold.write_bytes(r.content)
        score=float(getattr(metric,name)(str(pred),str(gold)))
        scores.append({'metric':name,'score':score})
    return {'success':all(x['score']==1 for x in scores),'metrics':scores,'metric_source':str(metric_path),'metric_sha256':hashlib.sha256(metric_path.read_bytes()).hexdigest()}


def evaluate_t1(desktop, task, out):
    metric_path=SOURCES/'visualskill_pinned_gimp.py'
    spec=importlib.util.spec_from_file_location('upstream_gimp_metrics',metric_path)
    metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)
    post=[]
    for entry in task['evaluator'].get('postconfig',[]):
        if entry['type']=='execute':
            r=desktop.http.post('/execute',json=entry['parameters']);r.raise_for_status();feedback=r.json()
            if feedback.get('returncode',0):raise RuntimeError('Verifier postconfig execution failed: '+str(feedback))
            post.append(feedback)
        elif entry['type']=='sleep':time.sleep(entry['parameters']['seconds'])
        else:raise ValueError('Unsupported evaluator postconfig '+entry['type'])
    write_json(out/'verifier_postconfig.json',post)
    scores=[]
    for i,name in enumerate(task['evaluator']['func']):
        rule=task['evaluator']['expected'][i]['rules'];item=task['evaluator']['result'][i]
        guest_path='/home/user/.config/GIMP/2.10/'+item['file_name']
        r=desktop.http.post('/file',data={'file_path':guest_path})
        if r.status_code!=200:scores.append({'metric':name,'rule':rule,'score':0,'reason':'Config file unavailable'});continue
        path=out/item['dest'];path.write_bytes(r.content)
        scores.append({'metric':name,'rule':rule,'score':float(getattr(metric,name)(str(path),rule))})
    return {'success':all(x['score']==1 for x in scores),'metrics':scores,'metric_source':str(metric_path),'metric_sha256':hashlib.sha256(metric_path.read_bytes()).hexdigest()}


def run(args):
    if args.task not in ['gimp_T1','gimp_T4']:raise ValueError('Unsupported first-pilot task')
    task_path=SOURCES/('OSExpert/OSWorld/evaluation_examples_expert/OSExpert_Eval/long_horizon_json/gimp/'+args.task+'.json')
    task=json.loads(task_path.read_text());run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=Path(args.output)/'Holo4-27B'/args.condition/args.task/run_id
    out.mkdir(parents=True);(out/'screenshots').mkdir();(out/'effects').mkdir()
    write_json(out/'task.json',task)
    config=vars(args).copy();config.update(run_id=run_id,screen_resolution=[1280,720],model_revision=json.loads((ROOT/'motivation/runtime/model_manifest.json').read_text())['revision'],temperature=0,seed=42,context_policy='Keep latest 3 model-visible screenshot/reference messages; keep all text and raw evidence',harness='direct-QEMU pilot adapter; not original Claude runner')
    server_manifest=Path('/scratch/pioneer/jobs/wxy320/visual_effect_runtime/active_model_server.json')
    if server_manifest.exists():config['inference_runtime']=json.loads(server_manifest.read_text())
    config['original_task_sha256']=hashlib.sha256(task_path.read_bytes()).hexdigest()
    config['harness_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write_json(out/'config.json',config)
    desktop=Desktop(args.desktop_url);skill=Skill(args.skill_root)
    instructions='You control GIMP using only desktop actions. Complete the user task using the GUI. Do not use terminal commands, scripts, or file editing. Work in the 1280x720 desktop screenshot coordinate system. Call desktop with action done only after the requested output is saved.'
    tools=TOOLS.copy()
    if args.condition=='B':
        index=(skill.root/'SKILL.md').read_text();instructions+='\nOriginal application skill index:\n'+index+'\nUse load_topic to consult relevant guides before acting.';tools.append(LOAD_TOOL)
        (out/'skill_index.md').write_text(index)
    messages=[{'role':'system','content':instructions},{'role':'user','content':task['instruction']}]
    started=time.monotonic();result={'task_id':args.task,'model_id':'Hcompany/Holo4-27B','condition':args.condition,'status':'invalid','success':None,'actions':0,'tokens':0,'failure_tags':[],'first_error_step':None,'evidence_paths':['trace.jsonl','screenshots/'],'verifier':'original '+args.task+' metrics','seed':42}
    try:
        setup(desktop,task,out)
        version=desktop.execute("import subprocess;print(subprocess.check_output(['gimp','--version'],text=True))")
        write_json(out/'software_version.json',version);result['software_version']=version.get('output','').strip()
        with httpx.Client(timeout=300,trust_env=False) as model:
            for step in range(args.max_steps):
                if time.monotonic()-started>args.max_seconds:result['termination']='wall_clock_limit';break
                before=desktop.screenshot();bname=f'screenshots/step_{step:03d}_before.png';(out/bname).write_bytes(before)
                messages.append({'role':'user','content':[{'type':'text','text':f'Current desktop, step {step}.'},image_block(before)]})
                # Trim only model-visible historical images, not recorded evidence.
                image_messages=[m for m in messages if isinstance(m.get('content'),list) and any(b.get('type')=='image_url' for b in m['content'])]
                for old in image_messages[:-3]:old['content']=[b for b in old['content'] if b.get('type')!='image_url']
                payload={'model':args.model,'messages':messages,'tools':tools,'temperature':0,'seed':42,'max_tokens':2048,'chat_template_kwargs':{'enable_thinking':False},'parallel_tool_calls':False}
                key_path=Path(args.api_key_file);headers={'Authorization':'Bearer '+key_path.read_text().strip()}
                response=model.post(args.model_url.rstrip('/')+'/chat/completions',json=payload,headers=headers);response.raise_for_status();data=response.json()
                msg=data['choices'][0]['message'];msg.pop('reasoning_content',None);msg.pop('reasoning',None)
                append_json(out/'model_responses.jsonl',{'step':step,'message':msg,'usage':data.get('usage',{})});result['tokens']+=data.get('usage',{}).get('total_tokens',0)
                messages.append({k:msg[k] for k in ['role','content','tool_calls'] if k in msg})
                calls=msg.get('tool_calls',[]);events=[];done=False
                if len(calls)>1:raise RuntimeError('Pilot requires one tool action per recorded step')
                for call in calls:
                    name=call['function']['name'];a=json.loads(call['function']['arguments'])
                    try:
                        if name=='desktop':
                            feedback=desktop.action(a);done=done or feedback.get('done',False);result['actions']+=1
                            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(feedback)})
                        elif name=='load_topic' and args.condition=='B':
                            blocks,files=skill.load(a['topic']);feedback={'loaded_files':files}
                            for info in files:
                                target=out/'loaded_skills'/info['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(skill.root/info['path'],target)
                            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(feedback)})
                            messages.append({'role':'user','content':blocks})
                            append_json(out/'skill_loads.jsonl',{'step':step,**feedback})
                        else:raise ValueError('Unknown tool '+name)
                    except Exception as e:
                        feedback={'error':str(e)};messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(feedback)})
                    events.append({'tool':name,'arguments':a,'result':feedback})
                after=desktop.screenshot();aname=f'screenshots/step_{step:03d}_after.png';(out/aname).write_bytes(after)
                append_json(out/'trace.jsonl',{'step':step,'timestamp':datetime.now(timezone.utc).isoformat(),'before':bname,'after':aname,'events':events,'message':msg.get('content'),'model_usage':data.get('usage',{})})
                if any(e['tool']=='desktop' and e['arguments']['action'] not in ['done','wait'] for e in events):
                    b=Image.open(io.BytesIO(before)).convert('RGB');aimg=Image.open(io.BytesIO(after)).convert('RGB')
                    if aimg.size==b.size:ImageChops.difference(b,aimg).save(out/'effects'/f'step_{step:03d}_screen_diff.png')
                print(json.dumps({'run':str(out),'step':step,'events':[e['tool'] for e in events]}),flush=True)
                if done:result['termination']='agent_done';break
                if not calls:messages.append({'role':'user','content':'Use the provided tools to act or call desktop done.'})
            else:result['termination']='step_limit'
        (out/'screenshots/final.png').write_bytes(desktop.screenshot())
        result.update((evaluate_t1 if args.task=='gimp_T1' else evaluate_t4)(desktop,task,out));result['status']='completed'
    except Exception as e:
        result['error']=repr(e);result['failure_tags']=['infrastructure_or_harness_error']
        print(repr(e),flush=True)
    finally:
        try:
            if not (out/'screenshots/final.png').exists():(out/'screenshots/final.png').write_bytes(desktop.screenshot())
        except Exception:pass
        result['runtime']=time.monotonic()-started;write_json(out/'result.json',result)
        write_json(out/'final_state.json',{'saved_output':'export.jpg' if (out/'export.jpg').exists() else None,'termination':result.get('termination'),'status':result['status']})
        print(json.dumps({'result':str(out/'result.json'),**result}),flush=True)
    return 0 if result['status']=='completed' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--desktop-url',default='http://127.0.0.1:15000');p.add_argument('--model-url',required=True);p.add_argument('--model',default='Holo4-27B');p.add_argument('--api-key-file',default='/scratch/pioneer/jobs/wxy320/visual_effect_runtime/model_api_key');p.add_argument('--task',default='gimp_T1');p.add_argument('--condition',choices=['A','B'],required=True);p.add_argument('--max-steps',type=int,default=50);p.add_argument('--max-seconds',type=int,default=900);p.add_argument('--output',default='/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/runs');p.add_argument('--skill-root',default=str(SOURCES/'VisualSkills/skills/gimp-multimodal-stage2'));raise SystemExit(run(p.parse_args()))
