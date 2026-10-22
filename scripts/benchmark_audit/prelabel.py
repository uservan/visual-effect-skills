"""LLM pre-labels for M1 (proposals only; humans adjudicate).

Labels instruction-derived fields from annotation_guidelines.md. evaluator_type is NOT
asked of the model: it must be labelled from evaluator code (see label_evaluators.py).
Raw responses are kept so every pre-label can be inspected.
"""
from pathlib import Path
import argparse,asyncio,csv,json,re
import httpx

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'motivation/benchmark_audit'
SOURCES='/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/sources'
FORMS=['procedural_explicit','tool_named','attribute_direction','outcome_described','reference_image','infeasible','non_visual']
COMPONENT_FORMS=FORMS[:4]
SCHEMA={'type':'object','additionalProperties':False,'required':['components','instruction_form','k_tags','initial_state','preservation_clause','scope','instruction_defect','confidence','note'],
 'properties':{
  'components':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['text','form'],
                'properties':{'text':{'type':'string'},'form':{'enum':COMPONENT_FORMS}}}},
  'instruction_form':{'enum':FORMS},
  'k_tags':{'type':'array','items':{'enum':['K1','K2','K3','K4','K5']}},
  'initial_state':{'enum':['flat_image','stateful_project','no_document','multi_file']},
  'preservation_clause':{'type':'boolean'},'scope':{'enum':['global','local','mixed']},
  'instruction_defect':{'type':'boolean'},'confidence':{'enum':['high','medium','low']},'note':{'type':'string'}}}
ORDER={f:i for i,f in enumerate(COMPONENT_FORMS)}
FILES=re.compile(r'[\w./-]+\.(?:jpe?g|png|xcf|tiff?|svg|pptx|tnz|pli|tlv|psd|mp4|webp)\b',re.I)

def input_files(row):
    """File names referenced by the task setup, so initial_state can be judged."""
    if row['benchmark']=='PSBench':return ['start image (.jpg)']
    f=Path(SOURCES)/row['source_file'];text=f.read_text()
    if row['benchmark']=='CUA-World':
        text+=''.join(p.read_text(errors='ignore') for p in f.parent.glob('setup_task.sh'))
    else:
        text=json.dumps(json.loads(text).get('config',[]))
    # task_initial*.png are setup screenshots taken by CUA-World scripts, not task inputs.
    return sorted({Path(m).name for m in FILES.findall(text)}-{'task_initial.png','task_initial_state.png'})[:12]

def prompt(row,guide):
    task={'benchmark':row['benchmark'],'app':row['app'],'category':row['category'],'difficulty':row['difficulty'],
          'instruction':row['instruction'],'input_files':input_files(row),'evaluator_functions':row['evaluator_raw']}
    return [{'role':'system','content':'You are an annotator for a benchmark audit. Apply the guidelines exactly. '
             'Label what the agent is given and must supply itself. When unsure choose the more conservative label and explain in note. '
             'Return only JSON matching the schema.\n\n# Guidelines\n'+guide},
            {'role':'user','content':json.dumps(task,ensure_ascii=False,indent=1)}]

def derive(lab):
    """Task form = most demanding component unless a task-level label applies."""
    comps=lab['components'];counts={f:sum(c['form']==f for c in comps) for f in COMPONENT_FORMS}
    form=lab['instruction_form']
    if form in COMPONENT_FORMS and comps:form=max((c['form'] for c in comps),key=ORDER.get)
    ks=sorted(set(lab['k_tags']))
    return form,counts,ks,(ks[-1] if ks else '')

async def label(client,sem,args,row,guide):
    async with sem:
        body={'model':args.model,'messages':prompt(row,guide),'temperature':0.6,'top_p':0.95,'seed':args.seed,'max_tokens':12000,
              'response_format':{'type':'json_schema','json_schema':{'name':'labels','schema':SCHEMA}}}
        for attempt in range(3):
            # A new seed per retry: the same seed reproduces the same failure (e.g. whitespace runaway under guided JSON).
            body['seed']=args.seed+attempt
            try:
                r=await client.post(f'{args.base_url}/chat/completions',json=body,timeout=900);r.raise_for_status()
                msg=r.json()['choices'][0]['message'];return row,json.loads(msg['content']),msg.get('reasoning_content') or msg.get('reasoning') or ''
            # TypeError: content is None when the reasoning trace exhausts max_tokens before the answer.
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError) as e:err=repr(e)
        return row,None,err

async def run(args):
    rows=list(csv.DictReader(open(AUDIT/'task_inventory.csv',encoding='utf-8')))
    if args.limit:rows=rows[:args.limit]
    guide=(AUDIT/'annotation_guidelines.md').read_text()
    raw_path=AUDIT/f'prelabel_{args.tag}_raw.jsonl';done={}
    if raw_path.exists():
        for line in raw_path.open():
            rec=json.loads(line)
            if rec['labels']:done[(rec['benchmark'],rec['task_id'])]=rec
    todo=[r for r in rows if (r['benchmark'],r['task_id']) not in done]
    sem=asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient() as client:
        with raw_path.open('a') as h:
            for fut in asyncio.as_completed([label(client,sem,args,r,guide) for r in todo]):
                row,lab,reasoning=await fut
                rec={'benchmark':row['benchmark'],'task_id':row['task_id'],'model':args.model,'seed':args.seed,'labels':lab,'reasoning_or_error':reasoning}
                h.write(json.dumps(rec,ensure_ascii=False)+'\n');h.flush()
                if lab:done[(row['benchmark'],row['task_id'])]=rec
                print(len(done),row['benchmark'],row['task_id'],lab['instruction_form'] if lab else 'FAILED',flush=True)
    fields=['benchmark','task_id','annotator','instruction_form','n_components','n_procedural','n_tool_named','n_attribute','n_outcome','k_tags','k_max',
            'initial_state','evaluator_type','evaluator_note','preservation_clause','scope','instruction_defect','confidence','note']
    with (AUDIT/f'prelabel_{args.tag}.csv').open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fields);w.writeheader()
        for r in rows:
            rec=done.get((r['benchmark'],r['task_id']))
            if not rec:continue
            lab=rec['labels'];form,c,ks,kmax=derive(lab)
            w.writerow(dict(benchmark=r['benchmark'],task_id=r['task_id'],annotator=f'prelabel_{args.tag}',instruction_form=form,n_components=len(lab['components']),
                            n_procedural=c['procedural_explicit'],n_tool_named=c['tool_named'],n_attribute=c['attribute_direction'],n_outcome=c['outcome_described'],
                            k_tags=';'.join(ks),k_max=kmax,initial_state=lab['initial_state'],preservation_clause='yes' if lab['preservation_clause'] else 'no',
                            scope=lab['scope'],instruction_defect='yes' if lab['instruction_defect'] else 'no',confidence=lab['confidence'],note=lab['note']))
    print(json.dumps({'labelled':len(done),'total':len(rows)}))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url',default='http://localhost:8001/v1');ap.add_argument('--model',default='Qwen3.5-397B-A17B-FP8')
    ap.add_argument('--tag',default='qwen35');ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--concurrency',type=int,default=32);ap.add_argument('--limit',type=int,default=0)
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
