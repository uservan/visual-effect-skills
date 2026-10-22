"""E5: ask a vision-language model three questions per item.
  op_image    — START + RESULT shown: which operation was applied?
  param_image — START + RESULT shown, operation named: which setting?
  op_text     — no images: which operation "<does this>"? (the same knowledge in words; control)
Output: $DATA/e5/answers_<tag>.jsonl, resumable.
"""
from pathlib import Path
import argparse,asyncio,base64,json
import httpx

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
SCHEMA={'type':'object','additionalProperties':False,'required':['answer'],'properties':{'answer':{'enum':['A','B','C','D']}}}

def img(path):return {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()}}
def opts(xs):return '\n'.join(f'{l}. {x}' for l,x in zip('ABCD',xs))

def question(it,kind):
    s,r=DATA/'e5/images'/f"{it['item_id']}_start.jpg",DATA/'e5/images'/f"{it['item_id']}_result.jpg"
    tail='\n\nAnswer with the letter of the correct option. Return only JSON.'
    if kind=='op_image':
        return [{'type':'text','text':'An image editor applied exactly one adjustment to START to produce RESULT. Which adjustment?\n'+opts(it['op_options'])+tail},
                {'type':'text','text':'START:'},img(s),{'type':'text','text':'RESULT:'},img(r)],it['op_answer']
    if kind=='param_image':
        return [{'type':'text','text':f"An image editor applied {it['op_name']} to START to produce RESULT. Which setting was used?\n"+opts(it['param_options'])+tail},
                {'type':'text','text':'START:'},img(s),{'type':'text','text':'RESULT:'},img(r)],it['param_answer']
    desc=it['op_options_desc']['ABCD'.index(it['op_answer'])]
    return [{'type':'text','text':f'Which image adjustment {desc}?\n'+opts(it['op_options'])+tail}],it['op_answer']

async def ask(client,sem,args,it,kind):
    content,gold=question(it,kind)
    body={'model':args.model,'messages':[{'role':'user','content':content}],'temperature':0.6,'top_p':0.95,'max_tokens':8000,
          'response_format':{'type':'json_schema','json_schema':{'name':'a','schema':SCHEMA}}}
    async with sem:
        for attempt in range(3):
            body['seed']=args.seed+attempt
            try:
                r=await client.post(f'{args.base_url}/chat/completions',json=body,timeout=900);r.raise_for_status()
                pred=json.loads(r.json()['choices'][0]['message']['content'])['answer']
                return {'item_id':it['item_id'],'op':it['op'],'kind':kind,'gold':gold,'pred':pred,'correct':pred==gold}
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass
    return {'item_id':it['item_id'],'op':it['op'],'kind':kind,'gold':gold,'pred':None,'correct':None}

async def run(args):
    items=[json.loads(l) for l in open(DATA/'e5/items.jsonl')];out=DATA/'e5'/f'answers_{args.tag}.jsonl';done=set()
    if out.exists():done={(j['item_id'],j['kind']) for j in map(json.loads,open(out)) if j['pred']}
    jobs=[(it,k) for it in items for k in ('op_image','param_image','op_text') if (it['item_id'],k) not in done]
    sem=asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=None)) as client:
        with out.open('a') as h:
            for fut in asyncio.as_completed([ask(client,sem,args,it,k) for it,k in jobs]):
                h.write(json.dumps(await fut)+'\n');h.flush()
    print(json.dumps({'model':args.tag,'answered':len(jobs)}))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-url',required=True);ap.add_argument('--model',required=True)
    ap.add_argument('--tag',required=True);ap.add_argument('--seed',type=int,default=0);ap.add_argument('--concurrency',type=int,default=32)
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
