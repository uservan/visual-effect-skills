"""Evaluator-type labels for M1, from evaluator code at the pinned SHAs.

PSBench, OSWorld and OSExpert use a fixed, hand-read mapping from evaluator function to
type (definitions in annotation_guidelines.md §4). CUA-World ships one verifier.py per
task; those are pre-labelled by an LLM that reads the full verifier (proposals only).
"""
from pathlib import Path
import argparse,asyncio,csv,json
import httpx

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'motivation/benchmark_audit'
SOURCES='/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/sources'
GIMP='OSWorld/desktop_env/evaluators/metrics/gimp.py'
# Read from OSWorld @ 90a245c; "input" = the task's own start image, i.e. no reference output.
FUNCS={
 'check_brightness_decrease_and_structure_sim':('direction_only',f'{GIMP}: mean brightness lower than input + MSE<0.03 vs input after brightness normalisation'),
 'check_contrast_increase_and_structure_sim':('direction_only',f'{GIMP}: contrast higher than input + SSIM>=0.65 vs input'),
 'check_saturation_increase_and_structure_sim':('direction_only',f'{GIMP}: mean saturation higher than input + H/V SSIM>=0.9 vs input'),
 'check_structure_sim':('metric_vs_reference',f'{GIMP}: same size + SSIM>=0.9 vs expected file'),
 'check_structure_sim_resized':('metric_vs_reference',f'{GIMP}: SSIM vs expected after resizing'),
 'check_file_exists_and_structure_sim':('metric_vs_reference',f'{GIMP}: file exists + SSIM>=0.9 vs expected file'),
 'check_image_mirror':('metric_vs_reference',f'{GIMP}: SSIM>=0.99 vs horizontally flipped input'),
 'check_palette_and_structure_sim':('metric_vs_reference',f'{GIMP}: mode==P + SSIM vs expected file'),
 'check_config_status':('exact_state',f'{GIMP}: gimprc key/value equality'),
 'check_image_size':('exact_state',f'{GIMP}: pixel dimensions equal rule'),
 'check_include_exclude':('exact_state','OSWorld/desktop_env/evaluators/metrics/general.py: substring include/exclude on a command output'),
 'check_green_background':('threshold_heuristic',f'{GIMP}: every non-black pixel of expected mask has g>r and g>b'),
 'check_triangle_position':('threshold_heuristic',f'{GIMP}: centroid of 2nd most frequent colour within 5% of centre'),
 'check_textbox_on_leftside':('threshold_heuristic',f'{GIMP}: leftmost dark (<128) pixel within left 35%'),
 'infeasible':('infeasible_check','agent must output FAIL'),
}
# Referenced by OSExpert task JSONs but defined neither in OSExpert @ ed8673d nor OSWorld @ 90a245c (= origin/main on 2026-10-21).
UNRELEASED={'crop_cat_face','blackout_text','blur_cat_body','erase_cat','image_similarity','check_palette_only','check_rect_overlay_position_and_size'}
WEAKEST=['unreleased','vlm_rubric','direction_only','threshold_heuristic','metric_vs_reference','exact_state','infeasible_check']
CUA_TYPES=['exact_state','metric_vs_reference','direction_only','threshold_heuristic','vlm_rubric','hybrid_vlm_and_programmatic']
CUA_SCHEMA={'type':'object','additionalProperties':False,'required':['evaluator_type','checks','uses_vlm','uses_reference_output','note'],
 'properties':{'evaluator_type':{'enum':CUA_TYPES},'checks':{'type':'array','items':{'type':'string'}},
               'uses_vlm':{'type':'boolean'},'uses_reference_output':{'type':'boolean'},'note':{'type':'string'}}}

def fixed(row):
    if row['benchmark']=='PSBench':
        return 'vlm_rubric','PSBench/photoshop_evaluators.py:PhotoshopEvaluator._build_messages: judge sees instruction, rubric, START and RESULT; no reference; accepts subtle directionally-correct edits'
    labels=[]
    for f in json.loads(row['evaluator_raw']):
        if f in UNRELEASED:labels.append(('unreleased',f'{f}: definition not released'))
        else:labels.append(FUNCS[f])
    primary=min((t for t,_ in labels),key=WEAKEST.index)
    return primary,' | '.join(f'{t}: {n}' for t,n in labels)

async def cua(client,sem,args,row):
    code=(Path(SOURCES)/row['source_file']).parent.joinpath('verifier.py').read_text()
    msgs=[{'role':'system','content':'You audit benchmark verifiers. Classify what the verifier code actually checks, not what the task asks. '
           'Types: exact_state = equality checks on files/scene parameters/counts; metric_vs_reference = similarity to a stored reference output; '
           'direction_only = a statistic moved in the requested direction relative to the input; threshold_heuristic = hand-set thresholds on image or scene statistics with no reference; '
           'vlm_rubric = a VLM decides; hybrid_vlm_and_programmatic = both a VLM and programmatic checks contribute to pass/fail. '
           'List each pass/fail check briefly in checks. Return only JSON.'},
          {'role':'user','content':json.dumps({'task_id':row['task_id'],'instruction':row['instruction']})+'\n\nverifier.py:\n```python\n'+code[:60000]+'\n```'}]
    body={'model':args.model,'messages':msgs,'temperature':0.6,'top_p':0.95,'seed':args.seed,'max_tokens':12000,
          'response_format':{'type':'json_schema','json_schema':{'name':'verifier','schema':CUA_SCHEMA}}}
    async with sem:
        for attempt in range(3):
            body['seed']=args.seed+attempt  # same seed would repeat the same failure
            try:
                r=await client.post(f'{args.base_url}/chat/completions',json=body,timeout=900);r.raise_for_status()
                return row,json.loads(r.json()['choices'][0]['message']['content'])
            except (httpx.HTTPError,json.JSONDecodeError,KeyError,TypeError):pass  # TypeError: content None after max_tokens
        return row,None

async def run(args):
    rows=list(csv.DictReader(open(AUDIT/'task_inventory.csv',encoding='utf-8')))
    out={}
    for r in rows:
        if r['benchmark']!='CUA-World':
            t,n=fixed(r);out[(r['benchmark'],r['task_id'])]=dict(evaluator_type=t,evaluator_note=n,label_source='code_read_fixed_map')
    cua_rows=[r for r in rows if r['benchmark']=='CUA-World']
    if not args.skip_cua:
        sem=asyncio.Semaphore(args.concurrency)
        async with httpx.AsyncClient() as client:
            for fut in asyncio.as_completed([cua(client,sem,args,r) for r in cua_rows]):
                r,lab=await fut
                out[('CUA-World',r['task_id'])]=dict(evaluator_type=lab['evaluator_type'] if lab else '',
                    evaluator_note=json.dumps(lab,ensure_ascii=False) if lab else 'FAILED',label_source=f'prelabel_{args.tag}_verifier_code')
                print(r['task_id'],lab['evaluator_type'] if lab else 'FAILED',flush=True)
    with (AUDIT/'evaluator_labels.csv').open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,['benchmark','task_id','evaluator_type','evaluator_note','label_source']);w.writeheader()
        for r in rows:
            k=(r['benchmark'],r['task_id'])
            if k in out:w.writerow(dict(benchmark=k[0],task_id=k[1],**out[k]))
    counts={}
    for (b,_),v in out.items():counts.setdefault(b,{}).setdefault(v['evaluator_type'],0);counts[b][v['evaluator_type']]+=1
    print(json.dumps(counts,indent=1))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url',default='http://localhost:8001/v1');ap.add_argument('--model',default='Qwen3.5-397B-A17B-FP8')
    ap.add_argument('--tag',default='qwen35');ap.add_argument('--seed',type=int,default=0);ap.add_argument('--concurrency',type=int,default=16)
    ap.add_argument('--skip-cua',action='store_true')
    asyncio.run(run(ap.parse_args()))
if __name__=='__main__':main()
