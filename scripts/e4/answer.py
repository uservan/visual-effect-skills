"""E4: answer manual-grounded questions closed-book and open-book (the source manual page in context).

Options are re-shuffled per question with a fixed seed so answer position carries no signal.
Output: $DATA/e4/answers_<model>.jsonl (one row per question x condition); resumable.
"""
from pathlib import Path
import argparse,asyncio,json,random
import httpx

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
APPNAME={'gimp':'GIMP 2.10','darktable':'darktable','krita':'Krita','opentoonz':'OpenToonz','photoshop':'Adobe Photoshop'}
SCHEMA={'type':'object','additionalProperties':False,'required':['answer'],'properties':{'answer':{'enum':['A','B','C','D']}}}

def item(q,seed):
    order=list(range(4));random.Random(f"{seed}-{q['unit_id']}-{q['question']}").shuffle(order)
    letters='ABCD';gold=letters[order.index('ABCD'.index(q['answer']))]
    return [q['options'][i] for i in order],gold

def messages(q,opts,page):
    app=APPNAME[q['app']]
    body=f"Question about {app}:\n{q['question']}\n\n"+'\n'.join(f'{l}. {o}' for l,o in zip('ABCD',opts))
    if page:body=f"Reference: an excerpt from the official {app} manual.\n\n{page}\n\n---\n\n"+body
    return [{'role':'user','content':body+'\n\nAnswer with the letter of the correct option. Return only JSON.'}]

async def ask(client,sem,args,q,cond,page):
    opts,gold=item(q,args.seed)
    body={'model':args.model,'messages':messages(q,opts,page if cond=='open' else ''),'temperature':0.6,'top_p':0.95,'max_tokens':8000,
          'response_format':{'type':'json_schema','json_schema':{'name':'a','schema':SCHEMA}}}
    async with sem:
        for attempt in range(3):
            body['seed']=args.seed+attempt
            try:
                r=await client.post(f'{args.base_url}/chat/completions',json=body,timeout=900);r.raise_for_status()
                pred=json.loads(r.json()['choices'][0]['message']['content'])['answer']
                return {'qid':f"{q['unit_id']}|{q['type']}",'app':q['app'],'type':q['type'],'generator':q['generator'],'condition':cond,'gold':gold,'pred':pred,'correct':pred==gold}
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass
    return {'qid':f"{q['unit_id']}|{q['type']}",'app':q['app'],'type':q['type'],'generator':q['generator'],'condition':cond,'gold':gold,'pred':None,'correct':None}

async def run(args):
    out=DATA/'e4'/f'answers_{args.tag}.jsonl';done=set()
    if out.exists():done={(j['qid'],j['condition']) for j in map(json.loads,open(out)) if j['pred']}
    qs=[];pages={}
    for app in args.apps:
        pages.update({u['unit_id']:u['text'] for u in map(json.loads,open(DATA/'e4'/f'units_{app}.jsonl'))})
        qs+=[q for q in map(json.loads,open(DATA/'e4'/f'questions_{app}.jsonl')) if not args.verified_only or q['verified']]
    jobs=[(q,c) for q in qs for c in ('closed','open') if (f"{q['unit_id']}|{q['type']}",c) not in done]
    sem=asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=None)) as client:
        with out.open('a') as h:
            for fut in asyncio.as_completed([ask(client,sem,args,q,c,pages[q['unit_id']]) for q,c in jobs]):
                h.write(json.dumps(await fut)+'\n');h.flush()
    print(json.dumps({'model':args.tag,'answered':len(jobs)}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('apps',nargs='+');ap.add_argument('--base-url',required=True)
    ap.add_argument('--model',required=True);ap.add_argument('--tag',required=True);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--concurrency',type=int,default=32);ap.add_argument('--verified-only',action='store_true')
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
