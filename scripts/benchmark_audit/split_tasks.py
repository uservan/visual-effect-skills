"""E1: split benchmark tasks into explicit vs vague with two independent open models.

Each model answers three concrete questions per clause (named tool + menu path, parameter
specificity, clause role). The task class is derived by rule, never asked of the model:
explicit = every edit clause names a real command AND gives exact values (or needs none).
Agreement between models is reported; disagreements go to human adjudication.
"""
from pathlib import Path
import argparse,asyncio,csv,json
import httpx

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'motivation/benchmark_audit'
APP={'PSBench':'Adobe Photoshop','OSWorld':'GIMP 2.10','OSExpert':'GIMP 2.10','CUA-World':'OpenToonz 1.7'}
MODELS={'qwen35':('http://localhost:8001/v1','Qwen3.5-397B-A17B-FP8'),'glm53':('http://localhost:8002/v1','GLM-5.3-Flash'),
        'dsv41':('http://localhost:8003/v1','DeepSeek-V4.1-Flash')}
PARAMS=['exact_values','direction_or_degree_only','none_given','not_needed']
SCHEMA={'type':'object','additionalProperties':False,'required':['clauses','note'],'properties':{'note':{'type':'string'},
 'clauses':{'type':'array','items':{'type':'object','additionalProperties':False,
   'required':['text','role','named_command','menu_path','params'],
   'properties':{'text':{'type':'string'},'role':{'enum':['edit','ui','scope','preserve','deliver']},
                 'named_command':{'type':'string'},'menu_path':{'type':'string'},'params':{'enum':PARAMS}}}}}}
SYSTEM="""You audit instructions from GUI benchmarks for professional software. Split the instruction into clauses and answer, for each clause, only what is literally written. Do not infer what the author probably meant.

role:
- edit: requests a change to the visible content (pixels, drawn or animated content) or to properties that change how it renders (size, resolution, frame rate, color mode).
- ui: operates the application without changing visible content: open a dialog or window, change preferences or theme, show/hide panels, add or rename an empty layer, set undo steps.
- scope: only says where the next edit applies ("select the central part", "in the upper-left corner" when standing alone).
- preserve: asks to keep something unchanged.
- deliver: save / export / render / name a file.

named_command: the command, tool, filter, adjustment, preset or menu item of {app} that the clause names. It counts as named when:
  (a) the clause contains its name, in any case ("apply a Gaussian Blur", "use Perspective Warp", "shift the color balance");
  (b) the verb itself is the command ("flip horizontally" -> Flip Horizontal, "resize to 800x800" -> Image Size, "rotate 15 degrees" -> Rotate);
  (c) the clause names a property that {app} exposes directly as a control of one standard command ("increase brightness" -> Brightness/Contrast, "Saturation +10%" -> Hue/Saturation, "contrast stronger" -> Brightness/Contrast, "Exposure +1.0" -> Exposure, "opacity 50%" -> Layer Opacity, "Midtones green -20" / "shadows add blue" -> Color Balance);
  (d) it names a preset of a command ("sepia" -> the command that offers a Sepia preset, if {app} has one).
Use "" when the clause only describes an appearance or a goal and the reader must decide which command(s) to use ("make it warmer", "vintage look", "remove the blemishes", "make the flowers glow", "make the background transparent").
menu_path: where that command lives in {app} (e.g. "Image > Adjustments > Color Balance"); "" if no command is named or it does not exist in {app}. If the named thing does not exist in {app}, set named_command to "".

params:
- exact_values: every value the command needs is given as a number or exact setting ("+1.0", "-20", "15 degrees", "800x800", "4 levels", "50%").
- direction_or_degree_only: only a direction or a vague amount ("toward cyan-blue", "slightly", "strong", "visibly taller").
- none_given: no direction and no amount, and the command has settings that matter.
- not_needed: the command has no settings that matter (flip, invert, desaturate default, delete, plain Sharpen).

Return only JSON."""

def derive(clauses):
    edits=[c for c in clauses if c['role']=='edit']
    # UI-only tasks (open a window, change a preference) are instruction-following by nature.
    if not edits:return ('ui_operation' if any(c['role']=='ui' for c in clauses) else 'no_edit'),0,0
    no_tool=sum(1 for c in edits if not c['named_command'].strip())
    no_val=sum(1 for c in edits if c['named_command'].strip() and c['params'] not in('exact_values','not_needed'))
    if no_tool:return 'vague_missing_tool',no_tool,no_val
    if no_val:return 'vague_missing_values',no_tool,no_val
    return 'explicit',0,0

async def ask(client,sem,key,row,seed):
    base,model=MODELS[key]
    msgs=[{'role':'system','content':SYSTEM.format(app=APP[row['benchmark']])},
          {'role':'user','content':json.dumps({'app':APP[row['benchmark']],'instruction':row['instruction']},ensure_ascii=False)}]
    body={'model':model,'messages':msgs,'temperature':0.6,'top_p':0.95,'max_tokens':12000,
          'response_format':{'type':'json_schema','json_schema':{'name':'clauses','schema':SCHEMA}}}
    async with sem:
        for attempt in range(3):
            body['seed']=seed+attempt  # same seed would repeat the same failure
            try:
                r=await client.post(f'{base}/chat/completions',json=body,timeout=900);r.raise_for_status()
                return key,row,json.loads(r.json()['choices'][0]['message']['content'])
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass
    return key,row,None

async def run(args):
    rows=list(csv.DictReader(open(AUDIT/'task_inventory.csv',encoding='utf-8')))
    if args.ids:
        want=[tuple(x.split(':',1)) for x in args.ids.split(',')];rows=[r for r in rows if (r['benchmark'],r['task_id']) in want]
    raw_path=AUDIT/f'split_{args.tag}_raw.jsonl';done={}
    if raw_path.exists():
        for line in raw_path.open():
            j=json.loads(line)
            if j['labels']:done[(j['model'],j['benchmark'],j['task_id'])]=j['labels']
    jobs=[(k,r) for r in rows for k in args.models if (k,r['benchmark'],r['task_id']) not in done]
    # One limit per model: a slow reasoning model must not hold the slots of a fast one.
    sems={k:asyncio.Semaphore(args.concurrency) for k in args.models}
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=None)) as client:
        with raw_path.open('a') as h:
            for fut in asyncio.as_completed([ask(client,sems[k],k,r,args.seed) for k,r in jobs]):
                k,r,lab=await fut
                h.write(json.dumps({'model':k,'benchmark':r['benchmark'],'task_id':r['task_id'],'labels':lab},ensure_ascii=False)+'\n');h.flush()
                if lab:done[(k,r['benchmark'],r['task_id'])]=lab
                print(k,r['benchmark'],r['task_id'],derive(lab['clauses'])[0] if lab else 'FAILED',flush=True)
    out=[]
    for r in rows:
        rec={'benchmark':r['benchmark'],'task_id':r['task_id'],'instruction':r['instruction']}
        classes=[]
        for k in args.models:
            lab=done.get((k,r['benchmark'],r['task_id']))
            cls=derive(lab['clauses'])[0] if lab else 'missing';classes.append(cls);rec[f'class_{k}']=cls
        # Majority vote: unanimous -> 'all'; a strict majority -> 'majority' (spot-checked); otherwise a human decides.
        votes=[c for c in classes if c!='missing'];top=max(set(votes),key=votes.count) if votes else 'missing'
        n=votes.count(top)
        rec['agree']='all' if n==len(classes) else 'majority' if n*2>len(classes) else 'none'
        rec['class']=top if rec['agree']!='none' else 'needs_adjudication'
        out.append(rec)
    with (AUDIT/f'split_{args.tag}.csv').open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,list(out[0]));w.writeheader();w.writerows(out)
    c={k:sum(r['agree']==k for r in out) for k in ('all','majority','none')}
    print(json.dumps({'tasks':len(out),'models':args.models,**c}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='pilot');ap.add_argument('--ids',default='',help='benchmark:task_id,...')
    ap.add_argument('--models',nargs='+',default=list(MODELS));ap.add_argument('--seed',type=int,default=0);ap.add_argument('--concurrency',type=int,default=48)
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
