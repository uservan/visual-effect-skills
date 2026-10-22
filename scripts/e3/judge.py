"""E3: score candidates with PSBench's released judge prompt, served by open models.

The system prompt, user message, image encoding and pass rule come verbatim from
PSBench/photoshop_evaluators.py (PhotoshopEvaluator._build_messages / _normalize_report).
Only the transport changes: our vLLM endpoints instead of gpt-5.4, with each model's recommended
sampling (temperature 0 loops on whitespace under JSON constraints for Qwen3.5) and room for reasoning.
Results are labelled "PSBench rubric, substitute judge". Resumable; one row per task x candidate x judge x repeat.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,asyncio,csv,json,sys
import httpx

ROOT=Path(__file__).resolve().parents[2]
DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
sys.path.insert(0,str(DATA/'sources/PSBench'))
from photoshop_evaluators import PhotoshopEvaluator  # PSBench @ 5a9a911

JUDGES={'qwen35':('http://localhost:8001/v1','Qwen3.5-397B-A17B-FP8'),'glm53':('http://localhost:8002/v1','GLM-5.3-Flash'),
        'dsv41':('http://localhost:8003/v1','DeepSeek-V4.1-Flash'),'step37':('http://localhost:8004/v1','Step-3.7-Flash-FP8'),
        'nemo35':('http://localhost:8005/v1','NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16')}
SCHEMA={'type':'object','required':['summary','criteria'],'properties':{'summary':{'type':'string'},
  'criteria':{'type':'array','items':{'type':'object','required':['id','passed','reason'],
    'properties':{'id':{'type':'string'},'passed':{'type':'boolean'},'reason':{'type':'string'}}}}}}

def evaluator(task):
    return PhotoshopEvaluator(task_folder=str(DATA/'sources/PSBench-data'/task),result_folder=str(DATA/'e3/reports'),api_key='unused')

_messages={}
def build(row):
    """PSBench's _build_messages re-encodes both images as optimised PNG, which is slow; do it once per candidate."""
    key=(row['task_id'],row['candidate'])
    if key not in _messages:
        ev=evaluator(row['task_id']);rubric=ev.load_rubric()
        _messages[key]=(ev,rubric,ev._build_messages(rubric,ev.get_start_path(),Path(row['path'])))
    return _messages[key]

async def judge(client,sem,key,row,rep,seed):
    base,model=JUDGES[key];ev,rubric,msgs=_messages[(row['task_id'],row['candidate'])]
    body={'model':model,'messages':msgs,'temperature':0.6,'top_p':0.95,'max_tokens':12000,
          'response_format':{'type':'json_schema','json_schema':{'name':'report','schema':SCHEMA}}}
    rec={k:row[k] for k in ('task_id','group','e1_class','difficulty','candidate')}|{'judge':key,'rep':rep}
    async with sem:
        for attempt in range(3):
            body['seed']=seed+100*rep+attempt
            try:
                r=await client.post(f'{base}/chat/completions',json=body,timeout=900);r.raise_for_status()
                rep_=ev._normalize_report(json.loads(r.json()['choices'][0]['message']['content']),rubric)
                return rec|{'passed':rep_['passed'],'failed_requirements':rep_['failed_requirements'],'summary':rep_['summary'][:500]}
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass
    return rec|{'passed':None}

async def run(args):
    rows=list(csv.DictReader(open(ROOT/'motivation/e3/candidates_manifest.csv')))
    out=ROOT/'motivation/e3/judgments.jsonl';done=set()
    if out.exists():
        done={(j['task_id'],j['candidate'],j['judge'],j['rep']) for j in map(json.loads,open(out)) if j['passed'] is not None}
    jobs=[(k,r,rep) for k in args.judges for rep in range(args.repeats) for r in rows if (r['task_id'],r['candidate'],k,rep) not in done]
    with ThreadPoolExecutor(32) as pool:list(pool.map(build,{(r['task_id'],r['candidate']):r for _,r,_ in jobs}.values()))
    print(json.dumps({'encoded':len(_messages),'jobs':len(jobs)}),flush=True)
    sems={k:asyncio.Semaphore(args.concurrency) for k in args.judges}
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=None)) as client:
        with out.open('a') as h:
            for fut in asyncio.as_completed([judge(client,sems[k],k,r,rep,args.seed) for k,r,rep in jobs]):
                h.write(json.dumps(await fut)+'\n');h.flush()
    print(json.dumps({'judged':len(jobs)}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--judges',nargs='+',default=list(JUDGES));ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--concurrency',type=int,default=32)
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
