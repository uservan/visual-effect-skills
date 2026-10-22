"""E4: draft manual-grounded multiple-choice questions (Q1 location, Q2 function, Q3 effect, Q4 goal->tool).

Generators alternate between two open models by unit so each model's advantage on its own questions can be
reported separately. A question is kept only if its evidence quote appears verbatim in the unit text and the
four options are distinct. Kept questions still need human verification before they count.
Output: $DATA/e4/questions_<app>.jsonl
"""
from pathlib import Path
import argparse,asyncio,json,random,re
import httpx

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
GEN={'qwen35':('http://localhost:8001/v1','Qwen3.5-397B-A17B-FP8'),'glm53':('http://localhost:8002/v1','GLM-5.3-Flash')}
APPNAME={'gimp':'GIMP 2.10','darktable':'darktable','krita':'Krita','opentoonz':'OpenToonz','photoshop':'Adobe Photoshop'}
TYPES={'Q1':'Location: where in the UI the tool/command/control is (menu path, dialog, panel).',
       'Q2':'Function: what the tool/command does or what it is for.',
       'Q3':'Effect: how changing a specific parameter/setting changes the visible result (direction or kind of change).',
       'Q4':'Goal to tool: given a desired visual result, which tool/setting achieves it and why.'}
SCHEMA={'type':'object','additionalProperties':False,'required':['questions'],'properties':{'questions':{'type':'array','items':{
  'type':'object','additionalProperties':False,'required':['type','question','options','answer','evidence_quote'],
  'properties':{'type':{'enum':list(TYPES)},'question':{'type':'string'},
                'options':{'type':'array','items':{'type':'string'},'minItems':4,'maxItems':4},
                'answer':{'enum':['A','B','C','D']},'evidence_quote':{'type':'string'}}}}}}

def norm(s):return re.sub(r'\s+',' ',s).strip().lower()

def prompt(unit):
    app=APPNAME[unit['app']]
    rules='\n'.join(f'- {k}: {v}' for k,v in TYPES.items())
    return [{'role':'system','content':f"""You write exam questions about {app} from one page of its official manual.
Write one question of each type the page supports (at most one per type, skip a type the page cannot ground):
{rules}
Rules: the correct answer must follow from the page alone; quote the supporting sentence(s) verbatim from the page in evidence_quote (copy exactly, 5-60 words); write three plausible wrong options a non-expert might pick; do not mention "the manual" or "the page" in the question; the question must make sense without the page. Return only JSON."""},
            {'role':'user','content':f"Page title: {unit['title']}\n\n{unit['text']}"}]

async def gen(client,sem,args,key,unit):
    base,model=GEN[key]
    body={'model':model,'messages':prompt(unit),'temperature':0.6,'top_p':0.95,'max_tokens':12000,
          'response_format':{'type':'json_schema','json_schema':{'name':'qs','schema':SCHEMA}}}
    async with sem:
        for attempt in range(3):
            body['seed']=args.seed+attempt
            try:
                r=await client.post(f'{base}/chat/completions',json=body,timeout=900);r.raise_for_status()
                return key,unit,json.loads(r.json()['choices'][0]['message']['content'])['questions']
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass
    return key,unit,None

async def run(args):
    for app in args.apps:
        units=[json.loads(l) for l in open(DATA/'e4'/f'units_{app}.jsonl')]
        random.Random(args.seed).shuffle(units);units=units[:args.units]
        sems={k:asyncio.Semaphore(args.concurrency) for k in GEN}
        kept=rejected=0;out=(DATA/'e4'/f'questions_{app}.jsonl').open('w')
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=None)) as client:
            jobs=[gen(client,sems[list(GEN)[i%2]],args,list(GEN)[i%2],u) for i,u in enumerate(units)]
            for fut in asyncio.as_completed(jobs):
                key,unit,qs=await fut
                for q in qs or []:
                    ok=norm(q['evidence_quote']) in norm(unit['text']) and len(q['evidence_quote'].split())>=5 and len({norm(o) for o in q['options']})==4
                    if not ok:rejected+=1;continue
                    kept+=1
                    out.write(json.dumps({'app':app,'unit_id':unit['unit_id'],'url_path':unit['url_path'],'generator':key,**q,'verified':False},ensure_ascii=False)+'\n')
        out.close();print(json.dumps({'app':app,'units':len(units),'kept':kept,'rejected_unverifiable':rejected}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('apps',nargs='+');ap.add_argument('--units',type=int,default=30)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--concurrency',type=int,default=16)
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
